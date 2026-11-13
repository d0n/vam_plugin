// Compile-only stubs of the small UnityEngine surface used by the plugin.
// NOT shipped to VaM. Used by tools/check_plugin.sh to syntax/type-check src/*.cs with
// C# 6 outside of VaM. Behaviour is irrelevant; only signatures matter.
#pragma warning disable 0067, 0649, 0169, 1591
using System;
using System.Collections;

namespace UnityEngine
{
    public class Object { }
    public class Component : Object
    {
        public GameObject gameObject { get { return null; } }
        public Transform transform { get { return null; } }
    }
    public class Behaviour : Component { public bool enabled; }
    public class MonoBehaviour : Behaviour
    {
        public Coroutine StartCoroutine(IEnumerator routine) { return null; }
        public void StopCoroutine(Coroutine routine) { }
    }
    public class GameObject : Object
    {
        public T AddComponent<T>() where T : Component { return null; }
    }
    public sealed class Coroutine { }
    public class AsyncOperation { }
    public class Transform : Component
    {
        public Quaternion rotation { get; set; }
        public Vector3 position { get; set; }
    }
    public struct Vector3 { public float x, y, z; }
    public struct Quaternion
    {
        public static Quaternion identity { get { return new Quaternion(); } }
        public static Quaternion Euler(float x, float y, float z) { return new Quaternion(); }
        public static Quaternion Inverse(Quaternion q) { return q; }
        public static Quaternion operator *(Quaternion a, Quaternion b) { return a; }
    }
    public static class Mathf
    {
        public const float PI = 3.14159265f;
        public static float Sin(float f) { return 0f; }
        public static float Cos(float f) { return 0f; }
        public static float Pow(float f, float p) { return 0f; }
        public static float Abs(float f) { return 0f; }
        public static float Max(float a, float b) { return a; }
        public static float Clamp01(float v) { return v; }
        public static float MoveTowards(float c, float t, float d) { return t; }
        public static bool Approximately(float a, float b) { return true; }
        public static float PerlinNoise(float x, float y) { return 0f; }
    }
    public static class Time
    {
        public static float deltaTime { get { return 0f; } }
        public static float unscaledDeltaTime { get { return 0f; } }
        public static float time { get { return 0f; } }
    }
    public static class Random
    {
        public static float Range(float a, float b) { return a; }
    }
    public class AudioClip : Object { }
    public class AudioSource : Behaviour { public bool isPlaying { get { return false; } } }
}

namespace UnityEngine.Events
{
    public delegate void UnityAction();
    public class UnityEvent { public void AddListener(UnityAction a) { } }
}

namespace UnityEngine.UI
{
    public class Text : Component { }
    public class Button : Component
    {
        public class ButtonClickedEvent : UnityEngine.Events.UnityEvent { }
        public ButtonClickedEvent onClick { get { return null; } }
    }
    public class InputField : Component
    {
        public enum LineType { SingleLine, MultiLineSubmit, MultiLineNewline }
        public Text textComponent;
        public LineType lineType;
    }
}

namespace UnityEngine.Networking
{
    public class UploadHandler { }
    public class UploadHandlerRaw : UploadHandler { public UploadHandlerRaw(byte[] data) { } }
    public class DownloadHandler { public string text { get { return null; } } }
    public class DownloadHandlerBuffer : DownloadHandler { }
    public class UnityWebRequestAsyncOperation : AsyncOperation { }
    public class UnityWebRequest : IDisposable
    {
        public UnityWebRequest(string url, string method) { }
        public static UnityWebRequest Get(string url) { return null; }
        public static string EscapeURL(string s) { return s; }
        public UnityWebRequestAsyncOperation SendWebRequest() { return null; }
        public int timeout;
        public bool isNetworkError { get { return false; } }
        public bool isHttpError { get { return false; } }
        public string error { get { return null; } }
        public UploadHandler uploadHandler;
        public DownloadHandler downloadHandler;
        public void SetRequestHeader(string k, string v) { }
        public void Dispose() { }
    }
}
