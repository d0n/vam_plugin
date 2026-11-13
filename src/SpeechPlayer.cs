// Speech output: a playback queue on the Person's head audio source.
//
// Each utterance can be delivered two ways:
//   1. url  - downloaded from the companion's HTTP server with UnityWebRequestMultimedia
//             (primary; needs network access, works even if the companion runs elsewhere)
//   2. audio - a file path relative to the VaM folder, loaded through URLAudioClipManager
//             (fallback for the file transport)
// If both are given the URL is tried first and the path is used when the download fails.
//
// Utterances play strictly in order. The next ones are prefetched while one plays.
// speech_started / speech_ended are emitted from actual AudioSource playback state, so the
// companion's echo gate follows what is really coming out of the speakers.
//
// Playback uses the Unity AudioSource behind HeadAudioSource directly (clip + Play()), so
// downloaded clips and file clips share one code path and volume is under our control.
// VaM's LipSync reads the audio source output, so lip sync follows.
// TODO(verify): on VaM 1.22 confirm that (a) AudioSourceControl does not stop or replace a clip
// that was started directly on its AudioSource, and (b) LipSync reacts to it.
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;

namespace AIBody
{
    public class SpeechPlayer
    {
        private enum LoadState { Pending, Loading, Ready, Failed }

        private class Utterance
        {
            public string Id;
            public string Url;
            public string Path;
            public LoadState State;
            public string Error;
            public AudioClip Clip;
            public bool OwnsClip;           // downloaded clip: destroy when done
            public NamedAudioClip Managed;   // URLAudioClipManager clip: remove when done
            public bool Cancelled;
            public bool SeenPlaying;
            public float PlayTime;
        }

        private readonly MonoBehaviour _host;
        private readonly AudioSourceControl _control;
        private readonly AudioSource _audio;
        private readonly List<Utterance> _queue = new List<Utterance>();
        private Utterance _current;
        private float _volume = 1f;

        public float LoadTimeout = 15f;
        public int PrefetchCount = 2;

        /// <summary>Returns the companion base URL while HTTP is connected, else null.</summary>
        public Func<string> HttpBaseUrl;

        /// <summary>(utteranceId, clipLengthSeconds)</summary>
        public Action<string, float> OnStarted;

        /// <summary>(utteranceId, reason): completed | stopped | interrupted | cancelled | failed</summary>
        public Action<string, string> OnEnded;

        /// <summary>(utteranceId, message)</summary>
        public Action<string, string> OnError;

        public SpeechPlayer(MonoBehaviour host, Atom atom)
        {
            _host = host;
            _control = atom.GetStorableByID("HeadAudioSource") as AudioSourceControl;
            if (_control != null) _audio = _control.audioSource;
            if (_audio == null) Log.Error("No HeadAudioSource on atom " + atom.uid + "; speech output disabled.");
        }

        public bool Available { get { return _audio != null; } }
        public bool IsSpeaking { get { return _current != null; } }
        public string CurrentId { get { return _current != null ? _current.Id : null; } }
        public int QueueLength { get { return _queue.Count; } }

        public float Volume
        {
            get { return _volume; }
            set
            {
                _volume = Mathf.Clamp01(value);
                if (_current != null && _audio != null && _audio.clip == _current.Clip) _audio.volume = _volume;
            }
        }

        /// <summary>
        /// Adds an utterance. interrupt=true stops current speech and drops the queue first.
        /// Returns an error message, or null.
        /// </summary>
        public string Enqueue(string id, string url, string path, bool interrupt)
        {
            if (_audio == null) return "No HeadAudioSource on this atom";
            if (string.IsNullOrEmpty(url) && string.IsNullOrEmpty(path)) return "speak needs 'url' or 'audio'";
            if (interrupt) StopAll("interrupted");
            _queue.Add(new Utterance { Id = id, Url = url, Path = path, State = LoadState.Pending });
            return null;
        }

        /// <summary>Stops current speech and cancels everything queued.</summary>
        public void StopAll(string reason)
        {
            for (int i = 0; i < _queue.Count; i++)
            {
                Utterance u = _queue[i];
                u.Cancelled = true;
                if (u.State != LoadState.Loading) Release(u);
                Fire(OnEnded, u.Id, "cancelled");
            }
            _queue.Clear();
            if (_current != null)
            {
                if (_audio != null && _audio.clip == _current.Clip) _audio.Stop();
                Finish(reason);
            }
        }

        public void Update(float deltaTime)
        {
            if (_audio == null) return;

            // Start loading the first few queued utterances.
            int limit = Math.Min(_queue.Count, Math.Max(1, PrefetchCount));
            for (int i = 0; i < limit; i++)
            {
                if (_queue[i].State == LoadState.Pending)
                {
                    _queue[i].State = LoadState.Loading;
                    _host.StartCoroutine(LoadRoutine(_queue[i]));
                }
            }

            if (_current != null)
            {
                bool ours = _audio.clip == _current.Clip;
                bool playing = ours && _audio.isPlaying;
                if (playing) _current.SeenPlaying = true;
                _current.PlayTime += deltaTime;
                if (!ours) Finish("interrupted");
                // Grace period: some audio backends report isPlaying a frame late.
                else if (!playing && (_current.SeenPlaying || _current.PlayTime > 0.5f)) Finish("completed");
            }

            if (_current == null && _queue.Count > 0)
            {
                Utterance next = _queue[0];
                if (next.State == LoadState.Failed)
                {
                    _queue.RemoveAt(0);
                    Fire(OnError, next.Id, next.Error ?? "audio failed to load");
                    Fire(OnEnded, next.Id, "failed");
                }
                else if (next.State == LoadState.Ready)
                {
                    _queue.RemoveAt(0);
                    Play(next);
                }
            }
        }

        private void Play(Utterance u)
        {
            _current = u;
            _audio.Stop();
            _audio.clip = u.Clip;
            _audio.volume = _volume;
            _audio.Play();
            if (OnStarted != null) OnStarted(u.Id, u.Clip.length);
        }

        private void Finish(string reason)
        {
            Utterance done = _current;
            _current = null;
            if (_audio != null && _audio.clip == done.Clip) _audio.clip = null;
            Release(done);
            Fire(OnEnded, done.Id, reason);
        }

        private static void Fire(Action<string, string> cb, string a, string b)
        {
            if (cb != null) cb(a, b);
        }

        // ------------------------------------------------------------------ loading

        private IEnumerator LoadRoutine(Utterance u)
        {
            string error = null;
            string baseUrl = HttpBaseUrl != null ? HttpBaseUrl() : null;

            if (!string.IsNullOrEmpty(u.Url) && (baseUrl != null || u.Url.StartsWith("http")))
            {
                string url = u.Url.StartsWith("http") ? u.Url : baseUrl + u.Url;
                UnityWebRequest req = UnityWebRequestMultimedia.GetAudioClip(url, GuessAudioType(url));
                req.timeout = Mathf.CeilToInt(LoadTimeout);
                yield return req.SendWebRequest();
                if (req.isNetworkError || req.isHttpError) error = "download failed (" + req.error + "): " + url;
                else
                {
                    AudioClip clip = ExtractClip(req, out error);
                    if (clip != null)
                    {
                        u.Clip = clip;
                        u.OwnsClip = true;
                    }
                }
                req.Dispose();
            }
            else if (!string.IsNullOrEmpty(u.Url))
            {
                error = "not connected over HTTP, cannot download " + u.Url;
            }

            if (u.Clip == null && !string.IsNullOrEmpty(u.Path) && !u.Cancelled)
            {
                // TODO(verify): QueueClip accepts a path relative to the VaM folder on 1.22.
                NamedAudioClip managed = URLAudioClipManager.singleton.QueueClip(u.Path);
                if (managed == null) error = AppendError(error, "could not queue " + u.Path);
                else
                {
                    u.Managed = managed;
                    float waited = 0f;
                    while (!IsClipReady(managed) && waited < LoadTimeout && !u.Cancelled)
                    {
                        waited += Time.unscaledDeltaTime;
                        yield return null;
                    }
                    if (IsClipReady(managed)) u.Clip = managed.clipToPlay;
                    else error = AppendError(error, "timed out loading " + u.Path);
                }
            }

            if (u.Cancelled)
            {
                Release(u);
                yield break;
            }
            if (u.Clip != null) u.State = LoadState.Ready;
            else
            {
                u.State = LoadState.Failed;
                u.Error = error ?? "no audio source given";
            }
        }

        private static string AppendError(string a, string b)
        {
            return string.IsNullOrEmpty(a) ? b : a + "; " + b;
        }

        private static AudioClip ExtractClip(UnityWebRequest req, out string error)
        {
            error = null;
            try
            {
                AudioClip clip = DownloadHandlerAudioClip.GetContent(req);
                if (clip == null || clip.length <= 0f) error = "downloaded audio could not be decoded";
                return error == null ? clip : null;
            }
            catch (Exception e)
            {
                error = "audio decode failed: " + e.Message;
                return null;
            }
        }

        private static AudioType GuessAudioType(string url)
        {
            string u = url.ToLowerInvariant();
            if (u.EndsWith(".ogg")) return AudioType.OGGVORBIS;
            if (u.EndsWith(".mp3")) return AudioType.MPEG;
            return AudioType.WAV;
        }

        // TODO(verify): NamedAudioClip.clipToPlay is null until the URL clip finished loading.
        private static bool IsClipReady(NamedAudioClip clip)
        {
            return clip.clipToPlay != null;
        }

        private static void Release(Utterance u)
        {
            if (u.OwnsClip && u.Clip != null) UnityEngine.Object.Destroy(u.Clip);
            u.Clip = null;
            u.OwnsClip = false;
            if (u.Managed != null)
            {
                URLAudioClip urlClip = u.Managed as URLAudioClip;
                if (urlClip != null) URLAudioClipManager.singleton.RemoveClip(urlClip);
                u.Managed = null;
            }
        }
    }
}
