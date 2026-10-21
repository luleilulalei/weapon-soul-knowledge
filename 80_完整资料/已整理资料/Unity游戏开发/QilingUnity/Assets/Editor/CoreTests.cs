using System;
using System.Collections.Generic;
using Qiling;

// No Unity dependency: the exact production state machine can also be tested with a C# console compiler.
public static class CoreTests
{
    static int assertions;
    static double clock;
    static long id;
    static void Check(bool pass, string label) { assertions++; if (!pass) throw new Exception("FAILED: " + label); }
    static TrainingSession Fresh()
    {
        clock = 0; id = 0; var s = new TrainingSession();
        s.Device.Connected = s.Device.Authorized = s.Device.SwordVerified = true;
        s.Device.ObservedAt = clock; s.Tick(0, clock); return s;
    }
    static void Wait(TrainingSession s, float seconds)
    {
        // Step clocks as a live heartbeat would; never jump past an entire input window.
        int frames = Math.Max(1, (int)Math.Ceiling(seconds * 60));
        for (int i = 0; i < frames; i++) { clock += (double)seconds / frames; s.Device.ObservedAt = clock; s.Tick(seconds / frames, clock); }
    }
    static void Send(TrainingSession s, Motion m) { s.Submit(m, ++id, s.Window, clock); }
    static void Begin(TrainingSession s, TrainingMode mode, Skill skill = Skill.Single)
    {
        s.Select(mode); s.SelectSkill(skill); s.SpaceConfirmed = s.PhonePlaced = true; s.StartPreparation();
        Wait(s, 8.05f); Wait(s, 3.05f); Check(s.State == Phase.Calibrate, "calibration required");
        Send(s, Motion.Left); Wait(s, 3.05f); Check(s.IsCombat, "selected level begins");
    }
    static void WinDirection(TrainingSession s)
    {
        Begin(s, TrainingMode.Discern);
        for (int i=0;i<6;i++) { Send(s, s.Expected); if (i<5) Wait(s, 1.25f); }
        Check(s.Result == Outcome.Won && s.Successes == 6, "discern win computed");
    }
    static void WinRhythm(TrainingSession s)
    {
        Begin(s, TrainingMode.Rhythm);
        for (int i=0;i<4;i++) { Send(s, Motion.Left); Send(s, Motion.Right); if(i<3) Wait(s, 1.25f); }
        Check(s.Result == Outcome.Won && s.Successes == 4, "rhythm win computed");
    }
    static TrainingSession Guardian(Skill skill)
    {
        var s=Fresh(); WinDirection(s); WinRhythm(s); Begin(s, TrainingMode.Guardian, skill); return s;
    }
    public static int RunAll()
    {
        assertions=0;
        var s=Fresh();
        Check(!s.IsUnlocked(TrainingMode.Guardian), "guardian starts locked");
        s.Select(TrainingMode.Guardian); Check(s.State==Phase.Lobby, "locked route rejected");
        s.Select(TrainingMode.Discern); s.StartPreparation(); Check(s.State==Phase.Prepare, "manual placement required");
        s.SpaceConfirmed=s.PhonePlaced=true; s.Device.Charging=true; s.StartPreparation(); Check(s.State==Phase.Prepare,"charging gate");
        s.Device.Charging=false; s.Device.Authorized=false; s.StartPreparation(); Check(s.State==Phase.Prepare,"authorization gate");
        s.Device.Authorized=true; clock=4; s.Tick(0,clock); s.StartPreparation(); Check(s.State==Phase.Prepare,"freshness gate");
        s=Fresh(); s.Select(TrainingMode.Discern);s.SpaceConfirmed=s.PhonePlaced=true;s.StartPreparation();Wait(s,8.05f);Wait(s,3.05f);
        Send(s,Motion.Unknown); Check(s.State==Phase.Correction && s.Successes==0,"unknown calibration not success");
        s.StartPreparation();Check(s.State==Phase.Countdown,"retry returns to stand back");
        s=Fresh();Begin(s,TrainingMode.Discern);
        Send(s,Motion.Right); Wait(s,1.25f);Send(s,Motion.Left);Wait(s,1.25f);
        Check(s.Completed==2 && s.Result==Outcome.None,"two misses do not end six prompts");
        for(int i=2;i<6;i++){Send(s,s.Expected);if(i<5)Wait(s,1.25f);}
        Check(s.Result==Outcome.Won && s.Successes==4,"four of six passes");
        Check(s.PracticeProgress==1 && s.IsUnlocked(TrainingMode.Rhythm),"practice progression");
        Begin(s,TrainingMode.Rhythm); Send(s,Motion.Left);s.Pause();
        Check(s.State==Phase.Paused && s.Completed==0,"pause drops incomplete combo");
        s.Resume();Wait(s,8.05f);Wait(s,3.05f);Send(s,Motion.Left);Wait(s,3.05f);
        Check(s.State==Phase.ComboFirst && s.Mode==TrainingMode.Rhythm,"resume validates and restarts combo");
        Send(s,Motion.Right);Check(s.Completed==1 && s.Successes==0,"wrong order fails full group");
        Wait(s,1.25f);Send(s,Motion.Left);Wait(s,3.1f);Check(s.Completed==2 && s.Successes==0,"second stage timeout");
        s=Fresh();WinDirection(s);WinRhythm(s);Check(s.FirstUnlock && s.ChargeUnlocked,"first charge unlock");
        WinRhythm(s);Check(!s.FirstUnlock && s.ChargeUnlocked,"repeat grants no new skill");
        foreach(Skill skill in new[]{Skill.Single,Skill.Combo,Skill.Charge})
        {
            s=Guardian(skill);
            Send(s,Motion.Left); Check(s.EnemyHealth==3,"defense phase immune");
            for(int i=0;i<3;i++)
            {
                Wait(s,2.05f);Send(s,Motion.Block);
                if(skill==Skill.Single)Send(s,Motion.Left);
                if(skill==Skill.Combo){Send(s,Motion.Left);Check(s.EnemyHealth==3-i,"combo first has no damage");Send(s,Motion.Right);}
                if(skill==Skill.Charge){Send(s,Motion.Raise);Wait(s,2.05f);Check(s.State==Phase.Release,"charge ready");Send(s,Motion.Down);}
                Check(s.EnemyHealth==2-i,"one hit per successful counter");
                if(i<2)Wait(s,1.25f);
            }
            Check(s.Result==Outcome.Won,"three guardian tracks win");
            s.Exit();Check(s.Result==Outcome.Won,"terminal outcome immutable");
        }
        s=Guardian(Skill.Single);Wait(s,2.05f);Send(s,Motion.Block);
        int window=s.Window;long sameId=++id;s.Submit(Motion.Left,sameId,window,clock);s.Submit(Motion.Left,sameId,window,clock);
        Check(s.EnemyHealth==2,"duplicate event cannot duplicate damage");
        s.Pause();s.Resume();Wait(s,8.05f);Wait(s,3.05f);Send(s,Motion.Left);Wait(s,3.05f);
        Check(s.EnemyHealth==2 && s.State==Phase.Telegraph,"confirmed health survives pause");
        s.Submit(Motion.Left,++id,window,clock);Check(s.EnemyHealth==2,"old window rejected");
        s=Guardian(Skill.Charge);Wait(s,2.05f);Send(s,Motion.Block);Send(s,Motion.Raise);Send(s,Motion.Down);
        Check(s.State==Phase.Feedback && s.EnemyHealth==3,"early release cancels without fallback damage");
        Wait(s,1.25f);Wait(s,2.05f);Send(s,Motion.Block);Send(s,Motion.Raise);Wait(s,2.05f);Wait(s,3.05f);
        Check(s.State==Phase.Feedback && s.EnemyHealth==3,"release timeout cancels");
        s=Guardian(Skill.Single);
        for(int i=0;i<3;i++){Wait(s,2.05f);Wait(s,3.05f);if(i<2)Wait(s,1.25f);}
        Check(s.Result==Outcome.Lost && s.PlayerHealth==0,"missed blocks lose exactly three health");
        s=Guardian(Skill.Charge);Wait(s,2.05f);Send(s,Motion.Block);Send(s,Motion.Raise);s.Pause();s.Resume();Wait(s,8.05f);Wait(s,3.05f);Send(s,Motion.Left);Wait(s,3.05f);
        Check(s.State==Phase.Telegraph && s.EnemyHealth==3,"paused charge does not survive");
        s.Device.Connected=false;Wait(s,.01f);Check(s.State==Phase.Reconcile,"disconnect stops gameplay");
        Send(s,Motion.Left);Check(s.EnemyHealth==3,"no disconnected damage");
        s.Device.Connected=true;Wait(s,.01f);Check(s.State==Phase.Reconcile,"connection alone not terminal evidence");
        s.ResolveInterrupted("wrong-session");Check(s.State==Phase.Reconcile,"terminal evidence matches session");
        s.ResolveInterrupted(s.SessionId);Check(s.Result==Outcome.Interrupted,"explicit interruption evidence");
        s=Guardian(Skill.Single);s.Device.Docked=true;Wait(s,.01f);Check(s.Result==Outcome.Exited,"docking exits");
        s.Device.Docked=false;Wait(s,.1f);Check(s.State==Phase.Result,"undocking does not resume");
        s=Guardian(Skill.Single);s.Device.Risk=true;Wait(s,.01f);Check(s.State==Phase.Reconcile,"risk preempts");
        s=Guardian(Skill.Single);s.Interrupt();Check(s.State==Phase.Reconcile,"background interrupts");
        return assertions;
    }
#if QILING_CONSOLE_TESTS
    public static void Main() { Console.WriteLine("QILING_TESTS_PASSED="+RunAll()); }
#endif
}
