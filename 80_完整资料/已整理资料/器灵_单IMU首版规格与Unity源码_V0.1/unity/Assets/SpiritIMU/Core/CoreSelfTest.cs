using System;
namespace SpiritIMU {
// No NUnit dependency. Invoke editor menu Spirit IMU/Run core self tests.
public static class CoreSelfTest {
 static int id;
 static void Check(bool test,string message){if(!test)throw new Exception("FAIL: "+message);}
 static GameSession New(GameMode mode,CounterSkill skill=CounterSkill.Basic){var g=new GameSession{SafetyConfirmed=true,Calibrated=true,Skill=skill};Check(g.Start(mode,0),"start");return g;}
 static JudgeResult Send(GameSession g,ActionKind a,long t,string eventId=null){return g.Submit(new ActionEvent{sessionId=g.SessionId,windowId=g.WindowId,eventId=eventId??(++id).ToString(),action=a,tMs=t,source=InputSource.simulated},t);}
 static void Opening(GameSession g){g.Tick(1000);g.Tick(2200);Check(g.State==Phase.Attack,"attack phase");Check(Send(g,ActionKind.GuardEnter,2201).hit,"guard");Check(g.PlayerHP==3,"no simultaneous damage");}
 public static void Run(){
  var g=new GameSession();Check(!g.Start(GameMode.Boss,0),"safety gate");
  g=New(GameMode.Rhythm);for(int n=0;n<4;n++){Send(g,ActionKind.LeftSlash,10+n*20);Send(g,ActionKind.RightSlash,20+n*20);}Check(g.State==Phase.Ended&&g.CompleteGroups==4,"four groups");Check(!Send(g,ActionKind.LeftSlash,100).accepted,"terminal immutable");
  g=New(GameMode.Rhythm);Send(g,ActionKind.LeftSlash,10,"same");Check(!Send(g,ActionKind.RightSlash,11,"same").accepted,"dedup across windows");
  g=New(GameMode.Rhythm);Check(!Send(g,ActionKind.LeftSlash,1200).accepted,"close exclusive");
  g=New(GameMode.Rhythm);var old=new ActionEvent{sessionId=g.SessionId,windowId=g.WindowId,eventId="old",action=ActionKind.LeftSlash,tMs=1};Check(!g.Submit(old,252).accepted,"250ms stale");g.Pause();Check(g.State==Phase.Paused&&!g.Calibrated,"pause resets readiness");Check(!g.Start(GameMode.Rhythm,300),"cannot resume without calibration");g.Calibrated=true;g.Start(GameMode.Rhythm,300);Check(!g.Submit(old,301).accepted,"old session rejected");
  g=New(GameMode.Boss);Opening(g);Send(g,ActionKind.LeftSlash,2202);Check(g.BossHP==2,"basic counter");
  g=New(GameMode.Boss,CounterSkill.Charge);Opening(g);Check(!Send(g,ActionKind.ChargeReady,2202).accepted,"ready needs start");Send(g,ActionKind.ChargeStart,2203);Check(!Send(g,ActionKind.ChargeReady,3002).accepted,"hold 799 invalid");Check(Send(g,ActionKind.ChargeReady,3003).accepted,"hold 800 valid");Send(g,ActionKind.LeftSlash,3004);Check(!Send(g,ActionKind.DownSlash,3005).hit,"wrong slash cancels charge");
  g=New(GameMode.Boss,CounterSkill.Charge);Opening(g);Send(g,ActionKind.ChargeStart,2202);Send(g,ActionKind.ChargeReady,3002);Check(Send(g,ActionKind.DownSlash,3003).hit,"charged down hit");
  g=New(GameMode.Boss);g.Charging=true;g.Tick(1);Check(g.State==Phase.Ended&&!g.Calibrated,"charge safety");g.Charging=false;g.Connected=true;g.Tick(10000);Check(g.State==Phase.Ended,"no restored fight");
  g=New(GameMode.Boss);g.Docked=true;Check(!Send(g,ActionKind.LeftSlash,1).accepted&&g.State==Phase.Ended,"dock outranks input");
  var r=new CandidateRecognizer();for(int n=0;n<=100;n++)r.FeedCalibration(S(n,n*10,0));Check(r.Calibrated,"stationary calibration");Check(r.Feed(S(101,1010,180),false,false)==ActionKind.LeftSlash,"candidate left");Check(r.Feed(S(140,1400,180),false,false)==null&&!r.Calibrated,"gap invalidates calibration");
  r=new CandidateRecognizer();for(int n=0;n<=100;n++)r.FeedCalibration(S(n,n*10,0));Check(r.Feed(S(101,1010,180),false,false)==ActionKind.LeftSlash,"candidate left re-test");for(int n=102;n<150;n++)Check(r.Feed(S(n,n*10,180),false,false)==null,"continuous swing cannot repeat");
  r=Calibrated();for(int n=101;n<126;n++)Check(r.Feed(H(n,n*10),true,false)==null,"horizontal guard before 250ms");Check(r.Feed(H(126,1260),true,false)==ActionKind.GuardEnter,"horizontal guard 250ms");
  r=Calibrated();for(int n=101;n<140;n++)Check(r.Feed(S(n,n*10,0),true,false)==null,"up not horizontal guard");
  r=Calibrated();r.LeftHanded=true;Check(r.Feed(S(101,1010,180),false,false)==ActionKind.RightSlash,"left hand mirrors right basis");
  r=Calibrated();r.LeftHanded=true;r.HorizontalSign=-1;Check(r.Feed(S(101,1010,180),false,false)==ActionKind.LeftSlash,"basis sign and hand explicit");
  r=Ready();Check(r.Feed(M(182,1820,40),false,true)==null,"ready release pending");Check(r.Feed(M(184,1840,180),false,true)==ActionKind.DownSlash,"pending accepts down");
  r=Calibrated();Check(r.Feed(S(101,1010,0),false,true)==ActionKind.ChargeStart,"start charge");Check(r.Feed(M(102,1020,40),false,true)==ActionKind.GuardExit,"before ready exit cancels");
  r=Ready();r.Feed(M(182,1820,40),false,true);for(int n=183;n<212;n++)r.Feed(M(n,n*10,40),false,true);Check(r.Feed(M(212,2120,180),false,true)==ActionKind.GuardExit,"300ms expiry before down detection");
  r=Ready();r.Feed(M(182,1820,40),false,true);Check(r.Feed(M(183,1830,-180),false,true)==ActionKind.GuardExit,"reverse pending cancels");
  r=Ready();r.Feed(M(182,1820,40),false,true);Check(r.Feed(S(183,1830,0),false,true)==ActionKind.GuardExit,"return up cancels old ready");
  r=Ready();r.Feed(M(182,1820,40),false,true);r.ResetCandidates();Check(r.Feed(M(183,1830,40),false,true)==null,"window reset clears pending");
  bool invalid=false;try{RawCsv.Parse(RawCsv.Header+"\ns,d,1,1,NaN,1,0,0,0,0,replay");}catch(FormatException){invalid=true;}Check(invalid,"reject NaN");
 }
 static CandidateRecognizer Calibrated(){var r=new CandidateRecognizer();for(int n=0;n<=100;n++)r.FeedCalibration(S(n,n*10,0));return r;}
 static CandidateRecognizer Ready(){var r=Calibrated();for(int n=101;n<=181;n++)r.Feed(S(n,n*10,0),false,true);return r;}
 static RawSample H(long seq,long t){var s=S(seq,t,0);s.ay=0;s.az=1;return s;}
 static RawSample M(long seq,long t,float gx){var s=H(seq,t);s.gx=gx;return s;}
 static RawSample S(long seq,long t,float gz){return new RawSample{sessionId="s",deviceId="d",seq=seq,tMs=t,ay=1,gz=gz,source=InputSource.replay};}
}
}
