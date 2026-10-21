using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Qiling.Editor
{
    [InitializeOnLoad]
    public static class ProjectSetup
    {
        static ProjectSetup() { EditorApplication.delayCall += EnsureScene; }
        [MenuItem("器灵/准备工程")]
        public static void EnsureScene()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) return;
            if (!File.Exists("Assets/Resources/ArenaLit.mat")) { AssetDatabase.CreateAsset(new Material(Shader.Find("Standard")), "Assets/Resources/ArenaLit.mat"); AssetDatabase.SaveAssets(); }
            if (!File.Exists("Assets/Scenes/Training.unity"))
            {
                Directory.CreateDirectory("Assets/Scenes");
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                EditorSceneManager.SaveScene(scene, "Assets/Scenes/Training.unity");
                EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene("Assets/Scenes/Training.unity", true) };
                PlayerSettings.companyName = "Qiling";
                PlayerSettings.productName = "器灵 · 训练场";
                PlayerSettings.defaultScreenWidth = 1688; PlayerSettings.defaultScreenHeight = 780;
                PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;
                PlayerSettings.allowedAutorotateToPortrait = false;
                PlayerSettings.allowedAutorotateToPortraitUpsideDown = false;
                PlayerSettings.allowedAutorotateToLandscapeLeft = true;
                PlayerSettings.allowedAutorotateToLandscapeRight = true;
                PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Android, "com.qiling.training.dev");
                PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel26;
                PlayerSettings.runInBackground = false;
                PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
                AssetDatabase.SaveAssets();
            }
        }
        [MenuItem("器灵/运行核心规则测试")]
        public static void Test()
        {
            int count = CoreTests.RunAll();
            count += TrajectoryTests.Run();
            Debug.Log("QILING_TESTS_PASSED=" + count);
        }
        [MenuItem("器灵/构建 Mac 开发版")]
        public static void BuildMac()
        {
            EnsureScene(); Test(); Directory.CreateDirectory("Builds");
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { "Assets/Scenes/Training.unity" },
                locationPathName = "Builds/Qiling Training.app", target = BuildTarget.StandaloneOSX,
                options = BuildOptions.Development
            });
            if (report.summary.result != BuildResult.Succeeded) throw new Exception("Mac build failed: " + report.summary.result);
        }
        [MenuItem("器灵/构建 Android 开发版")]
        public static void BuildAndroid()
        {
            EnsureScene(); Test(); Directory.CreateDirectory("Builds");
            PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64 | AndroidArchitecture.ARMv7;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel34;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel26;
            PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Android, "com.qiling.training.dev");
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;
            PlayerSettings.Android.useCustomKeystore = false;
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { "Assets/Scenes/Training.unity" }, locationPathName = "Builds/Qiling-Development.apk",
                target = BuildTarget.Android, options = BuildOptions.Development
            });
            if (report.summary.result != BuildResult.Succeeded) throw new Exception("Android build failed: " + report.summary.result);
        }
    }
}
