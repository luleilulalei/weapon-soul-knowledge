using System;
using System.Collections.Generic;

namespace Qiling
{
    public enum TrainingMode { Discern, Rhythm, Guardian }
    public enum Skill { Single, Combo, Charge }
    public enum Motion { Left, Right, Block, Raise, Down, Unknown, LeavePose }
    public enum Phase { Lobby, Prepare, Countdown, Demo, Calibrate, Correction, Ready, Direction, ComboFirst, ComboSecond, Telegraph, Block, Counter, ChargeWait, Charging, Release, Feedback, Paused, Reconcile, Result, Review }
    public enum Outcome { None, Won, Lost, Exited, Interrupted }

    // Hardware adapters must supply current verified status. No permissive defaults.
    public sealed class DeviceStatus
    {
        public bool Connected, Authorized, SwordVerified, Docked, Charging, Risk, MicrophoneOn;
        public double ObservedAt;
        public string BlockReason(double now)
        {
            if (now - ObservedAt > 2 || now < ObservedAt) return "设备状态已过期，请重新检查";
            if (!Connected) return "器灵未连接";
            if (!Authorized) return "尚未确认设备使用资格";
            if (!SwordVerified) return "尚未确认训练剑";
            if (Charging) return "正在充电，禁止挥剑";
            if (Docked) return "器灵已入座，请先停止训练";
            if (Risk) return "检测到风险，请放下训练剑";
            return "";
        }
    }
    public sealed class TrainingSession
    {
        public Phase State { get; private set; } = Phase.Lobby;
        public TrainingMode Mode { get; private set; }
        public Skill SelectedSkill { get; private set; }
        public Outcome Result { get; private set; }
        public string SessionId { get; private set; } = "";
        public string Message { get; private set; } = "";
        public int Completed { get; private set; }
        public int Successes { get; private set; }
        public int PlayerHealth { get; private set; } = 3;
        public int EnemyHealth { get; private set; } = 3;
        public int PracticeProgress { get; private set; }
        public int Misses { get; private set; }
        public bool FirstUnlock { get; private set; }
        public bool SpaceConfirmed, PhonePlaced;
        public float Remaining { get; private set; }
        public float Duration { get; private set; }
        public int Window { get; private set; }
        public Motion Expected { get; private set; }
        public readonly DeviceStatus Device = new DeviceStatus();
        readonly HashSet<long> acceptedEvents = new HashSet<long>();
        Phase afterFeedback;
        bool active, resuming;
        double now;
        // All times are adjustable development defaults, not validated IMU thresholds.
        public const float StandBackSeconds = 8, ActionSeconds = 3, ChargeSeconds = 2;
        public bool IsCombat => State >= Phase.Direction && State <= Phase.Feedback;
        public bool IsLive => active;
        public bool IsUnlocked(TrainingMode mode) => mode == TrainingMode.Discern || PracticeProgress >= (mode == TrainingMode.Rhythm ? 1 : 2);
        public bool ChargeUnlocked => PracticeProgress >= 2;
        public string Gate => Device.BlockReason(now);

        public void Select(TrainingMode mode)
        {
            if (active || !IsUnlocked(mode)) return;
            Mode = mode; SelectedSkill = mode == TrainingMode.Rhythm ? Skill.Combo : Skill.Single;
            Result = Outcome.None; SpaceConfirmed = PhonePlaced = false;
            Go(Phase.Prepare, 0, "确认周围空间，再放稳手机");
        }
        public void SelectSkill(Skill skill)
        {
            if (State == Phase.Prepare && Mode == TrainingMode.Guardian && (skill != Skill.Charge || ChargeUnlocked)) SelectedSkill = skill;
        }
        public void StartPreparation()
        {
            if (State != Phase.Prepare && State != Phase.Correction) return;
            if (Gate != "" || !SpaceConfirmed || !PhonePlaced) { Message = Gate != "" ? Gate : "请确认空间与手机放置"; return; }
            Go(Phase.Countdown, StandBackSeconds, "请回到安全站位");
        }
        public void CancelPreparation()
        {
            if (active) { Go(Phase.Paused, 0, "训练已暂停"); return; }
            Go(Phase.Prepare, 0, "准备已取消");
        }
        public void Tick(float delta, double clock)
        {
            now = clock;
            if (State == Phase.Lobby || State == Phase.Prepare || State == Phase.Result || State == Phase.Reconcile) return;
            if (Device.Docked) { if (active) Finish(Outcome.Exited); else CancelPreparation(); return; }
            if (Gate != "")
            {
                if (active) { Go(Phase.Reconcile, 0, Gate + "；本局结果待核对"); }
                else Go(Phase.Prepare, 0, Gate);
                return;
            }
            if (State == Phase.Paused || State == Phase.Correction) return;
            if (Remaining <= 0) return;
            Remaining = Math.Max(0, Remaining - Math.Max(0, delta));
            if (Remaining > 0) return;
            switch (State)
            {
                case Phase.Countdown: Go(Phase.Demo, 3, "方向示范：你的右 → 左"); break;
                case Phase.Demo: Go(Phase.Calibrate, 8, "试一次左斩 · 本次不计分"); break;
                case Phase.Calibrate: Go(Phase.Correction, 0, "未收到清楚动作，请自然站立后重试"); break;
                case Phase.Ready: BeginOrResume(); break;
                case Phase.Direction: DirectionDone(false, "未在提示内完成动作"); break;
                case Phase.ComboFirst: case Phase.ComboSecond: ComboDone(false, "本组超时，回到自然姿态"); break;
                case Phase.Telegraph: Go(Phase.Block, ActionSeconds, "现在格挡"); break;
                case Phase.Block: PlayerHealth--; Misses++; if (PlayerHealth == 0) Finish(Outcome.Lost); else Feedback("未完成格挡 · 生命 -1", Phase.Telegraph); break;
                case Phase.Counter: Feedback("反击窗口结束 · 本次未命中", Phase.Telegraph); break;
                case Phase.ChargeWait: Feedback("未开始蓄势 · 本次未命中", Phase.Telegraph); break;
                case Phase.Charging: Go(Phase.Release, ActionSeconds, "蓄势就绪 · 现在向下挥斩"); break;
                case Phase.Release: Feedback("释放超时 · 蓄势已清空", Phase.Telegraph); break;
                case Phase.Feedback: NextWindow(); break;
            }
        }
        void BeginOrResume()
        {
            if (Gate != "") { Go(Phase.Prepare, 0, Gate); return; }
            if (!resuming)
            {
                active = true; SessionId = Guid.NewGuid().ToString("N"); acceptedEvents.Clear();
                Completed = Successes = Misses = 0; PlayerHealth = EnemyHealth = 3; FirstUnlock = false; Result = Outcome.None;
            }
            resuming = false;
            if (Mode == TrainingMode.Discern) OpenDirection();
            else if (Mode == TrainingMode.Rhythm) Go(Phase.ComboFirst, ActionSeconds, "第一段 · 左斩");
            else Go(Phase.Telegraph, 2, "守门者防御中 · 即将从你的右侧来袭");
        }
        // Device timestamps must be converted to this monotonic clock. Window + event ID prevent stale / duplicate damage.
        public void Submit(Motion motion, long eventId, int window, double observedAt)
        {
            if (State != Phase.Calibrate && !IsCombat) return;
            if (Gate != "" || window != Window || now - observedAt > .5 || observedAt > now + .05 || !acceptedEvents.Add(eventId)) return;
            if (State == Phase.Calibrate)
            {
                if (motion == Motion.Left) Go(Phase.Ready, 3, "方向验证完成 · 即将进入训练");
                else Go(Phase.Correction, 0, motion == Motion.Unknown ? "动作还不清楚，无需更用力" : "本次需要左斩，请先回看示范");
                return;
            }
            if (!active || !IsCombat) return;
            if (motion == Motion.Unknown) { Message = "动作还不清楚 · 不计成功"; return; }
            switch (State)
            {
                case Phase.Direction: DirectionDone(motion == Expected, motion == Expected ? "方向正确" : "方向不符，下次跟随提示"); break;
                case Phase.ComboFirst:
                    if (motion == Motion.Left) Go(Phase.ComboSecond, ActionSeconds, "第二段 · 右斩");
                    else ComboDone(false, "顺序未接上 · 先左后右");
                    break;
                case Phase.ComboSecond: ComboDone(motion == Motion.Right, motion == Motion.Right ? "完整回锋" : "顺序未接上 · 本组清空"); break;
                case Phase.Block:
                    if (motion == Motion.Block)
                    {
                        if (SelectedSkill == Skill.Single) Go(Phase.Counter, ActionSeconds, "格挡成功 · 左斩或右斩反击");
                        else if (SelectedSkill == Skill.Combo) Go(Phase.ComboFirst, ActionSeconds, "格挡成功 · 第一段左斩");
                        else Go(Phase.ChargeWait, ActionSeconds, "格挡成功 · 举剑进入蓄势");
                    }
                    else Message = "等待正确格挡 · 不把斩击算作防御";
                    break;
                case Phase.Counter:
                    if (motion == Motion.Left || motion == Motion.Right) Hit();
                    else Feedback("本次未命中", Phase.Telegraph);
                    break;
                case Phase.ChargeWait: if (motion == Motion.Raise) Go(Phase.Charging, ChargeSeconds, "保持蓄势 · 尚未就绪"); break;
                case Phase.Charging: if (motion != Motion.Raise) Feedback("提前释放或离开姿态 · 蓄势已取消", Phase.Telegraph); break;
                case Phase.Release: if (motion == Motion.Down) Hit(); else Feedback("未完成向下释放 · 蓄势已取消", Phase.Telegraph); break;
                case Phase.Telegraph: Message = "敌方防御中 · 等待格挡提示"; break;
            }
        }
        void DirectionDone(bool success, string message)
        {
            Completed++; if (success) Successes++; else Misses++;
            if (Completed == 6) Finish(Successes >= 4 ? Outcome.Won : Outcome.Lost);
            else Feedback(message, Phase.Direction);
        }
        void ComboDone(bool success, string message)
        {
            if (Mode == TrainingMode.Guardian) { if (success) Hit(); else Feedback(message, Phase.Telegraph); return; }
            Completed++; if (success) Successes++; else Misses++;
            if (Completed == 4) Finish(Successes >= 3 ? Outcome.Won : Outcome.Lost);
            else Feedback(message, Phase.ComboFirst);
        }
        void Hit()
        {
            EnemyHealth--; Successes++;
            if (EnemyHealth == 0) Finish(Outcome.Won); else Feedback("有效反击 · 守门者生命 -1", Phase.Telegraph);
        }
        void Feedback(string text, Phase next) { afterFeedback = next; Go(Phase.Feedback, 1.2f, text); }
        void NextWindow()
        {
            if (afterFeedback == Phase.Direction) OpenDirection();
            else if (afterFeedback == Phase.ComboFirst) Go(Phase.ComboFirst, ActionSeconds, "第一段 · 左斩");
            else Go(Phase.Telegraph, 2, "守门者防御中 · 等待来袭");
        }
        void OpenDirection() { Expected = Completed % 2 == 0 ? Motion.Left : Motion.Right; Go(Phase.Direction, ActionSeconds, Expected == Motion.Left ? "左斩 · 你的右 → 左" : "右斩 · 你的左 → 右"); }
        public void Pause()
        {
            if (!active || !IsCombat) return;
            // Confirmed round outcomes stay; incomplete combos and charge are discarded.
            Go(Phase.Paused, 0, "已确认进度保留 · 未完成动作清空");
        }
        public void Review()
        {
            if (State == Phase.Paused || State == Phase.Result || State == Phase.Prepare)
                Go(Phase.Review, 0, "静态动作回看 · 不计分，不会自动进入攻击窗口");
        }
        public void Resume()
        {
            if (State != Phase.Paused || Gate != "") return;
            resuming = true; Go(Phase.Countdown, StandBackSeconds, "恢复前，请回到安全站位");
        }
        public void Interrupt() { if (active && State != Phase.Result) Go(Phase.Reconcile, 0, "本局已停下 · 结果待核对"); }
        public void ResolveInterrupted(string sessionId)
        {
            if (State == Phase.Reconcile && Gate == "" && sessionId == SessionId) Finish(Outcome.Interrupted);
        }
        public void Exit() { if (active && State != Phase.Reconcile) Finish(Outcome.Exited); }
        public void Lobby()
        {
            if (State == Phase.Reconcile || active) return;
            resuming = false; Go(Phase.Lobby, 0, "");
        }
        void Finish(Outcome outcome)
        {
            if (!active || Result != Outcome.None) return;
            Result = outcome; active = false; resuming = false;
            if (outcome == Outcome.Won)
            {
                if (Mode == TrainingMode.Discern) PracticeProgress = Math.Max(PracticeProgress, 1);
                if (Mode == TrainingMode.Rhythm) { FirstUnlock = PracticeProgress < 2; PracticeProgress = 2; }
            }
            Go(Phase.Result, 0, outcome == Outcome.Won ? "训练完成" : outcome == Outcome.Lost ? "本次练习结束" : outcome == Outcome.Exited ? "主动退出" : "本局已中断");
        }
        void Go(Phase phase, float seconds, string message) { State = phase; Duration = Remaining = seconds; Message = message; Window++; }
    }
}
