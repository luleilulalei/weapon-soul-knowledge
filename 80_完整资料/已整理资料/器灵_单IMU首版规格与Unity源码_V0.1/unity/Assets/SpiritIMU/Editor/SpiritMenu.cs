#if UNITY_EDITOR
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using System.Collections.Generic;
public static class SpiritMenu {
 [MenuItem("Spirit IMU/Create demo scene")]
 public static void CreateScene(){if(!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())return;var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);new GameObject("Spirit Prototype").AddComponent<SpiritPrototype>();EditorSceneManager.SaveScene(scene,"Assets/SpiritIMU/SpiritDemo.unity");var entries=new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);if(!entries.Exists(x=>x.path==scene.path))entries.Add(new EditorBuildSettingsScene(scene.path,true));EditorBuildSettings.scenes=entries.ToArray();PlayerSettings.defaultInterfaceOrientation=UIOrientation.LandscapeLeft;PlayerSettings.defaultScreenWidth=1280;PlayerSettings.defaultScreenHeight=720;}
 [MenuItem("Spirit IMU/Run core self tests")]
 public static void Tests(){SpiritIMU.CoreSelfTest.Run();Debug.Log("Spirit IMU core self-tests passed (C# execution in this editor).");}
}
#endif
