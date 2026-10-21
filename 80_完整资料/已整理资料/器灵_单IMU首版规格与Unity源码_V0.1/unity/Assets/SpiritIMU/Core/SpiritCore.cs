using System;
using System.Collections.Generic;
using System.Globalization;
namespace SpiritIMU {
public enum ActionKind { LeftSlash, RightSlash, DownSlash, GuardEnter, GuardExit, ChargeStart, ChargeReady, Cancel, Neutral }
public enum InputSource { simulated, replay, hardware }
public enum GameMode { Tutorial, Rhythm, Boss }
public enum Phase { Preparation, Tutorial, RhythmLeft, RhythmRight, Defense, Telegraph, Attack, Opening, Paused, Ended }
public enum CounterSkill { Basic, Combo, Charge }
[Serializable] public struct RawSample {
 public string sessionId, deviceId; public long seq, tMs; public float ax,ay,az,gx,gy,gz; public InputSource source;
 public bool Finite { get { return Valid(ax)&&Valid(ay)&&Valid(az)&&Valid(gx)&&Valid(gy)&&Valid(gz); } }
 static bool Valid(float x) { return !float.IsNaN(x)&&!float.IsInfinity(x); }
}
[Serializable] public struct ActionEvent {
 public string sessionId, windowId, eventId, reason; public long tMs; public ActionKind action; public InputSource source;
}
public struct JudgeResult { public bool accepted, hit; public string reason; public JudgeResult(bool a,bool h,string r) {accepted=a;hit=h;reason=r;} }
// A transport adapter must dispatch safety state before samples/actions, on Unity's main thread.
public interface IImuInput { event Action<RawSample> Sample; event Action<string> Interrupted; void Start(); void Stop(); }
public sealed class GameSession {
 public string SessionId {get; private set;} public string WindowId {get; private set;}
 public Phase State {get; private set;} = Phase.Preparation;
 public GameMode Mode {get; private set;} public CounterSkill Skill = CounterSkill.Basic;
 public int PlayerHP {get; private set;} public int BossHP {get; private set;}
 public int Groups {get; private set;} public int CompleteGroups {get; private set;}
 public int TutorialStep {get; private set;} public string Feedback {get; private set;} = "Confirm safety, then prepare";
 public long OpenMs {get; private set;} public long CloseMs {get; private set;}
 public bool Connected=true, Charging=false, Docked=false, Calibrated=false, SafetyConfirmed=false;
 public bool RewardsEnabled {get {return false;}} // Deliberately no account, persistent reward or network implementation.
 public bool ChargeReady {get; private set;} public bool ChargeStarted {get; private set;}
 public int Epoch {get; private set;}
 readonly HashSet<string> seen = new HashSet<string>(); bool comboLeft; int windowNo; long lastNow,chargeStartMs;
 public bool Running {get {return State!=Phase.Preparation&&State!=Phase.Paused&&State!=Phase.Ended;}}
 public bool Start(GameMode mode,long now) {
  if(!Connected||Charging||Docked||!Calibrated||!SafetyConfirmed) {Feedback="Blocked: check safety, calibration and device";return false;}
  SessionId=Guid.NewGuid().ToString("N"); Epoch++; windowNo=0;seen.Clear();Mode=mode;Groups=CompleteGroups=TutorialStep=0;PlayerHP=BossHP=3;comboLeft=false;ClearCharge();lastNow=now;
  Enter(mode==GameMode.Tutorial?Phase.Tutorial:mode==GameMode.Rhythm?Phase.RhythmLeft:Phase.Defense,now);return true;
 }
 void ClearCharge(){ChargeReady=false;ChargeStarted=false;chargeStartMs=-1;}
 void Enter(Phase p,long now) {
  State=p;WindowId=(++windowNo).ToString(CultureInfo.InvariantCulture);OpenMs=now;
  CloseMs=now+(p==Phase.Defense?1000:p==Phase.Telegraph?1200:p==Phase.Attack?1200:p==Phase.Opening?3500:p==Phase.Tutorial?60000:1200);
  comboLeft=false;ClearCharge();Feedback=p.ToString();
 }
 public void Tick(long now) {
  if(now<lastNow){Interrupt("Clock moved backwards");return;}lastNow=now;
  if(!Running)return;
  if(!Connected||Charging||Docked){Interrupt(Docked?"Docked":Charging?"Charging":"Disconnected");return;}
  // No catch-up damage across a stalled app frame.
  if(now>=CloseMs) {
   switch(State) {
    case Phase.Defense:Enter(Phase.Telegraph,now);break;
    case Phase.Telegraph:Enter(Phase.Attack,now);break;
    case Phase.Attack:PlayerHP--;if(PlayerHP==0)End("Defeat (simulation)");else Enter(Phase.Defense,now);break;
    case Phase.Opening:Enter(Phase.Defense,now);Feedback="Counter window missed";break;
    case Phase.RhythmLeft:case Phase.RhythmRight:FinishGroup(false,now);break;
    case Phase.Tutorial:Feedback="Try again gently";Enter(Phase.Tutorial,now);break;
   }
  }
 }
 public void Pause(){if(!Running)return;State=Phase.Paused;Epoch++;Calibrated=false;seen.Clear();ClearCharge();comboLeft=false;Feedback="Paused; recalibrate and start a NEW attempt";}
 public void Interrupt(string why){if(Running||State==Phase.Paused){End("Interrupted: "+why);}Calibrated=false;Epoch++;ClearCharge();}
 public void End(string why){if(State==Phase.Ended)return;State=Phase.Ended;ClearCharge();comboLeft=false;Feedback=why;}
 public void Exit(){End("User exited; no rewards");Calibrated=false;Epoch++;}
 void FinishGroup(bool ok,long now){Groups++;if(ok)CompleteGroups++;if(Groups==4)End(CompleteGroups>=3?"Rhythm passed (simulation)":"Rhythm incomplete (simulation)");else Enter(Phase.RhythmLeft,now);}
 public JudgeResult Submit(ActionEvent e,long now) {
  if(!Running)return new JudgeResult(false,false,"Inactive");
  if(!Connected||Charging||Docked){Interrupt("Unsafe device state");return new JudgeResult(false,false,"Unsafe");}
  if(e.sessionId!=SessionId||e.windowId!=WindowId)return new JudgeResult(false,false,"Old session/window");
  if(string.IsNullOrEmpty(e.eventId)||!seen.Add(e.eventId))return new JudgeResult(false,false,"Duplicate/empty eventId");
  if(e.tMs>now||now-e.tMs>250||e.tMs<OpenMs||e.tMs>=CloseMs||now>=CloseMs)return new JudgeResult(false,false,"Expired/outside [open,close)");
  if(e.action==ActionKind.Cancel||e.action==ActionKind.Neutral){ClearCharge();comboLeft=false;Feedback="Cancelled; return to neutral";if(State==Phase.Tutorial&&TutorialStep==4){TutorialStep++;End("Five-step tutorial complete (simulation)");}return new JudgeResult(true,false,Feedback);}
  if(State==Phase.Tutorial&&TutorialStep==3){if(e.action==ActionKind.GuardEnter||e.action==ActionKind.GuardExit||e.action==ActionKind.LeftSlash||e.action==ActionKind.RightSlash||e.action==ActionKind.DownSlash)ClearCharge();if(e.action==ActionKind.ChargeStart){ClearCharge();ChargeStarted=true;chargeStartMs=e.tMs;return new JudgeResult(true,false,"Charging");}if(e.action==ActionKind.ChargeReady&&(!ChargeStarted||e.tMs-chargeStartMs<800))return new JudgeResult(false,false,"Charge not held 800ms");}
  if(State==Phase.Tutorial){ActionKind[] expected={ActionKind.LeftSlash,ActionKind.RightSlash,ActionKind.GuardEnter,ActionKind.ChargeReady,ActionKind.Cancel};if(e.action==expected[TutorialStep]){TutorialStep++;Feedback="Step complete";if(TutorialStep==5)End("Tutorial complete");return new JudgeResult(true,true,Feedback);}return new JudgeResult(true,false,"Follow current tutorial step");}
  if(State==Phase.RhythmLeft||State==Phase.RhythmRight){if(e.action!=ActionKind.LeftSlash&&e.action!=ActionKind.RightSlash&&e.action!=ActionKind.DownSlash)return new JudgeResult(true,false,"Non-slash ignored");bool left=State==Phase.RhythmLeft;bool ok=e.action==(left?ActionKind.LeftSlash:ActionKind.RightSlash);if(!ok){FinishGroup(false,now);Feedback="Wrong direction/order; group failed";}else if(left)Enter(Phase.RhythmRight,now);else FinishGroup(true,now);return new JudgeResult(true,ok,Feedback);}
  if(State==Phase.Attack&&e.action==ActionKind.GuardEnter){Enter(Phase.Opening,now);return new JudgeResult(true,true,"Guard accepted; counter now");}
  if(State!=Phase.Opening)return new JudgeResult(true,false,"Wait for the correct window");
  bool hit=false;
  if(Skill==CounterSkill.Basic)hit=e.action==ActionKind.LeftSlash||e.action==ActionKind.RightSlash;
  if(Skill==CounterSkill.Combo){if(e.action==ActionKind.LeftSlash){comboLeft=true;Feedback="Combo: now right";}else if(e.action==ActionKind.RightSlash&&comboLeft)hit=true;else comboLeft=false;}
  if(Skill==CounterSkill.Charge){if(e.action==ActionKind.GuardEnter||e.action==ActionKind.LeftSlash||e.action==ActionKind.RightSlash){ClearCharge();Feedback="Charge cancelled: wrong pose/slash";}if(e.action==ActionKind.ChargeStart){ClearCharge();ChargeStarted=true;chargeStartMs=e.tMs;Feedback="Charging";}if(e.action==ActionKind.ChargeReady){if(!ChargeStarted||e.tMs-chargeStartMs<800)return new JudgeResult(false,false,"Charge not held 800ms");ChargeReady=true;Feedback="Ready: down slash";}if(e.action==ActionKind.GuardExit){ClearCharge();Feedback="Pose left; charge cancelled";}if(e.action==ActionKind.DownSlash){hit=ChargeReady;ClearCharge();}}
  if(hit){BossHP--;if(BossHP==0)End("Boss defeated (simulation)");else Enter(Phase.Defense,now);}
  return new JudgeResult(true,hit,hit?"Counter hit":Feedback);
 }
}
}
