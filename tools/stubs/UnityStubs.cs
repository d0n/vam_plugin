// Compile-only stubs of the small UnityEngine surface used by the plugin.
// NOT shipped to VaM. Used by tools/check_plugin.py to syntax/type-check src/*.cs with
// C# 6 outside of VaM. Behaviour is irrelevant; only signatures matter.
#pragma warning disable 0067, 0649, 0169, 1591
using System;
using System.Collections;

namespace UnityEngine
{
    public enum TextAnchor { UpperLeft, UpperCenter, UpperRight, MiddleLeft, MiddleCenter, MiddleRight, LowerLeft, LowerCenter, LowerRight }
    public class Object { public string name; public static void Destroy(Object o) { } }   // name: E12 L164 (fc.name == ...)
    public class Component : Object
    {
        public GameObject gameObject { get { return null; } }
        public Transform transform { get { return null; } }
    }
    public class Behaviour : Component { public bool enabled; }
    public class MonoBehaviour : Behaviour { }
    public class GameObject : Object
    {
        public T AddComponent<T>() where T : Component { return null; }
        public bool activeInHierarchy { get { return false; } }       // E12 L1271, E11 L206
    }
    public struct Color                                                // E32 (AmbientLightRig L122, L181), E30 (AutoPupil L204)
    {
        public float r, g, b, a;
        public Color(float r, float g, float b, float a) { this.r = r; this.g = g; this.b = b; this.a = a; }
        public Color(float r, float g, float b) { this.r = r; this.g = g; this.b = b; this.a = 1f; }
        public static Color HSVToRGB(float h, float s, float v) { return new Color(); }   // E32 (AmbientLightRig L181)
    }
    public enum CameraClearFlags { Skybox = 1, SolidColor = 2, Depth = 3, Nothing = 4 }   // E30 (AutoPupil L203: SolidColor); the old value is only kept and restored
    public class Camera : Behaviour                                    // E30 (AutoPupil L203-205)
    {
        public CameraClearFlags clearFlags { get; set; }
        public Color backgroundColor { get; set; }
    }
    public class Transform : Component
    {
        public Quaternion rotation { get; set; }
        public Vector3 position { get; set; }
    }
    public struct Vector3                                              // E12 L1182, E28 L187-209 (+, *, / float, forward, zero)
    {
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public static Vector3 zero { get { return new Vector3(); } }
        public static Vector3 forward { get { return new Vector3(0f, 0f, 1f); } }
        public static Vector3 up { get { return new Vector3(0f, 1f, 0f); } }                  // E12 L1158 (Vector3.up)
        public float magnitude { get { return 0f; } }                                          // E12 L1279
        public Vector3 normalized { get { return this; } }                                     // E12 L1280
        public static Vector3 Cross(Vector3 a, Vector3 b) { return a; }                        // E12 L1554
        public static Vector3 operator -(Vector3 a, Vector3 b) { return a; }                   // E12 L1278 (target - eyeCenter)
        public static Vector3 operator +(Vector3 a, Vector3 b) { return a; }
        public static Vector3 operator *(Vector3 a, float d) { return a; }
    }
    public struct Quaternion
    {
        public static Quaternion identity { get { return new Quaternion(); } }
        public static Quaternion Euler(float x, float y, float z) { return new Quaternion(); }
        public static Quaternion Inverse(Quaternion q) { return q; }
        public static Quaternion operator *(Quaternion a, Quaternion b) { return a; }
        public static Vector3 operator *(Quaternion q, Vector3 v) { return v; }   // E12 L1182 (_head.rotation * ... * Vector3.forward)
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
        public static float SmoothStep(float a, float b, float t) { return a; }                // E29 L87
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
    public class AudioSource : Behaviour
    {
        // Read-only use: playback goes through AudioSourceControl (FreeMMD reads .audioSource).
        public bool isPlaying { get { return false; } }
        public AudioClip clip { get; set; }
    }
}

namespace UnityEngine.Events
{
    public delegate void UnityAction();
    public class UnityEvent { public void AddListener(UnityAction a) { } }
}

namespace UnityEngine.UI
{
    public class Text : Component { public TextAnchor alignment; public string text; }   // E27; text: vam-timeline MocapScreen.cs (commit d6f7177c) sets buttonText.text
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
        // Standard Unity UI (same class as E14, UnityEngine.UI.InputField): true while the field has keyboard focus.
        public bool isFocused { get { return false; } }
    }
}

