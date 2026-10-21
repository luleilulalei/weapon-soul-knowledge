using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using SpiritIMU;
// Drop Assets/SpiritIMU into a blank Unity project; any empty scene can enter Play.
public sealed class SpiritPrototype : MonoBehaviour {
 readonly GameSession game=new GameSession();readonly CandidateRecognizer recognizer=new CandidateRecognizer();
 GameMode selected=GameMode.Tutorial;InputSource source=InputSource.simulated;
 List<RawSample> replay;int replayIndex;long replayBase,replayFirst,lastRaw=-1,frameTime=-1,eventNo;string priorWindow;int priorTutorialStep=-1;
 string status="SIMULATION ONLY. No BLE, no rewards.";bool leftHanded,confirm,calibrating,chargingSim;long simChargeAt;string chargeWindow;
 string rawDevice,rawSession;long lastRawSeq=-1,lastRawStamp=-1;bool directionsVerified;
 bool recording;readonly List<string> recorded=new List<string>();IImuInput adapter;
 static long Now {get {return (long)(Time.realtimeSinceStartupAsDouble*1000);}}
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]static void Boot(){if(FindObjectOfType<SpiritPrototype>()==null)new GameObject("Spirit IMU Prototype").AddComponent<SpiritPrototype>();}
 void Awake(){Screen.orientation=ScreenOrientation.LandscapeLeft;Application.targetFrameRate=60;}
 void OnDestroy(){if(adapter!=null){adapter.Sample-=OnRaw;adapter.Interrupted-=OnInterrupted;adapter.Stop();}}
 // Adapter's timestamps must already be mapped into host monotonic Now milliseconds.
 // Call on main thread only. No transport implementation is bundled.
 public void AttachInput(IImuInput input){game.Interrupt("Switching to external input");StopInput();adapter=input;source=InputSource.hardware;recognizer.Reset();game.Calibrated=false;calibrating=true;adapter.Sample+=OnRaw;adapter.Interrupted+=OnInterrupted;adapter.Start();status="External raw adapter; calibration required";}
 public void UpdateDeviceState(bool connected,bool charging,bool docked,string reason){bool changed=game.Connected!=connected||game.Charging!=charging||game.Docked!=docked;game.Connected=connected;game.Charging=charging;game.Docked=docked;if(changed)OnInterrupted(reason);}
 void OnInterrupted(string why){game.Interrupt(why);recognizer.Reset();chargingSim=false;calibrating=false;status=why;}
 void StopInput(){if(recording)SaveRecording();replay=null;if(adapter!=null){adapter.Sample-=OnRaw;adapter.Interrupted-=OnInterrupted;adapter.Stop();adapter=null;}chargingSim=false;lastRaw=-1;lastRawSeq=lastRawStamp=-1;rawDevice=rawSession=null;directionsVerified=false;}
 void Update(){long now=Now;
  if(frameTime>=0&&now-frameTime>250&&game.Running){OnInterrupted("App frame gap >250ms");replay=null;}frameTime=now;
  if(replay!=null){while(replayIndex<replay.Count&&replayBase+replay[replayIndex].tMs-replayFirst<=now){var sample=replay[replayIndex++];sample.tMs=replayBase+sample.tMs-replayFirst;sample.source=InputSource.replay;OnRaw(sample);}if(replayIndex==replay.Count){replay=null;OnInterrupted("Replay ended; no continuing old fight");}}
  if(source!=InputSource.simulated&&game.Running&&(lastRaw<0||now-lastRaw>250))OnInterrupted("Raw input stale >250ms");
  game.Tick(now);
  if(priorWindow!=game.WindowId||priorTutorialStep!=game.TutorialStep){recognizer.ResetCandidates();priorWindow=game.WindowId;priorTutorialStep=game.TutorialStep;chargingSim=false;}
  if(chargingSim&&now-simChargeAt>=800){chargingSim=false;if(game.WindowId==chargeWindow)Inject(ActionKind.ChargeReady);}
#if ENABLE_LEGACY_INPUT_MANAGER
  if(Input.GetKeyDown(KeyCode.A))Inject(ActionKind.LeftSlash);if(Input.GetKeyDown(KeyCode.D))Inject(ActionKind.RightSlash);if(Input.GetKeyDown(KeyCode.S))Inject(ActionKind.DownSlash);
  if(Input.GetKeyDown(KeyCode.G))Inject(ActionKind.GuardEnter);if(Input.GetKeyDown(KeyCode.C))BeginSimCharge();if(Input.GetKeyDown(KeyCode.X))Inject(ActionKind.Cancel);if(Input.GetKeyDown(KeyCode.Space))Pause();
#endif
 }
 void OnRaw(RawSample s){long now=Now;if(rawDevice!=null&&(s.deviceId!=rawDevice||s.sessionId!=rawSession)){OnInterrupted("Raw stream changed; reattach and recalibrate");return;}if(!s.Finite||s.seq<=lastRawSeq||s.tMs<=lastRawStamp){status="Dropped invalid/duplicate/out-of-order raw sample";return;}if(s.tMs>now||now-s.tMs>250){OnInterrupted("Expired raw sample");return;}lastRaw=now;lastRawSeq=s.seq;lastRawStamp=s.tMs;rawDevice=s.deviceId;rawSession=s.sessionId;
  if(recording)recorded.Add(RawCsv.Row(s));
  if(calibrating){if(recognizer.FeedCalibration(s)){calibrating=false;game.Calibrated=true;status=recognizer.Status;}return;}
  if(!game.Running){var preview=recognizer.Feed(s,false,false);if(preview.HasValue)status="UNSCORED direction check: "+preview.Value;if(!recognizer.Calibrated)game.Calibrated=false;return;}
  if(priorWindow!=game.WindowId||priorTutorialStep!=game.TutorialStep){recognizer.ResetCandidates();priorWindow=game.WindowId;priorTutorialStep=game.TutorialStep;}
  bool guard=game.State==Phase.Attack||(game.State==Phase.Tutorial&&game.TutorialStep==2);
  bool charge=(game.State==Phase.Opening&&game.Skill==CounterSkill.Charge)||(game.State==Phase.Tutorial&&game.TutorialStep==3);
  var candidate=recognizer.Feed(s,guard,charge);if(!recognizer.Calibrated){game.Interrupt(recognizer.Status);return;}
  if(candidate.HasValue)Submit(candidate.Value,s.source,s.tMs);
 }
 void Submit(ActionKind action,InputSource origin,long t){var e=new ActionEvent{sessionId=game.SessionId,windowId=game.WindowId,eventId=(++eventNo).ToString(),tMs=t,action=action,reason="prototype",source=origin};var result=game.Submit(e,Now);status=origin+" / "+action+": "+result.reason;}
 void Inject(ActionKind action){if(action==ActionKind.Cancel||action==ActionKind.Neutral){chargingSim=false;recognizer.ResetCandidates();Submit(action,InputSource.simulated,Now);return;}if(source!=InputSource.simulated){status="Action injection disabled for raw input";return;}if(action==ActionKind.Cancel||action==ActionKind.Neutral)chargingSim=false;Submit(action,InputSource.simulated,Now);}
 void BeginSimCharge(){if(source!=InputSource.simulated)return;Inject(ActionKind.ChargeStart);simChargeAt=Now;chargeWindow=game.WindowId;chargingSim=true;}
 void Pause(){game.Pause();recognizer.Reset();chargingSim=false;calibrating=false;status="Paused. Prepare starts a NEW attempt, never resumes old input.";}
 void OnApplicationPause(bool value){if(value)OnInterrupted("App backgrounded");}
 void OnApplicationFocus(bool value){if(!value&&game.Running)OnInterrupted("App focus lost");}
 void SimPrepare(){game.Interrupt("New simulated preparation");StopInput();source=InputSource.simulated;recognizer.Reset();game.Calibrated=true;game.SafetyConfirmed=confirm;status="SIMULATED calibration; hardware calibration NOT validated";}
 void LoadReplay(){try{var asset=Resources.Load<TextAsset>("sample_raw");if(asset==null)throw new IOException("Missing Resources/sample_raw.csv");StopInput();game.Interrupt("Switching input");replay=RawCsv.Parse(asset.text);replayIndex=0;replayFirst=replay[0].tMs;replayBase=Now;source=InputSource.replay;recognizer.Reset();calibrating=true;status="Raw CSV replay calibrating. Then press Start.";}catch(Exception e){status=e.Message;}}
 void SaveRecording(){recording=false;try{string p=Path.Combine(Application.persistentDataPath,"spirit_raw_"+DateTime.UtcNow.ToString("yyyyMMdd_HHmmss")+".csv");File.WriteAllLines(p,recorded);status="Saved locally: "+p;}catch(Exception e){status="Save failed: "+e.Message;}}
 void OnGUI(){
  GUI.backgroundColor=new Color(.08f,.18f,.24f);GUI.contentColor=new Color(.95f,.86f,.65f);
  float scale=Mathf.Min(Screen.width/1280f,Screen.height/720f);GUI.matrix=Matrix4x4.TRS(Vector3.zero,Quaternion.identity,new Vector3(scale,scale,1));
  var style=new GUIStyle(GUI.skin.label){fontSize=22,wordWrap=true};var small=new GUIStyle(GUI.skin.label){fontSize=17,wordWrap=true};GUI.skin.button.fontSize=19;GUI.skin.toggle.fontSize=18;
  GUI.Box(new Rect(0,0,1280,720),"");GUI.Label(new Rect(30,18,1220,36),"SPIRIT / Single-IMU functional prototype v0.1",style);
  GUI.Label(new Rect(30,57,1220,30),"SIMULATED SCORES ONLY | No BLE / firmware / physical contact / position tracking",small);
  GUILayout.BeginArea(new Rect(30,100,330,590));
  confirm=GUILayout.Toggle(confirm,"Clear space; adult tester; no charging");game.SafetyConfirmed=confirm;
  bool lh=GUILayout.Toggle(leftHanded,"Left-handed (candidate mapping)");if(lh!=leftHanded){leftHanded=lh;recognizer.LeftHanded=lh;OnInterrupted("Hand changed; recalibrate");}
  GUILayout.Label("Mode (demo access, no unlocks)",small);selected=(GameMode)GUILayout.SelectionGrid((int)selected,new[]{"Tutorial","Rhythm","Boss"},1);
  if(!game.Running)game.Skill=(CounterSkill)GUILayout.SelectionGrid((int)game.Skill,new[]{"Basic counter","Left > Right combo","Up hold > Down"},1);
  if(GUILayout.Button("1. Simulated preparation"))SimPrepare();
  if(GUILayout.Button("2. Start NEW attempt")){if(game.Running)status="Pause or exit before a new attempt";else if(source!=InputSource.simulated&&!directionsVerified){status="Verify axis mapping and directions before Start";}else {game.Start(selected,Now);recognizer.ResetCandidates();priorWindow=game.WindowId;status=game.Feedback;}}
  if(GUILayout.Button("Load bundled raw CSV"))LoadReplay();
  if(source!=InputSource.simulated&&!game.Running){directionsVerified=GUILayout.Toggle(directionsVerified,"Directions manually verified");GUILayout.BeginHorizontal();if(GUILayout.Button("Flip L/R sign")){recognizer.HorizontalSign*=-1;directionsVerified=false;}if(GUILayout.Button("Flip down sign")){recognizer.DownSign*=-1;directionsVerified=false;}GUILayout.EndHorizontal();}
  if(GUILayout.Button("Recalibrate raw input")){game.Interrupt("Recalibrate");recognizer.Reset();directionsVerified=false;calibrating=source!=InputSource.simulated;}
  if(GUILayout.Button(recording?"Stop + save CSV locally":"Record raw CSV (explicit opt-in)")){if(recording)SaveRecording();else{recorded.Clear();recorded.Add(RawCsv.Header);recording=true;status="Recording local raw samples only; no upload";}}
  GUILayout.EndArea();
  GUI.Label(new Rect(395,105,840,55),game.State+" | "+source+" | window "+game.WindowId,style);
  string prompt=game.State==Phase.Tutorial?new[]{"1 / Left slash","2 / Right slash","3 / Horizontal blade guard pose","4 / Upward hold 800ms","5 / Cancel / return neutral","Complete"}[Math.Min(game.TutorialStep,5)]:game.State==Phase.RhythmLeft?"LEFT now":game.State==Phase.RhythmRight?"RIGHT now":game.State==Phase.Defense?"Enemy defending: WAIT":game.State==Phase.Telegraph?"Enemy preparing: WAIT for attack":game.State==Phase.Attack?"GUARD NOW":game.State==Phase.Opening?"COUNTER: "+game.Skill:game.Feedback;
  GUI.Label(new Rect(395,165,840,85),prompt,style);
  GUI.Label(new Rect(395,250,840,60),"Player "+game.PlayerHP+" / Boss "+game.BossHP+"    Rhythm "+game.CompleteGroups+" complete / "+game.Groups+" of 4",style);
  GUI.Label(new Rect(395,308,840,80),status,small);
  GUILayout.BeginArea(new Rect(395,400,840,280));GUILayout.BeginHorizontal();
  if(GUILayout.Button("A / Left",GUILayout.Height(54)))Inject(ActionKind.LeftSlash);if(GUILayout.Button("D / Right"))Inject(ActionKind.RightSlash);if(GUILayout.Button("S / Down"))Inject(ActionKind.DownSlash);GUILayout.EndHorizontal();GUILayout.BeginHorizontal();
  if(GUILayout.Button("G / Guard",GUILayout.Height(54)))Inject(ActionKind.GuardEnter);if(GUILayout.Button("C / Hold 800ms"))BeginSimCharge();if(GUILayout.Button("X / Cancel"))Inject(ActionKind.Cancel);GUILayout.EndHorizontal();GUILayout.BeginHorizontal();
  if(GUILayout.Button("Pause",GUILayout.Height(48)))Pause();if(GUILayout.Button("Exit attempt")){game.Exit();chargingSim=false;}GUILayout.EndHorizontal();GUILayout.BeginHorizontal();
  if(GUILayout.Button(game.Connected?"Disconnect":"Reconnect")){game.Connected=!game.Connected;OnInterrupted(game.Connected?"Reconnected; new preparation required":"Disconnected");}
  if(GUILayout.Button(game.Charging?"Stop charge":"Charging ON")){game.Charging=!game.Charging;OnInterrupted("Charging state changed");}
  if(GUILayout.Button(game.Docked?"Undock":"Dock")){game.Docked=!game.Docked;OnInterrupted("Dock state changed");}GUILayout.EndHorizontal();GUILayout.EndArea();
  GUI.Label(new Rect(395,684,850,30),"Upward means blade inclination, not above-head height. Touch buttons are simulation injection.",small);
 }
}
