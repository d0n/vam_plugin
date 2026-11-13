// Compile-only stubs of the small UnityEngine surface used by the plugin.
// NOT shipped to VaM. Used by tools/check_plugin.sh to syntax/type-check src/*.cs with
// C# 6 outside of VaM. Behaviour is irrelevant; only signatures matter.
#pragma warning disable 0067, 0649, 0169, 1591
using System;
using System.Collections;

namespace UnityEngine
{
    public class Object { public static void Destroy(Object o) { } }
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
        public static float Min(float a, float b) { return a; }
        public static float Log10(float f) { return 0f; }
        public static int Clamp(int v, int min, int max) { return v; }
        public static int FloorToInt(float f) { return 0; }
        public static int CeilToInt(float f) { return 0; }
        public static int RoundToInt(float f) { return 0; }
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
    public class AudioClip : Object { public float length { get { return 0f; } } }
    public enum AudioType { UNKNOWN, ACC, AIFF, IT, MOD, MPEG, OGGVORBIS, S3M, WAV, XM, XMA, VAG, AUDIOQUEUE }
    public class AudioSource : Behaviour
    {
        public bool isPlaying { get { return false; } }
        public AudioClip clip { get; set; }
        public float volume { get; set; }
        public void Play() { }
        public void Stop() { }
    }
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

