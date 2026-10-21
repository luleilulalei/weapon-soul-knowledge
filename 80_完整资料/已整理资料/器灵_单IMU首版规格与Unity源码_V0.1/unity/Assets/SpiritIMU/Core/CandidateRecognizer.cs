using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
namespace SpiritIMU {
// EXPERIMENTAL candidate detector, not a validated gesture classifier.
// Sensor axes must be mapped to blade coordinates by the adapter: +Y toward tip,
// +X player right at neutral, +Z toward player. Acceleration is in g; gyro deg/s.
public sealed class CandidateRecognizer {
 public bool Calibrated {get; private set;} public bool LeftHanded;
 // Set only by explicit direction demonstration; never infer world yaw from gravity.
 public float HorizontalSign=1, DownSign=1;
 public string Status="Need 1 second of stationary samples";
 long stillSince=-1,lastT=-1,lastSeq=-1,lastAction=-10000,poseSince=-1,releaseSince=-1;int stillCount;double bx,by,bz;float biasX,biasY,biasZ;bool poseSent,chargeSent,slashArmed=true;string lastDevice,lastSession;
 public void Reset(){Calibrated=false;stillSince=lastT=lastSeq=poseSince=releaseSince=-1;lastAction=-10000;stillCount=0;bx=by=bz=0;poseSent=chargeSent=false;slashArmed=true;lastDevice=lastSession=null;Status="Need calibration";}
 public void ResetCandidates(){poseSince=releaseSince=-1;poseSent=chargeSent=false;lastAction=-10000;}
 public bool FeedCalibration(RawSample s) {
  if(!Validate(s))return false;
  double a=Math.Sqrt(s.ax*s.ax+s.ay*s.ay+s.az*s.az),g=Math.Sqrt(s.gx*s.gx+s.gy*s.gy+s.gz*s.gz);
  if(Math.Abs(a-1)>.12||g>=12){stillSince=-1;stillCount=0;bx=by=bz=0;Status="Move less; restart stationary calibration";return false;}
  if(stillSince<0)stillSince=s.tMs;stillCount++;bx+=s.gx;by+=s.gy;bz+=s.gz;
  if(s.tMs-stillSince>=1000&&stillCount>=20){biasX=(float)(bx/stillCount);biasY=(float)(by/stillCount);biasZ=(float)(bz/stillCount);Calibrated=true;Status="Bias calibrated; manually verify left/right/down directions";}
  return Calibrated;
 }
 bool Validate(RawSample s){if(!s.Finite||s.tMs<0||s.seq<0){Status="Non-finite/invalid sample";return false;}if(lastDevice!=null&&(s.deviceId!=lastDevice||s.sessionId!=lastSession)){Reset();Status="Stream changed; recalibrate";return false;}if(s.seq<=lastSeq||s.tMs<=lastT){Status="Duplicate/out-of-order sample";return false;}if(lastT>=0&&s.tMs-lastT>250){Reset();Status="Sample gap; recalibrate";return false;}lastT=s.tMs;lastSeq=s.seq;lastDevice=s.deviceId;lastSession=s.sessionId;return true;}
 public ActionKind? Feed(RawSample s,bool guardWindow,bool chargeWindow){
  if(!Calibrated||!Validate(s))return null;
  float gx=s.gx-biasX,gy=s.gy-biasY,gz=s.gz-biasZ;double a=Math.Sqrt(s.ax*s.ax+s.ay*s.ay+s.az*s.az);double g=Math.Sqrt(gx*gx+gy*gy+gz*gz);
  bool up=Math.Abs(a-1)<.12&&g<12&&s.ay/a>.85;
  bool horizontal=Math.Abs(a-1)<.12&&g<12&&Math.Abs(s.ay/a)<.3;
  // Ready-only bounded release transition. No extra charge accumulates here.
  if(chargeSent&&chargeWindow&&!up&&releaseSince<0){releaseSince=s.tMs;Status="Release pending: down within 300ms";}
  if(releaseSince>=0&&(!chargeWindow||s.tMs-releaseSince>=300||up||gx*DownSign < -120)){ResetPose();return ActionKind.GuardExit;}
  // Axis/sign values are demonstration-configured. Left-handed is explicit, never auto-detected.
  if(g<12)slashArmed=true;
  if(slashArmed&&s.tMs-lastAction>=300){
   if(gx*DownSign>120&&Math.Abs(gx)>1.4*Math.Abs(gz)&&Math.Abs(gx)>1.4*Math.Abs(gy)){lastAction=s.tMs;slashArmed=false;ResetPose();return ActionKind.DownSlash;}
   if(Math.Abs(gz)>120&&Math.Abs(gz)>1.4*Math.Abs(gx)&&Math.Abs(gz)>1.4*Math.Abs(gy)){lastAction=s.tMs;slashArmed=false;ResetPose();return gz*HorizontalSign*(LeftHanded?-1:1)>0?ActionKind.LeftSlash:ActionKind.RightSlash;}
  }
  if(releaseSince>=0)return null; // Waiting for down slash, wrong slash or expiry; never re-charge.
  if((up&&chargeWindow)||(horizontal&&guardWindow)){
   if(poseSince<0){poseSince=s.tMs;poseSent=chargeSent=false;}
   if(chargeWindow&&!poseSent){poseSent=true;return ActionKind.ChargeStart;}
   if(chargeWindow&&!chargeSent&&s.tMs-poseSince>=800){chargeSent=true;return ActionKind.ChargeReady;}
   if(guardWindow&&!poseSent&&s.tMs-poseSince>=250){poseSent=true;return ActionKind.GuardEnter;}
  }else {bool had=poseSent||chargeSent;ResetPose();if(had)return ActionKind.GuardExit;}
  return null;
 }
 void ResetPose(){poseSince=releaseSince=-1;poseSent=chargeSent=false;}
}
public static class RawCsv {
 public const string Header="sessionId,deviceId,seq,tMs,ax,ay,az,gx,gy,gz,source";
 public static List<RawSample> Parse(string text){
  var rows=new List<RawSample>();using(var reader=new StringReader(text)){if(reader.ReadLine()!=Header)throw new FormatException("CSV header mismatch");string line;long previous=-1,seq=-1;string device=null,session=null;
   while((line=reader.ReadLine())!=null){if(string.IsNullOrWhiteSpace(line))continue;var c=line.Split(',');if(c.Length!=11)throw new FormatException("CSV needs 11 columns");
    var s=new RawSample{sessionId=c[0],deviceId=c[1],seq=long.Parse(c[2],CultureInfo.InvariantCulture),tMs=long.Parse(c[3],CultureInfo.InvariantCulture),ax=F(c[4]),ay=F(c[5]),az=F(c[6]),gx=F(c[7]),gy=F(c[8]),gz=F(c[9]),source=(InputSource)Enum.Parse(typeof(InputSource),c[10],false)};
    if(!s.Finite||s.tMs<0||s.seq<0||s.tMs<=previous||s.seq<=seq||!Enum.IsDefined(typeof(InputSource),s.source))throw new FormatException("Invalid sample or non-monotonic timestamp/seq");
    if(device!=null&&(device!=s.deviceId||session!=s.sessionId))throw new FormatException("One stream per CSV");device=s.deviceId;session=s.sessionId;previous=s.tMs;seq=s.seq;rows.Add(s);
   }
  }if(rows.Count==0)throw new FormatException("Empty recording");return rows;
 }
 static float F(string s){return float.Parse(s,CultureInfo.InvariantCulture);}
 public static string Row(RawSample s){return string.Join(",",new[]{s.sessionId,s.deviceId,s.seq.ToString(CultureInfo.InvariantCulture),s.tMs.ToString(CultureInfo.InvariantCulture),s.ax.ToString("R",CultureInfo.InvariantCulture),s.ay.ToString("R",CultureInfo.InvariantCulture),s.az.ToString("R",CultureInfo.InvariantCulture),s.gx.ToString("R",CultureInfo.InvariantCulture),s.gy.ToString("R",CultureInfo.InvariantCulture),s.gz.ToString("R",CultureInfo.InvariantCulture),s.source.ToString()});}
}
}
