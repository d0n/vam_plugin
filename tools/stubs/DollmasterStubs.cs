// Compile-only stubs: the VaM / Unity API the ported Dollmaster uses (src/AIBody/Dm*.cs). NOT shipped.
// Evidence E39 (docs/API_AUDIT.md): Don's copy of Dollmaster (VAMDeluxe, 2019; upstream github.com/vamdeluxe/DeluxePlugin,
// MIT), which runs in Don's VaM 1.22 as it is. Each member names the Dollmaster file and line it is used at (original
// file names). FileManagerSecure.GetFiles(dir, pattern) / GetDirectories: E39b (everlasterVR/LiveReload src/FileSearch.cs
// L34, L44): the port reads files only through FileManagerSecure instead of SuperController.GetFilesAtPath /
// GetDirectoriesAtPath / ReadFileIntoString.
#pragma warning disable 0067, 0649, 0169, 1591
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace UnityEngine
{
public partial class Object   // E39 (Instantiate: UI.cs L63)
    {
        public static T Instantiate<T>(T original) where T : Object { return null; }   // E39 UI.cs L63
    }
public partial class Component   // E39 (GetComponent: UI.cs L67, L124)
    {
        public T GetComponent<T>() { return default(T); }   // E39 DressController.cs L109
        public T GetComponentInChildren<T>() { return default(T); }   // E39 Arousal.cs L45
        public T[] GetComponents<T>() { return null; }   // E39 DressController.cs L107
    }
    public partial class GameObject   // E39 HeadController.cs L34
    {
        public GameObject() { }   // E39 HeadController.cs L34
        public bool activeSelf { get { return false; } }   // E39 TopButtons.cs L67
        public void SetActive(bool on) { }   // E39 ClimaxController.cs L59
        public Transform transform { get { return null; } }   // E39 Dollmaster.cs L65
        public T GetComponent<T>() { return default(T); }   // E39 DressController.cs L109
        public GameObject gameObject { get { return this; } }   // E39 ClimaxController.cs L59
    }
    public partial class Transform   // E39 KissController.cs L26
    {
        public Vector3 localPosition { get; set; }   // E39 PoseController.cs L12
        public Vector3 localScale { get; set; }   // E39 UI.cs L42
        public Vector3 localEulerAngles { get; set; }   // E39 UI.cs L243
        public Quaternion localRotation { get; set; }   // E39 PoseController.cs L13
        public Vector3 forward { get { return new Vector3(); } }   // E39 KissController.cs L121
        public Vector3 up { get { return new Vector3(); } }   // E39 HeadController.cs L131
        public int childCount { get { return 0; } }   // E39 TopButtons.cs L62
        public Transform GetChild(int i) { return null; }   // E39 TopButtons.cs L64
        public void SetParent(Transform p, bool worldPositionStays) { }   // E39 UI.cs L34
        public void SetParent(Transform p) { }   // E39 UI.cs L34
        public void Translate(float x, float y, float z, Space s) { }   // E39 Dollmaster.cs L65
        public void Translate(Vector3 v, Space s) { }   // E39 Dollmaster.cs L65
        public void Translate(float x, float y, float z) { }   // E39 Dollmaster.cs L65
        public void LookAt(Vector3 p, Vector3 up) { }   // E39 UI.cs L239
        public void LookAt(Vector3 p) { }   // E39 UI.cs L239
        public void SetPositionAndRotation(Vector3 p, Quaternion r) { }   // E39 SFXController.cs L32
    }
    public partial class RectTransform : Transform   // E39 UI.cs L124
    {
        public enum Axis { Horizontal, Vertical }   // E39 UI.cs L126
        public Vector2 anchoredPosition { get; set; }   // E39 UI.cs L125
        public void SetSizeWithCurrentAnchors(Axis axis, float size) { }   // E39 UI.cs L126
    }
    public enum Space { World, Self }   // E39 HeadController.cs L66
    public enum RenderMode { ScreenSpaceOverlay, ScreenSpaceCamera, WorldSpace }   // E39 UI.cs L30
    public enum HorizontalWrapMode { Wrap, Overflow }   // E39 UI.cs L141
    public enum FontStyle { Normal, Bold, Italic, BoldAndItalic }   // E39 UI.cs L160
    public partial class Font : Object { }   // E39 UI.cs L130
    public static partial class Resources { public static Object GetBuiltinResource(Type t, string path) { return null; } }   // E39 UI.cs L130
    public partial struct Vector2 { public float x, y; public Vector2(float x, float y) { this.x = x; this.y = y; } }   // E39 UI.cs L125
    public partial class Canvas : Behaviour { public RenderMode renderMode; public bool pixelPerfect; }   // E39 UI.cs L13
    public partial class Rigidbody : Component { }   // E39 SFXController.cs L39
public partial class Coroutine { }   // E39 (return type of StartCoroutine, Dollmaster: dm.StartCoroutine SFXController.cs L27)
public partial class YieldInstruction { }   // E39 (base of WaitForSeconds, BaseModule.cs L35)
    public partial class WaitForSeconds : YieldInstruction { public WaitForSeconds(float s) { } }   // E39 BaseModule.cs L35
public partial class MonoBehaviour { public Coroutine StartCoroutine(IEnumerator routine) { return null; } }   // E39 SFXController.cs L27, ThrustController.cs L226
    public static partial class Debug   // E39 Expressions.cs L29
    {
        public static void Log(object m) { }   // E39 Expressions.cs L29
        public static void LogWarning(object m) { }   // E39 Personality.cs L39
        public static void LogError(object m) { }   // E39 Dollmaster.cs L49
    }
}

namespace UnityEngine
{
    public partial struct Color   // E39 Arousal.cs L37
    {
        public static Color green { get { return new Color(); } }   // E39 Arousal.cs L37
        public static Color white { get { return new Color(); } }   // E39 TopButtons.cs L54
        public static Color black { get { return new Color(); } }   // E39 TopButtons.cs L54
    }
    public partial struct Vector3   // E39 HeadController.cs L30
    {
        public static Vector3 down { get { return new Vector3(); } }   // E39 HeadController.cs L89
        public static Vector3 one { get { return new Vector3(); } }   // E39 Montage.cs L76
        public static Vector3 Lerp(Vector3 a, Vector3 b, float t) { return a; }   // E39 HeadController.cs L132
        public static float Dot(Vector3 a, Vector3 b) { return 0f; }   // E39 HeadController.cs L133
        public static Vector3 Normalize(Vector3 v) { return v; }   // E39 HeadController.cs L130
        public static Vector3 operator -(Vector3 a) { return a; }   // E39 Dollmaster.cs L49
        public static Vector3 operator *(float d, Vector3 a) { return a; }   // E39 Dollmaster.cs L49
        public static Vector3 operator /(Vector3 a, float d) { return a; }   // E39 Dollmaster.cs L49
    }
    public partial struct Quaternion   // E39 HeadController.cs L137
    {
        public Vector3 eulerAngles { get; set; }   // E39 PoseController.cs L73
        public static Quaternion LookRotation(Vector3 forward, Vector3 up) { return new Quaternion(); }   // E39 HeadController.cs L137
        public static Quaternion LookRotation(Vector3 forward) { return new Quaternion(); }   // E39 HeadController.cs L137
        public static Quaternion RotateTowards(Quaternion a, Quaternion b, float d) { return a; }   // E39 HeadController.cs L138
        public static Quaternion Lerp(Quaternion a, Quaternion b, float t) { return a; }   // E39 HeadController.cs L132
    }
    public static partial class Mathf   // E39 Arousal.cs L84
    {
        public static float Clamp(float v, float min, float max) { return v; }   // E39 Arousal.cs L94
        public static float Lerp(float a, float b, float t) { return a; }   // E39 HeadController.cs L132
    }
    public static partial class Random   // E39 ClimaxController.cs L89
    {
        public static int Range(int a, int b) { return a; }   // E39 ClimaxController.cs L89
        public static Vector3 insideUnitSphere { get { return new Vector3(); } }   // E39 HeadController.cs L103
        public static float value { get { return 0f; } }   // E39 Arousal.cs L114
    }
}

namespace UnityEngine.XR
{
    public static class XRSettings { public static bool enabled { get { return false; } } }   // E39 UI.cs L235
}

namespace UnityEngine.UI
{
public partial class Graphic : Behaviour { public Color color { get; set; } }   // E39 (Image.color: Arousal.cs L46; InputField.targetGraphic: UI.cs)
public partial class MaskableGraphic : Graphic { }   // E39 (Unity UI base of Image / Text)
    public partial class Image : MaskableGraphic { }   // E39 Arousal.cs L27
    public partial class Text   // E39 UI.cs L133
    {
        public Font font { get; set; }   // E39 UI.cs L138
        public int fontSize { get; set; }   // E39 ClimaxController.cs L60
        public FontStyle fontStyle { get; set; }   // E39 UI.cs L160
        public bool supportRichText { get; set; }   // E39 UI.cs L140
        public HorizontalWrapMode horizontalOverflow { get; set; }   // E39 UI.cs L141
    }
    public partial class InputField   // E39 UI.cs L112
    {
        public Graphic targetGraphic { get; set; }   // E39 UI.cs L167
        public Graphic placeholder { get; set; }   // E39 UI.cs L169
        public int characterLimit { get; set; }   // E39 UI.cs L170
    }
    public partial class Selectable : Behaviour { }   // E39 (Unity UI base of Button / Slider / Toggle)
public partial class SliderEvent : UnityEngine.Events.UnityEvent<float> { }   // E39 (slider.onValueChanged.AddListener: ThrustController.cs L77)
    public partial class Slider : Selectable   // E39 ThrustController.cs L16
    {
        public float value { get; set; }   // E39 Arousal.cs L114
        public float maxValue { get; set; }   // E39 SFXController.cs L114
        public SliderEvent onValueChanged { get { return null; } }   // E39 ThrustController.cs L77
    }
public partial class Toggle : Selectable { public bool isOn { get; set; } }   // E39 (editModeToggle.isOn: TopButtons.cs L21)
    public partial class ScrollRect : Behaviour { public RectTransform viewport { get; set; } public float elasticity { get; set; } }   // E39 UI.cs L21
    public partial class Mask : Behaviour { }   // E39 UI.cs L190
    public partial class CanvasScaler : Behaviour { public float scaleFactor { get; set; } public float dynamicPixelsPerUnit { get; set; } }   // E39 UI.cs L36
    public partial class GraphicRaycaster : Behaviour { }   // E39 UI.cs L40
    public partial class ContentSizeFitter : Behaviour   // E39 UI.cs L204
    {
        public enum FitMode { Unconstrained, MinSize, PreferredSize }   // E39 UI.cs L205
        public FitMode horizontalFit { get; set; }   // E39 UI.cs L205
    }
    public partial class VerticalLayoutGroup : Behaviour   // E39 UI.cs L198
    {
        public bool childControlWidth { get; set; }   // E39 UI.cs L208
        public bool childForceExpandHeight { get; set; }   // E39 UI.cs L209
        public bool childForceExpandWidth { get; set; }   // E39 UI.cs L210
    }
}

namespace UnityEngine.Events
{
    public delegate void UnityAction<T0>(T0 arg0);   // E39 TopButtons.cs L82
public partial class UnityEvent<T0> { public void AddListener(UnityAction<T0> a) { } }   // E39 ThrustController.cs L77
}

public partial class SuperController   // E39 BaseModule.cs L38
{
    public enum ActiveUI { None, MainMenu, MainMenuOnly, EmbeddedScenePanel, OnlineBrowser, SelectedOptions, PackageBuilder, MultiButtonPanel, Custom }   // E39 UI.cs L251
    public ActiveUI activeUI { get; set; }   // E39 UI.cs L251
    public uFileBrowser.FileBrowser fileBrowserUI;   // E39 TopButtons.cs L36
    public uFileBrowser.FileBrowser directoryBrowserUI;   // E39 MontageController.cs L34
    public Transform mainHUD;   // E39 UI.cs L34
    public Camera lookCamera;   // E39 UI.cs L237
    public UnityEngine.UI.Toggle editModeToggle;   // E39 TopButtons.cs L21
    public string currentLoadDir;   // E39 Dollmaster.cs L58
    public string currentSaveDir;   // E39 Dollmaster.cs L285
    public string savesDir;   // E39 MontageController.cs L34
    public Atom GetAtomByUid(string uid) { return null; }   // E39 BaseModule.cs L38
    public IEnumerator AddAtomByType(string type, string id, bool userInvoked = false, bool forceSelect = false, bool forceFocus = false) { yield break; }   // E39 BaseModule.cs L41
    public void RemoveAtom(Atom a) { }   // E39 BaseModule.cs L78
    public Rigidbody RigidbodyNameToRigidbody(string n) { return null; }   // E39 SFXController.cs L39
    public void AddCanvas(Canvas c) { }   // E39 UI.cs L32
    public void RemoveCanvas(Canvas c) { }   // E39 UI.cs L273
    public void ShowMainHUDAuto() { }   // E39 TopButtons.cs L22
    public void ClearSelection() { }   // E39 TopButtons.cs L23
    public void SelectController(FreeControllerV3 c) { }   // E39 TopButtons.cs L24
    public FreeControllerV3 GetSelectedController() { return null; }   // E39 UI.cs L258
public delegate void SelectAtomCallback(Atom a);   // E39 (SelectModeAtom callback: ThrustController.cs L111)
    public void SelectModeAtom(SelectAtomCallback cb) { }   // E39 ThrustController.cs L111
    public List<AnimationPattern> GetAllAnimationPatterns() { return null; }   // E39 ThrustController.cs L139
    public void PauseSimulation(int frames, string reason) { }   // E39 MontageController.cs L211
}
namespace uFileBrowser
{
public delegate void FileBrowserCallback(string path);   // E39 (fileBrowserUI.Show callback: TopButtons.cs L38)
public partial class FileBrowser : UnityEngine.MonoBehaviour   // E39 (fileBrowserUI: TopButtons.cs L36-38, UI.cs L258; directoryBrowserUI: MontageController.cs L34-39)
    {
        public string defaultPath;   // E39 MontageController.cs L34
        public bool showDirs;   // E39 MontageController.cs L35
        public bool showFiles;   // E39 MontageController.cs L36
        public bool selectDirectory;   // E39 MontageController.cs L37
        public UnityEngine.GameObject window;   // E39 UI.cs L255
        public void SetTextEntry(bool b) { }   // E39 MontageController.cs L38
        public void Show(FileBrowserCallback cb, bool changeDirectory = true) { }   // E39 MontageController.cs L39
    }
}
public partial class Atom   // E39 BaseModule.cs L13
{
    public bool hidden;   // E39 SFXController.cs L42
    public void PreRestore() { }   // E39 MontageController.cs L193
    public void RestoreTransform(SimpleJSON.JSONClass jc) { }   // E39 MontageController.cs L194
    public void Restore(SimpleJSON.JSONClass jc, bool restorePhysical = true, bool restoreAppearance = true, bool restoreCore = true, SimpleJSON.JSONArray presetAtoms = null) { }   // E39 MontageController.cs L195
    public void LateRestore(SimpleJSON.JSONClass jc, bool restorePhysical = true, bool restoreAppearance = true, bool restoreCore = true) { }   // E39 MontageController.cs L196
    public void PostRestore() { }   // E39 Dollmaster.cs L155
    public void ClearParentAtom() { }   // E39 ThrustController.cs L318
    public void SelectAtomParent(Atom a) { }   // E39 ThrustController.cs L283
}
public partial class JSONStorable   // E39 DressController.cs L18
{
    public virtual void RestoreFromJSON(SimpleJSON.JSONClass jc, bool restorePhysical = true, bool restoreAppearance = true, SimpleJSON.JSONArray presetAtoms = null, bool setMissingToDefault = true) { }   // E39 Dollmaster.cs L149
    public virtual void PostRestore() { }   // E39 Dollmaster.cs L155
    public void SetBoolParamValue(string n, bool v) { }   // E39 Config.cs L32
    public void SetStringChooserParamValue(string n, string v) { }   // E39 Config.cs L37
}
public partial class MVRScript   // E39 Dollmaster.cs L10
{
    public MVRPluginManager manager;   // E39 Dollmaster.cs L287
    public UIDynamic CreateSpacer(bool rightSide = false) { return null; }   // E39 Arousal.cs L65
    public void RegisterUrl(JSONStorableUrl p) { }   // E39 MontageController.cs L30
}
public partial class MVRPluginManager   // E39 Dollmaster.cs L287
{
    public Transform configurableSliderPrefab;   // E39 UI.cs L63
    public Transform configurableButtonPrefab;   // E39 UI.cs L81
    public Transform configurableTogglePrefab;   // E39 UI.cs L92
    public Transform configurablePopupPrefab;   // E39 UI.cs L103
}
public partial class JSONStorableParam   // E39 ThrustController.cs L66
{
    public enum StoreType { Any, Physical, Appearance, Full }   // E39 ThrustController.cs L66
    public StoreType storeType;   // E39 ThrustController.cs L66
}
public partial class JSONStorableBool   // E39 Arousal.cs L14
{
    public JSONStorableBool(string name, bool startingValue) { }   // E39 Arousal.cs L14
    public bool defaultVal;   // E39 ThrustController.cs L193
    public void SetVal(bool v) { }   // E39 MontageController.cs L40
    public UnityEngine.UI.Toggle toggle;   // E39 HeadController.cs L47
}
public partial class JSONStorableFloat   // E39 Arousal.cs L15
{
    public JSONStorableFloat(string name, float startingValue, float minValue, float maxValue, bool constrain = true, bool interactable = true) { }   // E39 Arousal.cs L15
    public float min;   // E39 ThrustController.cs L162
    public float max;   // E39 Arousal.cs L111
    public float defaultVal;   // E39 ThrustController.cs L193
    public void SetVal(float v) { }   // E39 MontageController.cs L40
    public UnityEngine.UI.Slider slider;   // E39 Arousal.cs L44
}
public partial class JSONStorableStringChooser   // E39 PluginState.cs L12
{
    public string defaultVal;   // E39 ThrustController.cs L193
    public void SetVal(string v) { }   // E39 MontageController.cs L40
    public UIPopup popup;   // E39 PluginState.cs L26
}
public partial class JSONStorableUrl   // E39 MontageController.cs L19
{
    public JSONStorableUrl(string name, string startingValue) { }   // E39 MontageController.cs L19
    public void SetVal(string v) { }   // E39 MontageController.cs L40
}
public partial class JSONStorableAction { public ActionCallback actionCallback; }   // E39 Dollmaster.cs L118
public partial class UIDynamicToggle   // E39 Arousal.cs L35
{
    public string label;   // E39 Arousal.cs L36
    public Color backgroundColor;   // E39 Arousal.cs L37
    public UnityEngine.UI.Toggle toggle;   // E39 HeadController.cs L47
    public UnityEngine.UI.Text labelText;   // E39 Arousal.cs L47
}
public partial class UIDynamicSlider   // E39 Arousal.cs L42
{
    public UnityEngine.UI.Slider slider;   // E39 Arousal.cs L44
    public UnityEngine.UI.Text labelText;   // E39 Arousal.cs L47
    public bool quickButtonsEnabled;   // E39 UI.cs L70
    public bool rangeAdjustEnabled;   // E39 UI.cs L71
    public bool defaultButtonEnabled;   // E39 UI.cs L72
}
public partial class UIDynamicPopup { public UIPopup popup; }   // E39 ThrustController.cs L68
public partial class UIDynamicButton   // E39 ClimaxController.cs L23
{
    public string label;   // E39 Arousal.cs L36
    public Color textColor;   // E39 MontageController.cs L62
    public Color buttonColor;   // E39 MontageController.cs L61
}
public partial class DAZMorph   // E39 ExpressionController.cs L20
{
    public void SetValue(float v) { }   // E39 ExpressionController.cs L113
    public float startValue;   // E39 ExpressionController.cs L259
    public string region;   // E39 ExpressionController.cs L277
    public bool isPoseControl;   // E39 ExpressionController.cs L277
    public void SyncJSON() { }   // E39 Expressions.cs L65
}
public partial class GenerateDAZMorphsControlUI { public List<string> GetMorphDisplayNames() { return null; } }   // E39 ExpressionController.cs L16
public partial class DAZClothingItem : MonoBehaviour { public bool active; }   // E39 DressController.cs L43
public partial class DAZCharacterSelector   // E39 DressController.cs L14
{
    public enum Gender { None, Male, Female }   // E39 ThrustController.cs L297
    public Gender gender;   // E39 ThrustController.cs L297
    public DAZClothingItem[] clothingItems;   // E39 DressController.cs L21
    public void SetActiveClothingItem(DAZClothingItem item, bool active) { }   // E39 DressController.cs L37
}
public partial class NamedAudioClip { public string displayName; }   // E39 BreathController.cs L23
public partial class AudioSourceControl   // E39 Dollmaster.cs L39
{
    public void PlayIfClear(NamedAudioClip clip) { }   // E39 BreathController.cs L91
    public float clipLoudness;   // E39 ExpressionController.cs L104
    public float smoothedClipLoudness;   // E39 ExpressionController.cs L123
    public float volumeTriggerQuickness;   // E39 ExpressionController.cs L129
    public float pitch;   // E39 SFXController.cs L100
}
public partial class FreeControllerV3   // E39 BreathController.cs L14
{
    public enum PositionState { On, Off, Following, Hold, Lock, ParentLink, PhysicsLink }   // E39 SFXController.cs L35
    public enum SelectLinkState { Position, Rotation, PositionAndRotation }   // E39 SFXController.cs L40
    public PositionState currentPositionState;   // E39 SFXController.cs L35
    public Rigidbody linkToRB;   // E39 HeadController.cs L119
    public float RBHoldPositionSpring;   // E39 ClimaxController.cs L74
    public float RBHoldRotationSpring;   // E39 ClimaxController.cs L69
    public float jointRotationDriveXTarget;   // E39 BreathController.cs L71
    public bool canGrabPosition;   // E39 SFXController.cs L37
    public bool canGrabRotation;   // E39 SFXController.cs L38
    public bool selected;   // E39 UI.cs L260
    public void SelectLinkToRigidbody(Rigidbody rb, SelectLinkState s) { }   // E39 SFXController.cs L40
}
public partial class EyesControl { public Transform lookAt; }   // E39 HeadController.cs L32
public partial class MoveProducer : JSONStorable   // E39 MontageController.cs L149
{
    public FreeControllerV3 receiver;   // E39 MontageController.cs L151
    public void SetReceiverByName(string n) { }   // E39 ThrustController.cs L286
}
namespace MVR.FileManagementSecure
{
public static partial class FileManagerSecure   // E39b (everlasterVR/LiveReload src/FileSearch.cs)
    {
        public static string[] GetFiles(string dir, string pattern) { return null; }   // E39b LiveReload FileSearch.cs L34
        public static string[] GetDirectories(string dir, string pattern = null) { return null; }   // E39b LiveReload FileSearch.cs L44
    }
}

namespace SimpleJSON
{
    public partial class JSONNode   // E39 ExpressionController.cs L22
    {
        public virtual JSONClass AsObject { get { return null; } }   // E39 Config.cs L17
        public virtual JSONArray AsArray { get { return null; } }   // E39 ExpressionController.cs L293
        public virtual IEnumerable<JSONNode> Childs { get { yield break; } }   // E39 PoseController.cs L24
        public static implicit operator string(JSONNode n) { return null; }   // E39 BaseModule.cs L27
    }
}

namespace MeshVR { public partial class PresetManager { } }   // E39 TopButtons.cs L8 (using MeshVR; nothing of it is called)

public partial class DAZBone : JSONStorable { }   // E39 ExpressionController.cs L37-38, HeadController.cs L18-20, KissController.cs L20-27
public partial class DAZSkinWrap : MonoBehaviour { public string wrapName; }   // E39 DressController.cs L110-133
public partial class DAZSkinWrapSwitcher : MonoBehaviour   // E39 DressController.cs L68-112
{
    public string currentWrapName;   // E39 DressController.cs L78
    public void SetCurrentWrapName(string n) { }   // E39 DressController.cs L91
}
public partial class AnimationStep : JSONStorable { }   // E39 ThrustController.cs L320-340
public partial class AnimationPattern : JSONStorable   // E39 ThrustController.cs L17-340
{
    public void InitUI() { }   // E39 ThrustController.cs L41
    public void SyncStepNames() { }   // E39 ThrustController.cs L125
    public JSONStorableBool autoSyncStepNamesJSON;   // E39 ThrustController.cs L126
    public float GetCurrentTimeCounter() { return 0f; }   // E39 ThrustController.cs L181
    public float GetTotalTime() { return 0f; }   // E39 ThrustController.cs L181
    public AnimationStep[] steps;   // E39 ThrustController.cs L235
    public bool hideCurveUnlessSelected;   // E39 ThrustController.cs L246
    public void HideAllSteps() { }   // E39 ThrustController.cs L247
    public void DestroyAllSteps() { }   // E39 ThrustController.cs L272
    public AnimationStep CreateStepAtPosition(int i) { return null; }   // E39 ThrustController.cs L317
}
public partial class UIPopup : MonoBehaviour   // E39 UI.cs L104-113, PluginState.cs L29-35
{
    public string label;   // E39 Arousal.cs L36
    public bool showSlider;   // E39 PluginState.cs L28
public delegate void OnOpenPopup();   // E39 (onOpenPopupHandlers: ThrustController.cs L69)
    public OnOpenPopup onOpenPopupHandlers;   // E39 ThrustController.cs L69
}
