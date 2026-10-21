using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;

namespace Qiling
{
    public enum TrajectorySource { Pointer, Simulated, HardwarePose }
    public struct SwordPoseSample
    {
        public string SessionId;
        public int Window;
        public long Sequence;
        public double Time;
        public Quaternion Orientation;
        public TrajectorySource Source;
    }
    // All sources share the same calibrated orientation-to-tip projection. The grip is fixed;
    // this is a visual reconstruction from attitude, never measured 6-DoF tip position.
    public sealed class SwordTrajectory : MonoBehaviour
    {
        public event Action<Motion, long, int, double> Recognized;
        public Vector3 Tip { get; private set; } = new Vector3(.7f, 2.8f, -1.5f);
        public readonly Vector3 Grip = new Vector3(.25f, .55f, -3.0f);
        public bool Moving { get; private set; }
        public bool Holding { get; private set; }
        public bool InputEnabled = true;
        public TrajectorySource Source { get; private set; }
        TrainingSession session;
        RectTransform ui;
        readonly List<Vector2> points = new List<Vector2>();
        bool stroke, playback, held, emitted;
        Motion heldMotion;
        int window;
        string sessionId;
        long sequence, lastHardwareSequence = -1;
        double lastHardwareTime;
        float age, holdTime;
        Vector2 start, end;
        public string Diagnostic { get; private set; } = "触屏轨迹模拟";
        public void Initialize(TrainingSession model, RectTransform canvas) { session = model; ui = canvas; }
        bool Allowed => session != null && (session.IsCombat || session.State == Phase.Calibrate);
        public void Play(Motion motion)
        {
            if (!Allowed || !InputEnabled || playback || held) return;
            if (motion == Motion.Unknown || motion == Motion.LeavePose) { Emit(motion, session.Window); return; }
            if (motion == Motion.Block || motion == Motion.Raise) { BeginHold(motion); return; }
            start = motion == Motion.Left ? new Vector2(.9f,.7f) : motion == Motion.Right ? new Vector2(.1f,.65f) : new Vector2(.52f,.95f);
            end = motion == Motion.Left ? new Vector2(.1f,.35f) : motion == Motion.Right ? new Vector2(.9f,.35f) : new Vector2(.48f,.06f);
            Begin(start, TrajectorySource.Simulated); playback = true; age = 0;
        }
        public void BeginHold(Motion motion)
        {
            if (!Allowed || !InputEnabled || playback || held) return;
            Cancel();
            held = true; heldMotion = motion; holdTime = 0; emitted = false; window = session.Window; sessionId = session.SessionId;
            Source = TrajectorySource.Pointer;
        }
        public void EndHold()
        {
            if (!held) return;
            bool cancel = heldMotion == Motion.Raise && emitted && session.State == Phase.Charging;
            held = false; Holding = false;
            if (cancel) Emit(Motion.LeavePose, session.Window);
        }
        public void Cancel()
        {
            stroke = playback = held = Moving = Holding = false; points.Clear();
        }
        void Begin(Vector2 p, TrajectorySource source)
        {
            if (!Allowed) return;
            stroke = true; Moving = true; points.Clear(); window = session.Window; sessionId = session.SessionId; Source = source;
            Add(p);
        }
        void Add(Vector2 p)
        {
            p.x = Mathf.Clamp01(p.x); p.y = Mathf.Clamp01(p.y);
            if (points.Count < 256) points.Add(p);
            Vector3 aimedTip = new Vector3(Mathf.Lerp(-2.6f,2.6f,p.x), Mathf.Lerp(.8f,3.8f,p.y), -1.2f);
            var orientation = Quaternion.FromToRotation(Vector3.up, (aimedTip - Grip).normalized);
            ApplyOrientation(orientation);
        }
        void Finish()
        {
            stroke = playback = Moving = false;
            if (session.Window != window || session.SessionId != sessionId) { Diagnostic = "旧窗口轨迹已丢弃"; return; }
            Motion result = Classify(points);
            Diagnostic = result == Motion.Unknown ? "轨迹不清楚" : "轨迹识别：" + result;
            Emit(result, window);
        }
        public static Motion Classify(IList<Vector2> trajectory)
        {
            if (trajectory == null || trajectory.Count < 3) return Motion.Unknown;
            var d = trajectory[trajectory.Count-1] - trajectory[0];
            if (d.magnitude < .16f) return Motion.Unknown;
            float path = 0;
            for (int i=1;i<trajectory.Count;i++) path += Vector2.Distance(trajectory[i],trajectory[i-1]);
            if (path > d.magnitude * 2.7f) return Motion.Unknown;
            if (Mathf.Abs(d.x) > Mathf.Abs(d.y) * 1.2f) return d.x < 0 ? Motion.Left : Motion.Right;
            if (d.y < -.16f && Mathf.Abs(d.y) > Mathf.Abs(d.x)*1.2f) return Motion.Down;
            return Motion.Unknown;
        }
        public bool PushHardwarePose(SwordPoseSample sample)
        {
            double now = Time.realtimeSinceStartupAsDouble;
            if (InputEnabled || sample.Source != TrajectorySource.HardwarePose || !Allowed || sample.SessionId != session.SessionId || sample.Window != session.Window || sample.Sequence <= lastHardwareSequence || sample.Time <= lastHardwareTime || now-sample.Time > .25 || sample.Time > now+.05) return false;
            var q=sample.Orientation;
            float norm=q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w;
            if (float.IsNaN(norm)||float.IsInfinity(norm)||norm<.5f||norm>1.5f) return false;
            lastHardwareSequence=sample.Sequence;lastHardwareTime=sample.Time;Source=sample.Source;
            ApplyOrientation(q.normalized); Moving=true; Diagnostic="IMU姿态可视化 · 固定握持点"; return true;
        }
        void ApplyOrientation(Quaternion orientation) { Tip = Grip + orientation * Vector3.up * 2.65f; }
        void Emit(Motion m,int w) { Recognized?.Invoke(m, ++sequence, w, Time.realtimeSinceStartupAsDouble); }
        bool OverUI(int finger = -1) => EventSystem.current != null && EventSystem.current.IsPointerOverGameObject(finger);
        Vector2 Pointer(Vector2 screen)
        {
            RectTransformUtility.ScreenPointToLocalPointInRectangle(ui, screen, null, out var local);
            return new Vector2((local.x+422-245)/420, (local.y+195-82)/225);
        }
        bool InArea(Vector2 p) => p.x>=0 && p.x<=1 && p.y>=0 && p.y<=1;
        void Update()
        {
            if (!Allowed) { Cancel(); return; }
            if (!InputEnabled) { if (Time.realtimeSinceStartupAsDouble-lastHardwareTime > .25) Moving=false; return; }
            if (stroke && (session.Window != window || session.SessionId != sessionId)) { Cancel(); return; }
            if (held)
            {
                Holding=true; holdTime += Time.unscaledDeltaTime;
                var target=heldMotion==Motion.Block ? Grip+new Vector3(-2.4f,1.1f,.4f) : Grip+new Vector3(.15f,2.6f,.3f);
                Tip=Vector3.Lerp(Tip,target,1-Mathf.Exp(-18*Time.unscaledDeltaTime));
                if (!emitted && holdTime>=.25f) { emitted=true; Emit(heldMotion,window); }
            }
            if (playback)
            {
                age += Time.unscaledDeltaTime; float t=Mathf.Clamp01(age/.48f);
                var p=Vector2.Lerp(start,end,Mathf.SmoothStep(0,1,t)); p.y+=Mathf.Sin(t*Mathf.PI)*.1f; Add(p);
                if(t>=1)Finish(); return;
            }
            if (held) return;
            bool down, up, pressed; Vector2 position; int finger=-1;
            if(Input.touchCount>0)
            {
                var touch=Input.GetTouch(0);position=touch.position;finger=touch.fingerId;
                if(touch.phase==TouchPhase.Canceled) { Cancel(); return; }
                down=touch.phase==TouchPhase.Began;up=touch.phase==TouchPhase.Ended||touch.phase==TouchPhase.Canceled;pressed=!up;
            }
            else {position=Input.mousePosition;down=Input.GetMouseButtonDown(0);up=Input.GetMouseButtonUp(0);pressed=Input.GetMouseButton(0);}
            var v=Pointer(position);
            if(down&&!OverUI(finger)&&InArea(v)) Begin(v,TrajectorySource.Pointer);
            if(stroke&&pressed) Add(v);
            if(stroke&&up) Finish();
        }
    }
}
