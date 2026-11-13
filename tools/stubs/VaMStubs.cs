// Compile-only stubs of the VaM 1.22 API surface used by the plugin (NOT shipped).
// Each member here is an assumption about the real VaM API. If VaM refuses to compile
// the plugin, compare the error against this list first.
#pragma warning disable 0067, 0649, 0169, 1591
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class SuperController : MonoBehaviour
{
    public static SuperController singleton;
    public static void LogMessage(string m) { }
    public static void LogError(string m) { }
    public List<Atom> GetAtoms() { return null; }
}

public class Atom : MonoBehaviour
{
    public string uid;
    public string type;
    public JSONStorable GetStorableByID(string id) { return null; }
    public List<string> GetStorableIDs() { return null; }
}

public class JSONStorable : MonoBehaviour
{
    public string storeId;
    public Atom containingAtom;
    public void RegisterBool(JSONStorableBool p) { }
    public void RegisterFloat(JSONStorableFloat p) { }
    public void RegisterString(JSONStorableString p) { }
    public void RegisterStringChooser(JSONStorableStringChooser p) { }
    public void RegisterAction(JSONStorableAction a) { }
    public JSONStorableFloat GetFloatJSONParam(string n) { return null; }
    public JSONStorableBool GetBoolJSONParam(string n) { return null; }
    public JSONStorableString GetStringJSONParam(string n) { return null; }
    public JSONStorableStringChooser GetStringChooserJSONParam(string n) { return null; }
    public JSONStorableUrl GetUrlJSONParam(string n) { return null; }
    public List<string> GetActionNames() { return null; }
    public void CallAction(string n) { }
}

public class JSONStorableParam { public string name; }
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
    public InputField inputField;
}
public class JSONStorableStringChooser : JSONStorableParam
{
    public delegate void SetStringCallback(string v);
    public JSONStorableStringChooser(string name, List<string> choices, string startingValue, string displayName, SetStringCallback callback) { }
    public string val;
    public List<string> choices { get; set; }
}
public class JSONStorableUrl : JSONStorableParam { public string val; }
public class JSONStorableAction
{
    public delegate void ActionCallback();
    public JSONStorableAction(string name, ActionCallback callback) { }
}

public class UIDynamic : MonoBehaviour { public float height; }
public class UIDynamicToggle : UIDynamic { }
public class UIDynamicSlider : UIDynamic { }
public class UIDynamicPopup : UIDynamic { }
public class UIDynamicButton : UIDynamic { public Button button; }
public class UIDynamicTextField : UIDynamic { public Text UItext; }

public class MVRScript : JSONStorable
{
    public virtual void Init() { }
    public UIDynamicToggle CreateToggle(JSONStorableBool p, bool rightSide = false) { return null; }
    public UIDynamicSlider CreateSlider(JSONStorableFloat p, bool rightSide = false) { return null; }
    public UIDynamicPopup CreatePopup(JSONStorableStringChooser p, bool rightSide = false) { return null; }
    public UIDynamicTextField CreateTextField(JSONStorableString p, bool rightSide = false) { return null; }
    public UIDynamicButton CreateButton(string label, bool rightSide = false) { return null; }
}

public class DAZMorph { public float morphValue; public string displayName; public string uid; }
public class GenerateDAZMorphsControlUI
{
    public DAZMorph GetMorphByDisplayName(string n) { return null; }
    public DAZMorph GetMorphByUid(string n) { return null; }
}
public class DAZCharacterSelector : JSONStorable { public GenerateDAZMorphsControlUI morphsControlUI; }

public class NamedAudioClip { public AudioClip clipToPlay; public AudioClip sourceClip; }
public class URLAudioClip : NamedAudioClip { }
public class URLAudioClipManager : MonoBehaviour
{
    public static URLAudioClipManager singleton;
    public URLAudioClip QueueClip(string url, string category = null) { return null; }
    public bool RemoveClip(NamedAudioClip clip) { return true; }
}
public class AudioSourceControl : JSONStorable
{
    public AudioSource audioSource;
    public void PlayNow(NamedAudioClip clip) { }
    public void Stop() { }
}

public class FreeControllerV3 : JSONStorable
{
    public enum RotationState { On, Off, Following, Hold, Lock, ParentLink, PhysicsLink }
    public RotationState currentRotationState;
}

namespace MVR.FileManagementSecure
{
    public static class FileManagerSecure
    {
        public static bool FileExists(string path, bool onlySystemFiles = false) { return false; }
        public static string ReadAllText(string path) { return null; }
        public static void WriteAllText(string path, string text) { }
        public static void DeleteFile(string path) { }
        public static void CreateDirectory(string path) { }
        public static string[] GetFiles(string dir, string pattern = null) { return null; }
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
