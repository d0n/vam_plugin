// Compile-only stubs of the VaM 1.22 API surface used by the plugin (NOT shipped).
//
// Only members with public evidence of use in sandboxed VaM plugins are declared here, so the
// compile check fails if the plugin starts using anything else. Each group names its evidence
// (keys E1..E20 = links in docs/API_AUDIT.md). Deliberately NOT declared: NamedAudioClip.clipToPlay,
// JSONStorable.GetActionNames, FileManagerSecure.GetFiles(dir, pattern),
// UnityEngine.Networking / UnityWebRequest (no stub file exists for them at all).
#pragma warning disable 0067, 0649, 0169, 1591
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class SuperController : MonoBehaviour
{
    public static SuperController singleton;
    public static void LogMessage(string m) { }                       // E9
    public static void LogError(string m) { }                         // E9, E12
    public string NormalizeMediaPath(string path) { return path; }    // E1, E3 (before QueueClip)
    public string NormalizePath(string path) { return path; }         // E7 (preset browse path)
    public CameraTarget centerCameraTarget;                           // E12 L647 (the player's view; .transform)
    public List<Atom> GetAtoms() { return null; }                     // E12 L180, L759, L797
}

public class CameraTarget : MonoBehaviour { }                          // E12 L647

public class Atom : MonoBehaviour
{
    public FreeControllerV3[] freeControllers;                        // E12 L164, L178; E28 L83
    public FreeControllerV3 mainController;                           // E12 L812, L957
    public string uid;
    public string type;                                               // E12 ("Person" check)
    public JSONStorable GetStorableByID(string id) { return null; }   // E1, E4, E6, E12
    public List<string> GetStorableIDs() { return null; }             // E8 (find Timeline storable)
}

public class JSONStorable : MonoBehaviour
{
    public string storeId;                                            // E1
    public Atom containingAtom;
    public void RegisterBool(JSONStorableBool p) { }                  // E9, E16
    public void RegisterFloat(JSONStorableFloat p) { }                // E4
    public void RegisterString(JSONStorableString p) { }              // E9
    public void RegisterStringChooser(JSONStorableStringChooser p) { }// E9, E16
    public void RegisterAction(JSONStorableAction a) { }              // E9, E12
    public JSONStorableFloat GetFloatJSONParam(string n) { return null; }                 // E12
    public JSONStorableBool GetBoolJSONParam(string n) { return null; }                   // E12
    public JSONStorableString GetStringJSONParam(string n) { return null; }               // E13
    public JSONStorableStringChooser GetStringChooserJSONParam(string n) { return null; } // E13
    public JSONStorableUrl GetUrlJSONParam(string n) { return null; }                     // E7
    public void CallAction(string n) { }                                                  // E7, E8
    public SimpleJSON.JSONClass GetJSON(bool includePhysical = true, bool includeAppearance = true, bool forceStore = false) { return null; } // E1 (L288, PluginManager)
}

public class MVRPluginManager : JSONStorable { }                       // E1 (L287, GetStorableByID("PluginManager"))

public class JSONStorableParam { public string name; public bool isStorable = true; public bool isRestorable = true; }   // E12 L66 (isStorable / isRestorable)
public class JSONStorableBool : JSONStorableParam
{
    public delegate void SetBoolCallback(bool v);
    public JSONStorableBool(string name, bool startingValue, SetBoolCallback callback) { }
    public bool val;
}
public class JSONStorableFloat : JSONStorableParam
{
    public delegate void SetFloatCallback(float v);
    public JSONStorableFloat(string name, float startingValue, SetFloatCallback callback, float minValue, float maxValue, bool constrain = true, bool interactable = true) { }
    public float val;
}
public class JSONStorableString : JSONStorableParam
{
    public delegate void SetStringCallback(string v);
    public JSONStorableString(string name, string startingValue) { }
    public JSONStorableString(string name, string startingValue, SetStringCallback callback) { }
    public string val;
    public InputField inputField;                                     // E14
}
public class JSONStorableStringChooser : JSONStorableParam
{
    public delegate void SetStringCallback(string v);
    public JSONStorableStringChooser(string name, List<string> choices, string startingValue, string displayName, SetStringCallback callback) { }
    public string val;
    public List<string> choices { get; set; }                         // E9 (choices = ...), E25 (on a shown popup)
    public List<string> displayChoices { get; set; }                  // E24 (set together with choices)
    public delegate void PopupOpenCallback();
    public PopupOpenCallback popupOpenCallback;                       // E25 (Embody, Timeline)
}
public class JSONStorableUrl : JSONStorableParam { public string val; } // E7
public class JSONStorableAction
{
    public delegate void ActionCallback();
    public JSONStorableAction(string name, ActionCallback callback) { } // E9, E12
}

public class UIDynamic : MonoBehaviour { public float height; }
public class UIDynamicToggle : UIDynamic { }
public class UIDynamicSlider : UIDynamic { public string label; }   // label: E26 (TittyMagic, ExpressionRND)
public class UIDynamicPopup : UIDynamic { }
public class UIDynamicButton : UIDynamic { public Button button; public Text buttonText; }   // buttonText: E27
public class UIDynamicTextField : UIDynamic { public Text UItext; }   // E14

public class MVRScript : JSONStorable
{
    public virtual void Init() { }
    public UIDynamicToggle CreateToggle(JSONStorableBool p, bool rightSide = false) { return null; }        // E12
    public UIDynamicSlider CreateSlider(JSONStorableFloat p, bool rightSide = false) { return null; }       // E12
    public UIDynamicPopup CreatePopup(JSONStorableStringChooser p, bool rightSide = false) { return null; }  // E16
    public UIDynamicPopup CreateScrollablePopup(JSONStorableStringChooser p, bool rightSide = false) { return null; }  // E24
    public UIDynamicTextField CreateTextField(JSONStorableString p, bool rightSide = false) { return null; } // E12
    public UIDynamicButton CreateButton(string label, bool rightSide = false) { return null; }        // E1, E3
    // Tabs: remove the controls of the old tab, create the new ones.                     E17, E18
    public void RemoveToggle(UIDynamicToggle t) { }
    public void RemoveSlider(UIDynamicSlider s) { }
    public void RemovePopup(UIDynamicPopup p) { }
    public void RemoveButton(UIDynamicButton b) { }
    public void RemoveTextField(UIDynamicTextField t) { }
}

public class DAZMorph { public float morphValue; }                    // E4
public class GenerateDAZMorphsControlUI
{
    public DAZMorph GetMorphByDisplayName(string n) { return null; }  // E4
    public DAZMorph GetMorphByUid(string n) { return null; }          // E5
}
public class DAZCharacterSelector : JSONStorable { public GenerateDAZMorphsControlUI morphsControlUI; } // E4

public class NamedAudioClip { public string uid; }                    // E1
public class URLAudioClip : NamedAudioClip { }
public class URLAudioClipManager : MonoBehaviour
{
    public static URLAudioClipManager singleton;
    public URLAudioClip QueueClip(string url, string category = null) { return null; } // E1, E3
    public NamedAudioClip GetClip(string uid) { return null; }                         // E1, E3
    public bool RemoveClip(NamedAudioClip clip) { return true; }                       // E2
}
public class AudioSourceControl : JSONStorable
{
    public AudioSource audioSource;                                   // E3
    public float volume;                                              // E2
    public void PlayNow(NamedAudioClip clip) { }                      // E1, E2
    public void Stop() { }                                            // E3
}

public class FreeControllerV3 : JSONStorable                          // E6 (headControl transform)
{
    public enum RotationState { On, Off, Following, Hold, Lock, ParentLink, PhysicsLink }
    public RotationState currentRotationState;                        // E2
    public Transform control;                                         // E12 L678, L704; E28 L109, L209 (control.position)
}

public class EyesControl : JSONStorable                               // E12 L159; E28 L79 (GetStorableByID("Eyes"))
{
    public enum LookMode { Target, Custom }                           // E12 L681, L686 (the real enum has more values; only evidenced ones are declared)
    public LookMode currentLookMode;                                  // E12 L652, L681, L732; E28 L108, L116, L167
}

namespace MVR.FileManagementSecure                                    // E15 (official), E10, E11
{
    public static class FileManagerSecure
    {
        public static bool FileExists(string path, bool onlySystemFiles = false) { return false; } // E10
        public static string ReadAllText(string path) { return null; }                             // E11
        public static void WriteAllText(string path, string text) { }                              // E11, E20
        public static void DeleteFile(string path) { }                                             // E10
        public static void CreateDirectory(string path) { }                                        // E10, E11
        public static string[] GetFiles(string dir) { return null; }                               // E11
    }
}

namespace SimpleJSON
{
    // Mirrors the old (Bunny83) SimpleJSON bundled with VaM.
    public class JSONNode
    {
        public virtual JSONNode this[string key] { get { return null; } set { } }
        public virtual JSONNode this[int index] { get { return null; } set { } }
        public virtual string Value { get { return ""; } set { } }
        public virtual int Count { get { return 0; } }
        public virtual void Add(JSONNode item) { }
        public virtual JSONNode Remove(int index) { return null; }
        public virtual int AsInt { get; set; }
        public virtual float AsFloat { get; set; }
        public virtual double AsDouble { get; set; }
        public virtual bool AsBool { get; set; }
        public static implicit operator JSONNode(string s) { return new JSONData(s); }
    }
    public class JSONData : JSONNode { public JSONData(string s) { } }
    public class JSONArray : JSONNode, IEnumerable { public IEnumerator GetEnumerator() { yield break; } }
    public class JSONClass : JSONNode, IEnumerable { public IEnumerator GetEnumerator() { yield break; } }
    public static class JSON { public static JSONNode Parse(string s) { return null; } }
}
