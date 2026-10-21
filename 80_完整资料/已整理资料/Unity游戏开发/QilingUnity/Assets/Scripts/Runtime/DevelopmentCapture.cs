#if UNITY_EDITOR || DEVELOPMENT_BUILD
using System;
using System.Collections;
using System.IO;
using UnityEngine;

namespace Qiling
{
    // Explicit opt-in rendering check. Drives the same public state machine as user input.
    public sealed class DevelopmentCapture : MonoBehaviour
    {
        TrainingSession session;
        string directory;
        long sequence = 100000;
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            var args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, "--qiling-capture");
            if (index >= 0 && index + 1 < args.Length)
            {
                var capture = new GameObject("Development visual check").AddComponent<DevelopmentCapture>();
                capture.directory = args[index + 1]; capture.StartCoroutine(capture.Run());
            }
        }
        void Advance(float delta)
        {
            session.Device.ObservedAt = Time.realtimeSinceStartupAsDouble;
            session.Tick(delta, Time.realtimeSinceStartupAsDouble);
        }
        void Send(Motion motion) => session.Submit(motion, ++sequence, session.Window, Time.realtimeSinceStartupAsDouble);
        void Begin(TrainingMode mode)
        {
            session.Select(mode); session.SpaceConfirmed = session.PhonePlaced = true; session.StartPreparation();
            Advance(8.1f); Advance(3.1f); Send(Motion.Left); Advance(3.1f);
        }
        IEnumerator Shot(string name)
        {
            yield return null; yield return new WaitForEndOfFrame();
            ScreenCapture.CaptureScreenshot(Path.Combine(directory, name + ".png"));
            yield return new WaitForSecondsRealtime(.5f);
        }
        IEnumerator Run()
        {
            Directory.CreateDirectory(directory);
            yield return new WaitForSecondsRealtime(1);
            session = FindObjectOfType<TrainingGame>().Session;
            yield return Shot("01-lobby");
            session.Select(TrainingMode.Discern); yield return Shot("02-prepare");
            session.SpaceConfirmed = session.PhonePlaced = true; session.StartPreparation(); yield return Shot("03-countdown");
            Advance(8.1f); Advance(3.1f); Send(Motion.Left); Advance(3.1f); yield return Shot("04-direction");
            var trajectory=FindObjectOfType<TrainingGame>().Trajectory;
            var before=trajectory.Tip; trajectory.Play(session.Expected);
            yield return new WaitForSecondsRealtime(.22f);
            if(Vector3.Distance(before,trajectory.Tip)<.1f)throw new Exception("Sword did not move");
            yield return Shot("04b-moving-blade");
            if(session.Successes!=1)throw new Exception("Trajectory did not reach judge");
            Debug.Log("QILING_TRAJECTORY_INTEGRATION_PASSED");
            Advance(1.3f);
            for (int i = 1; i < 6; i++) { Send(session.Expected); if (i < 5) Advance(1.3f); }
            yield return Shot("05-result");
            Begin(TrainingMode.Rhythm);
            for (int i = 0; i < 4; i++) { Send(Motion.Left); Send(Motion.Right); if (i < 3) Advance(1.3f); }
            session.Select(TrainingMode.Guardian); session.SelectSkill(Skill.Charge);
            session.SpaceConfirmed = session.PhonePlaced = true; session.StartPreparation();
            Advance(8.1f); Advance(3.1f); Send(Motion.Left); Advance(3.1f);
            Advance(2.1f); trajectory.BeginHold(Motion.Block);
            yield return new WaitForSecondsRealtime(.35f); trajectory.EndHold();
            if(session.State!=Phase.ChargeWait)throw new Exception("Hold guard failed");
            trajectory.BeginHold(Motion.Raise); yield return new WaitForSecondsRealtime(.35f);
            if(session.State!=Phase.Charging)throw new Exception("Hold charge failed");
            yield return Shot("06-charge");
            Advance(2.1f); yield return Shot("07-release");
            trajectory.EndHold(); trajectory.Play(Motion.Down);
            yield return new WaitForSecondsRealtime(.6f);
            if(session.EnemyHealth!=2)throw new Exception("Charge trajectory hit failed");
            Debug.Log("QILING_GUARD_CHARGE_RELEASE_PASSED");
            session.Pause(); yield return Shot("08-pause");
            Debug.Log("QILING_CAPTURE_COMPLETE=" + directory);
            Application.Quit();
        }
    }
}
#endif
