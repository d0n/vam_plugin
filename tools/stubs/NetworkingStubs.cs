// Compile-only stubs of UnityEngine.Networking. Only used for the OPTIONAL AIBODY_HTTP build.
// The default build is compiled WITHOUT this file, so any accidental use of UnityWebRequest in
// the default sources fails the check (VaM 1.22 may refuse such plugins).
#pragma warning disable 0067, 0649, 0169, 1591
using System;
using UnityEngine;

namespace UnityEngine.Networking
{
    public class UploadHandler { }
    public class UploadHandlerRaw : UploadHandler { public UploadHandlerRaw(byte[] data) { } }
    public class DownloadHandler { public string text { get { return null; } } }
    public class DownloadHandlerBuffer : DownloadHandler { }
    public sealed class DownloadHandlerAudioClip : DownloadHandler
    {
        public static AudioClip GetContent(UnityWebRequest www) { return null; }
    }
    public static class UnityWebRequestMultimedia
    {
        public static UnityWebRequest GetAudioClip(string uri, AudioType audioType) { return null; }
    }
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
        public void Abort() { }
        public void Dispose() { }
    }
}
