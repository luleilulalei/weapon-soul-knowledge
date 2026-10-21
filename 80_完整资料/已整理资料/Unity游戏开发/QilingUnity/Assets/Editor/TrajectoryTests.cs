using System;
using UnityEngine;
namespace Qiling.Editor {
public static class TrajectoryTests {
public static int Run() {
Check(Motion.Left,new Vector2(.9f,.7f),new Vector2(.5f,.6f),new Vector2(.1f,.35f));
Check(Motion.Right,new Vector2(.1f,.7f),new Vector2(.5f,.6f),new Vector2(.9f,.35f));
Check(Motion.Down,new Vector2(.5f,.95f),new Vector2(.5f,.5f),new Vector2(.5f,.05f));
Check(Motion.Unknown,Vector2.zero,Vector2.zero,Vector2.zero);
Check(Motion.Unknown,Vector2.zero,Vector2.right,Vector2.zero);
Check(Motion.Unknown,Vector2.zero,Vector2.one*.5f,Vector2.one);
Check(Motion.Unknown,Vector2.zero,Vector2.up*.5f,Vector2.up);
Check(Motion.Unknown,Vector2.zero,Vector2.right);
return 8;
}
static void Check(Motion expected,params Vector2[] points) {if(SwordTrajectory.Classify(points)!=expected)throw new Exception("Trajectory classification: "+expected);}
}}
