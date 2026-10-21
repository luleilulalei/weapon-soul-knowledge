using System;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

namespace Qiling
{
    /// <summary>Development keyboard transport. Replace with a verified ITrainingInput implementation for hardware.</summary>
    public interface ITrainingInput
    {
        event Action<Motion, long, int, double> ActionReceived;
        void Poll(DeviceStatus status, int window, double clock);
    }

    public sealed class TrainingGame : MonoBehaviour
    {
        public TrainingSession Session { get; private set; }
        public ITrainingInput HardwareInput { get; private set; }
        RectTransform root;
        Font font;
        Text timer, message, statusText;
        Image timerFill;
        GameObject debugPanel;
        bool showDebug, charging, disconnected, risk, docked, simulation, captureMode;
        int revision = -1;
        public SwordTrajectory Trajectory { get; private set; }
        string lastMessage, lastGate;
        
        static readonly Color Bg = Hex("0B1020"), Card = Hex("151E32"), Cyan = Hex("72E5DB"), Gold = Hex("E7BD79"), White = Hex("F4F3ED"), Muted = Hex("98A8BE"), Bad = Hex("F3A896");

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot() { if (FindObjectOfType<TrainingGame>() == null) new GameObject("Qiling Game").AddComponent<TrainingGame>(); }
        void Awake()
        {
            Session = new TrainingSession();
            simulation = Application.isEditor || Debug.isDebugBuild;
            captureMode = simulation && Array.IndexOf(Environment.GetCommandLineArgs(), "--qiling-capture") >= 0;
            if (captureMode) Application.runInBackground = true;
            Application.targetFrameRate = 60;
            Screen.orientation = ScreenOrientation.LandscapeLeft;
            font = Resources.Load<Font>("NotoSansSC");
            if (font == null) font = Font.CreateDynamicFontFromOSFont(new[] { "PingFang SC", "Arial Unicode MS", "sans-serif" }, 20);
            if (FindObjectOfType<EventSystem>() == null) new GameObject("Input", typeof(EventSystem), typeof(StandaloneInputModule));
            var canvas = new GameObject("Training Canvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            canvas.GetComponent<Canvas>().renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = canvas.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(844, 390); scaler.matchWidthOrHeight = .5f;
            root = NewRect(canvas.transform, "Safe Area", 0, 0, 844, 390);
            root.anchorMin = root.anchorMax = root.pivot = new Vector2(.5f, .5f); root.anchoredPosition = Vector2.zero;
            var cameraObject = new GameObject("Training Camera", typeof(Camera));
            var cam = cameraObject.GetComponent<Camera>(); cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = Bg;
            Trajectory = gameObject.AddComponent<SwordTrajectory>(); Trajectory.Initialize(Session, root); Trajectory.Recognized += OnMotion;
            new GameObject("Live 3D arena").AddComponent<Arena3D>().Initialize(Session, Trajectory, cam);
            UpdateDevice(); Session.Tick(0, Time.realtimeSinceStartupAsDouble); Rebuild();
        }
        public void AttachHardware(ITrainingInput input)
        {
            if (HardwareInput != null) HardwareInput.ActionReceived -= OnMotion;
            HardwareInput = input; simulation = false; Trajectory.Cancel(); Trajectory.InputEnabled = false;
            Session.Device.Connected = false;
            if (input != null) input.ActionReceived += OnMotion;
            Session.Interrupt(); revision = -1;
        }
        void OnMotion(Motion motion, long id, int window, double time) { Session.Submit(motion, id, window, time); }
        void UpdateDevice()
        {
            var clock = Time.realtimeSinceStartupAsDouble;
            if (simulation)
            {
                var d = Session.Device; d.Connected = !disconnected; d.Authorized = true; d.SwordVerified = true;
                d.Charging = charging; d.Risk = risk; d.Docked = docked; d.ObservedAt = clock;
            }
            else HardwareInput?.Poll(Session.Device, Session.Window, clock);
        }
        void Update()
        {
            UpdateDevice(); Session.Tick(Time.unscaledDeltaTime, Time.realtimeSinceStartupAsDouble);
            if (simulation)
            {
                if (Input.GetKeyDown(KeyCode.LeftArrow) || Input.GetKeyDown(KeyCode.A)) Simulate(Motion.Left);
                if (Input.GetKeyDown(KeyCode.RightArrow) || Input.GetKeyDown(KeyCode.D)) Simulate(Motion.Right);
                if (Input.GetKeyDown(KeyCode.Space)) Simulate(Motion.Block);
                if (Input.GetKeyDown(KeyCode.W)) Simulate(Motion.Raise);
                if (Input.GetKeyUp(KeyCode.W) || Input.GetKeyUp(KeyCode.Space)) Trajectory.EndHold();
                if (Input.GetKeyDown(KeyCode.S) || Input.GetKeyDown(KeyCode.DownArrow)) Simulate(Motion.Down);
                if (Input.GetKeyDown(KeyCode.U)) Simulate(Motion.Unknown);
                if (Input.GetKeyDown(KeyCode.X)) Simulate(Motion.LeavePose);
                if (Input.GetKeyDown(KeyCode.F1)) { showDebug = !showDebug; revision = -1; }
                if (Input.GetKeyDown(KeyCode.C)) { charging = !charging; revision = -1; }
                if (Input.GetKeyDown(KeyCode.L)) { disconnected = !disconnected; revision = -1; }
                if (Input.GetKeyDown(KeyCode.B)) { docked = !docked; revision = -1; }
            }
            if (Input.GetKeyDown(KeyCode.Escape)) Session.Pause();
            if (lastGate != Session.Gate) { lastGate = Session.Gate; revision = -1; }
            if (revision != Session.Window && !Trajectory.Holding) Rebuild();
            if (timer != null) timer.text = Session.Remaining > 0 ? Mathf.CeilToInt(Session.Remaining).ToString("00") : "";
            if (timerFill != null)
            {
                float ratio = Session.Duration > 0 ? Session.Remaining / Session.Duration : 0;
                timerFill.rectTransform.sizeDelta = new Vector2(320 * (Session.State == Phase.Charging ? 1 - ratio : ratio), 4);
            }
            if (message != null && lastMessage != Session.Message) { message.text = Session.Message; lastMessage = Session.Message; }
            if (statusText != null) statusText.text = simulation ? "开发模拟 · 不连接实体硬件" : (Session.Device.Connected ? "硬件已连接" : "等待硬件连接");
            // Fit a fixed landscape composition inside the device safe area without stretching.
            var safe = Screen.safeArea;
            float s = Mathf.Min(safe.width / 844f, safe.height / 390f);
            float canvasScale = root.GetComponentInParent<Canvas>().scaleFactor;
            root.localScale = Vector3.one * s / canvasScale;
            root.anchoredPosition = (safe.center - new Vector2(Screen.width, Screen.height) * .5f) / canvasScale;

        }
        void OnApplicationPause(bool paused) { if (paused && !captureMode) Session?.Interrupt(); }
        void OnApplicationFocus(bool focus) { if (!focus && !captureMode && Session != null) Session.Interrupt(); }
        void OnDestroy() { if (HardwareInput != null) HardwareInput.ActionReceived -= OnMotion; }
        void Simulate(Motion motion) { if (simulation) Trajectory.Play(motion); }
        string ModeName => Session.Mode == TrainingMode.Discern ? "辨向" : Session.Mode == TrainingMode.Rhythm ? "节拍" : "守门者";
        string SkillName => Session.SelectedSkill == Skill.Single ? "基础斩" : Session.SelectedSkill == Skill.Combo ? "回锋" : "蓄势斩";
        void Rebuild()
        {
            foreach (Transform child in root) { child.gameObject.SetActive(false); Destroy(child.gameObject); }
            timer = null; timerFill = null; message = null; statusText = null;
            revision = Session.Window; lastMessage = Session.Message;
            switch (Session.State)
            {
                case Phase.Lobby: LobbyView(); break;
                case Phase.Prepare: PrepareView(); break;
                case Phase.Paused: PauseView(); break;
                case Phase.Reconcile: ReconcileView(); break;
                case Phase.Result: ResultView(); break;
                case Phase.Review: ReviewView(); break;
                default: PlayView(); break;
            }
            Panel(0, 368, 844, 22, Bg);
            statusText = Label(14, 369, 236, 18, "", 10, Gold);
            Label(250, 369, 580, 18, simulation ? "←/A 左斩   →/D 右斩   空格 格挡   W 举剑   S 下斩   Esc 暂停   F1 调试" : "感觉不安全时立即停下并放下剑；靠近手机前停止挥动。", 10, Muted);
            if (showDebug && simulation) DebugView();
        }
        void Sidebar()
        {
            Panel(0, 0, 80, 368, Bg);
            Label(13, 18, 54, 42, "器灵", 22, Cyan, TextAnchor.MiddleCenter);
            Label(10, 72, 60, 20, "雾 光", 11, Gold, TextAnchor.MiddleCenter);
            Panel(12, 148, 56, 52, Card); Label(12, 148, 56, 52, "训练", 14, Cyan, TextAnchor.MiddleCenter);
            Label(12, 314, 56, 32, "V1.4", 11, Muted, TextAnchor.MiddleCenter);
        }
        void Header(string title, string subtitle)
        {
            Sidebar(); Label(104, 20, 650, 38, title, 27, White); Label(105, 60, 690, 24, subtitle, 12, Muted);
        }
        void LobbyView()
        {
            Header("训练场", "与雾光一起，把每一次动作练得更从容。");
            Panel(104, 108, 300, 238, new Color(.04f, .07f, .12f, .62f));
            Label(124, 125, 260, 25, "QILING  /  TRAINING", 12, Gold);
            Label(124, 171, 260, 70, "循光而行\n一招一式，皆有回应", 24, White);
            Label(124, 264, 258, 60, "本地开发练习\n进度仅在本次运行内有效，不产生长期成长。", 12, Muted);
            string[] names = { "辨向", "节拍", "守门者" };
            string[] desc = { "基础斩 · 6 次提示，至少 4 次有效", "回锋 · 4 组组合，至少 3 组完整", "攻防练习 · 格挡后完成三次反击" };
            for (int i = 0; i < 3; i++)
            {
                var mode = (TrainingMode)i; bool unlocked = Session.IsUnlocked(mode); float y = 106 + 81 * i;
                Panel(424, y, 396, 72, Card); Label(440, y + 10, 45, 44, "0" + (i + 1), 25, unlocked ? Gold : Muted);
                Label(494, y + 8, 200, 26, names[i], 19, White); Label(494, y + 38, 224, 20, desc[i], 10, Muted);
                Button(738, y + 17, 66, 38, unlocked ? "准备" : "未解锁", () => Session.Select(mode), unlocked, unlocked);
            }
        }
        void PrepareView()
        {
            Header(ModeName + " · 开始前准备", "先在近屏处完成设置，放稳手机后再回到站位。");
            Panel(104, 102, 316, 244, Card); Label(124, 117, 270, 30, "雾光  /  训练剑", 21, White);
            Label(124, 162, 270, 54, Session.Gate == "" ? "当前设备条件已满足\n硬件麦克风状态：" + (Session.Device.MicrophoneOn ? "开" : "关") : Session.Gate, 14, Session.Gate == "" ? Cyan : Bad);
            Label(124, 232, 270, 80, "只判断方向与时机，不要求更用力。\n充电或入座时不能开始训练。\n动作幅度与识别参数仍待实机验证。", 12, Muted);
            Panel(436, 102, 384, 244, Card);
            Label(454, 113, 340, 24, "本次技能", 13, Muted);
            for (int i = 0; i < 3; i++)
            {
                var skill = (Skill)i; string name = i == 0 ? "基础斩" : i == 1 ? "回锋" : "蓄势斩";
                bool enabled = Session.Mode == TrainingMode.Guardian && (i != 2 || Session.ChargeUnlocked);
                Button(454 + i * 114, 145, 104, 34, name, () => { Session.SelectSkill(skill); revision = -1; }, Session.SelectedSkill == skill, enabled);
            }
            Button(454, 191, 344, 32, (Session.SpaceConfirmed ? "✓ " : "○ ") + "周围空间已检查，无障碍物和旁人", () => { Session.SpaceConfirmed = !Session.SpaceConfirmed; revision = -1; }, false);
            Button(454, 231, 344, 32, (Session.PhonePlaced ? "✓ " : "○ ") + "手机已放稳，可以回到站位", () => { Session.PhonePlaced = !Session.PhonePlaced; revision = -1; }, false);
            Button(454, 284, 220, 42, "开始 8 秒站位准备", () => Session.StartPreparation(), true, Session.Gate == "" && Session.SpaceConfirmed && Session.PhonePlaced);
            Button(684, 284, 114, 42, "返回", () => Session.Lobby(), false);
        }
        void PlayView()
        {
            Panel(0, 0, 844, 64, new Color(.04f, .06f, .12f, .92f));
            Label(24, 12, 280, 25, ModeName + "  /  " + SkillName, 18, White);
            string score = Session.Mode == TrainingMode.Guardian ? "你的生命 " + Pips(Session.PlayerHealth) + "     守门者 " + Pips(Session.EnemyHealth) : "已完成 " + Session.Completed + "/" + (Session.Mode == TrainingMode.Discern ? 6 : 4) + "     有效 " + Session.Successes;
            Label(24, 38, 520, 18, score, 12, Cyan);
            if (Session.IsCombat) Button(730, 13, 90, 37, "暂停", () => Session.Pause(), false);
            else Button(730, 13, 90, 37, "取消", () => Session.CancelPreparation(), false);
            Panel(18, 84, 216, 200, new Color(.04f, .07f, .13f, .78f));
            Label(32, 97, 190, 22, PhaseLabel(), 12, Gold);
            message = Label(32, 132, 186, 85, Session.Message, 20, White);
            Label(32, 222, 186, 55, Hint(), 11, Muted);
            timer = Label(720, 102, 90, 90, "", 52, Cyan, TextAnchor.MiddleCenter);
            Panel(260, 291, 320, 4, Card); timerFill = Panel(260, 291, 320, 4, Cyan);
            Label(280, 68, 420, 24, "在中央拖动画出剑轨迹，或点击下方方向", 12, Cyan);
            if (simulation) {
                Button(240, 315, 98, 40, "← 左斩", () => Simulate(Motion.Left));
                Button(346, 315, 98, 40, "右斩 →", () => Simulate(Motion.Right));
                Button(452, 315, 98, 40, "↓ 下斩", () => Simulate(Motion.Down));
                HoldButton(558, "按住格挡", Motion.Block);
                HoldButton(690, "按住蓄势", Motion.Raise);
            }
            if (Session.State == Phase.Correction) Button(270, 238, 280, 42, "回站位重试（8 秒）", () => Session.StartPreparation());
        }
        void HoldButton(float x, string title, Motion motion)
        {
            var image=Panel(x,315,124,40,Hex("243149")); image.raycastTarget=true;
            var events=image.gameObject.AddComponent<EventTrigger>();
            var down=new EventTrigger.Entry { eventID=EventTriggerType.PointerDown };
            down.callback.AddListener(_ => Trajectory.BeginHold(motion)); events.triggers.Add(down);
            var up=new EventTrigger.Entry { eventID=EventTriggerType.PointerUp };
            up.callback.AddListener(_ => Trajectory.EndHold()); events.triggers.Add(up);
            var leave=new EventTrigger.Entry { eventID=EventTriggerType.PointerExit };
            leave.callback.AddListener(_ => Trajectory.EndHold()); events.triggers.Add(leave);
            Label(x,315,124,40,title,13,White,TextAnchor.MiddleCenter);
        }

        string PhaseLabel()
        {
            switch (Session.State)
            {
                case Phase.Countdown: return "01 / 回到站位";
                case Phase.Demo: return "02 / 方向示范";
                case Phase.Calibrate: case Phase.Correction: return "03 / 不计分方向验证";
                case Phase.Ready: return "准备完成";
                case Phase.Charging: return "蓄势进度 · 尚未就绪";
                case Phase.Release: return "剩余释放时间";
                case Phase.Telegraph: return "敌方防御 · 不计反击";
                case Phase.Feedback: return "动作判定";
                default: return "跟随方向与节奏";
            }
        }
        string Hint() => Session.State == Phase.Countdown ? "倒计时不是安全距离标准。" : Session.State == Phase.Correction ? "无需更用力；先回自然姿态。" : Session.State == Phase.Charging ? "保持举剑；提前下斩会取消蓄势。" : "收到动作不等于命中；以有效判定为准。";
        void Overlay(string title, string subtitle)
        {
            Panel(0, 0, 844, 368, new Color(.03f, .05f, .10f, .87f));
            Label(108, 65, 628, 44, title, 30, White); Label(108, 118, 628, 65, subtitle, 15, Muted);
        }
        void PauseView()
        {
            Overlay("训练已暂停", "当前关卡：" + ModeName + "\n已确认的生命与次数保留，未完成的回锋和蓄势已清空。");
            Button(108, 217, 280, 48, "重新准备后继续", () => Session.Resume());
            Button(408, 217, 280, 48, "主动结束本局", () => Session.Exit(), false);
            Button(108, 276, 180, 38, "回看动作说明", () => Session.Review(), false);
            Label(108, 326, 628, 32, "恢复需重新回站位并验证方向。触屏暂停不代表已解决远距离暂停。", 13, Muted);
        }
        void ReconcileView()
        {
            Overlay("训练已停止 · 结果待核对", Session.Message + "\n重新连接不等于已确认本局结果，当前不会发放成长。");
            Label(108, 212, 628, 48, "请停止动作。硬件与结算服务接入后，在此等待唯一终态。", 16, Gold);
            if (simulation) Button(108, 283, 400, 44, "开发模拟：确认本局已中断", () => Session.ResolveInterrupted(Session.SessionId), true, Session.Gate == "");
        }
        void ResultView()
        {
            Header(Session.Message, "本次为本地开发练习，不保存长期成长或器灵记忆。");
            Panel(104, 108, 304, 238, Card); Label(126, 127, 260, 24, ModeName + " / 本局结果", 14, Gold);
            Label(126, 166, 260, 80, Session.Mode == TrainingMode.Guardian ? Session.Successes + " 次有效反击" : Session.Successes + " / " + (Session.Mode == TrainingMode.Discern ? "6 次有效" : "4 组完整"), 28, Cyan);
            Label(126, 267, 260, 56, Session.Result == Outcome.Interrupted ? "无胜负 · 无新增成长" : Session.Result == Outcome.Exited ? "已主动结束 · 已有技能保留" : "按本局实际动作判定生成", 13, Muted);
            Panel(428, 108, 392, 238, Card);
            string note = Session.Result == Outcome.Won ? Session.Mode == TrainingMode.Rhythm ? (Session.FirstUnlock ? "本次练习已开放：蓄势斩" : "本次练习中已拥有蓄势斩") : "把这份节奏，带到下一次练习。" : "先休息，再从容地练一次。";
            Label(450, 128, 344, 70, note, 21, White);
            Button(450, 215, 344, 44, "再练一次 · " + ModeName, () => Session.Select(Session.Mode));
            Button(450, 279, 210, 44, "回训练场休息", () => Session.Lobby(), false);
            Button(674, 279, 120, 44, "动作回看", () => Session.Review(), false);
        }
        void ReviewView()
        {
            Overlay("动作回看", "以下为开发说明，具体握持姿态、动作幅度和识别标准仍需实机验证。");
            string[] titles = { "基础斩", "回锋", "蓄势斩" };
            string[] notes = { "跟随提示左斩或右斩。\n方向以你自己为参照。", "先左斩，再右斩。\n两段完整才算一次有效组合。", "举剑蓄势，等待就绪。\n就绪后向下释放。" };
            for (int i = 0; i < 3; i++)
            {
                Panel(108 + 214 * i, 186, 202, 96, Card);
                Label(120 + 214 * i, 194, 178, 24, titles[i], 18, Cyan);
                Label(120 + 214 * i, 225, 178, 48, notes[i], 12, Muted);
            }
            Button(108, 302, 300, 44, Session.IsLive ? "返回暂停菜单" : "回到准备", () => Session.CancelPreparation());
            Label(432, 302, 308, 44, "守门者：先在来袭窗口格挡，\n看到反击提示后才执行技能。", 12, Gold);
        }
        void DebugView()
        {
            debugPanel = Panel(410, 67, 410, 276, Hex("202D43")).gameObject;
            Label(428, 76, 370, 26, "开发模拟面板 · F1 收起", 17, Gold);
            Motion[] motions = { Motion.Left, Motion.Right, Motion.Block, Motion.Raise, Motion.Down, Motion.Unknown, Motion.LeavePose };
            string[] labels = { "左斩", "右斩", "格挡", "举剑", "下斩", "未知动作", "离开姿态" };
            for (int i = 0; i < motions.Length; i++) { var motion = motions[i]; Button(428 + (i % 3) * 126, 114 + (i / 3) * 40, 116, 32, labels[i], () => Simulate(motion), false); }
            Button(428, 241, 116, 34, charging ? "结束充电" : "模拟充电", () => { charging = !charging; revision = -1; }, false);
            Button(554, 241, 116, 34, disconnected ? "模拟重连" : "模拟断连", () => { disconnected = !disconnected; revision = -1; }, false);
            Button(680, 241, 116, 34, risk ? "清除风险" : "模拟风险", () => { risk = !risk; revision = -1; }, false);
            Label(428, 286, 370, 42, "模拟按键不代表获批硬件控制映射。\nU 未知动作  /  X 离姿  /  B 入座切换", 11, Muted);
        }
        static string Pips(int count) => new string('●', count) + new string('○', 3 - count);
        static Color Hex(string hex) { ColorUtility.TryParseHtmlString("#" + hex, out var c); return c; }
        static RectTransform NewRect(Transform parent, string name, float x, float y, float w, float h)
        {
            var r = new GameObject(name, typeof(RectTransform)).GetComponent<RectTransform>(); r.SetParent(parent, false);
            r.anchorMin = r.anchorMax = r.pivot = new Vector2(0, 1); r.anchoredPosition = new Vector2(x, -y); r.sizeDelta = new Vector2(w, h); return r;
        }
        Image Panel(float x, float y, float w, float h, Color c)
        {
            var image = NewRect(root, "Panel", x, y, w, h).gameObject.AddComponent<Image>(); image.color = c; image.raycastTarget = false; return image;
        }
        Text Label(float x, float y, float w, float h, string text, int size, Color color, TextAnchor anchor = TextAnchor.UpperLeft)
        {
            var t = NewRect(root, text.Length > 24 ? text.Substring(0, 24) : text, x, y, w, h).gameObject.AddComponent<Text>();
            t.text = text; t.font = font; t.fontSize = size; t.color = color; t.alignment = anchor;
            t.horizontalOverflow = HorizontalWrapMode.Wrap; t.verticalOverflow = VerticalWrapMode.Overflow; t.raycastTarget = false; return t;
        }
        void Button(float x, float y, float w, float h, string text, Action action, bool primary = true, bool enabled = true)
        {
            var image = Panel(x, y, w, h, primary ? Cyan : Hex("243149")); image.raycastTarget = true;
            var b = image.gameObject.AddComponent<Button>(); b.targetGraphic = image; b.interactable = enabled;
            var colors = b.colors; colors.disabledColor = new Color(.42f, .45f, .50f, .7f); colors.highlightedColor = new Color(.9f, 1, 1); b.colors = colors;
            b.onClick.AddListener(() => { action(); revision = -1; });
            Label(x + 5, y, w - 10, h, text, h < 35 ? 11 : 14, primary ? Bg : enabled ? White : Muted, TextAnchor.MiddleCenter);
        }
    }
}
