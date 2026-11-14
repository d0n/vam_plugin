// Speech output: a playback queue on the Person's head audio source.
//
// Default build (sandbox safe, no networking): each utterance is a WAV/OGG file below the VaM
// folder (written by the companion into Saves/PluginData/AIBody/<channel>/audio/). It is loaded
// with VaM's own URLAudioClipManager, the same loader the scene audio panel uses, and played
// with AudioSourceControl.PlayNow, so VaM's built-in lip sync follows it.
//
// Optional build (#define AIBODY_HTTP): an absolute "url" can also be downloaded with
// UnityWebRequestMultimedia. That code is excluded from the default compile because VaM 1.22
// may refuse plugins that reference UnityEngine.Networking.
//
// Utterances play strictly in order; the next ones are prefetched while one plays.
// speech_started / speech_ended are emitted from actual AudioSource playback state.
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
#if AIBODY_HTTP
using UnityEngine.Networking;
#endif

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
            public bool OwnsClip;           // downloaded clip (HTTP build): destroy when done
            public NamedAudioClip Managed;   // URLAudioClipManager clip: remove when done
            public bool Cancelled;
            public bool SeenPlaying;
            public float PlayTime;
        }

        private readonly MonoBehaviour _host;
        private readonly AudioSourceControl _control;
        private readonly AudioSource _audio;
        private readonly JSONStorableFloat _controlVolume;
        private readonly List<Utterance> _queue = new List<Utterance>();
        private Utterance _current;
        private float _volume = 1f;

        public float LoadTimeout = 15f;
        public int PrefetchCount = 2;

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
            if (_control != null)
            {
                _audio = _control.audioSource;
                // TODO(verify): AudioSourceControl exposes its volume slider as float param "volume".
                // If not, GetFloatJSONParam returns null and we set AudioSource.volume directly.
                _controlVolume = _control.GetFloatJSONParam("volume");
            }
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
                ApplyVolume();
            }
        }

        private void ApplyVolume()
        {
            if (_controlVolume != null) _controlVolume.val = _volume;
            else if (_audio != null) _audio.volume = _volume;
        }

        /// <summary>
        /// Adds an utterance. interrupt=true stops current speech and drops the queue first.
        /// Returns an error message, or null.
        /// </summary>
        public string Enqueue(string id, string url, string path, bool interrupt)
        {
            if (_audio == null) return "No HeadAudioSource on this atom";
#if !AIBODY_HTTP
            url = null; // downloads need the optional HTTP build
#endif
            if (string.IsNullOrEmpty(url) && string.IsNullOrEmpty(path))
                return "speak needs 'audio' (a file path below the VaM folder)";
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
                if (IsOurs(_current)) StopSource();
                Finish(reason);
            }
        }

        public void Update(float deltaTime)
        {
            if (_audio == null) return;

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
                bool ours = IsOurs(_current);
                bool playing = ours && _audio.isPlaying;
                if (playing) _current.SeenPlaying = true;
                _current.PlayTime += deltaTime;
                // Grace period: playback may start a frame late, and PlayNow may swap clips once.
                if (!ours && _current.PlayTime > 0.5f) Finish("interrupted");
                else if (ours && !playing && (_current.SeenPlaying || _current.PlayTime > 0.5f)) Finish("completed");
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

        private bool IsOurs(Utterance u)
        {
            return _audio != null && u.Clip != null && _audio.clip == u.Clip;
        }

        private void Play(Utterance u)
        {
            _current = u;
            ApplyVolume();
            if (u.Managed != null && _control != null)
            {
                // VaM's own playback path: lip sync and the audio source settings apply.
                // TODO(verify): PlayNow assigns clip.clipToPlay to the AudioSource (IsOurs relies on it).
                _control.PlayNow(u.Managed);
            }
            else
            {
                _audio.Stop();
                _audio.clip = u.Clip;
                _audio.Play();
            }
            if (OnStarted != null) OnStarted(u.Id, u.Clip.length);
        }

        private void StopSource()
        {
            if (_control != null) _control.Stop();
            else _audio.Stop();
        }

        private void Finish(string reason)
        {
            Utterance done = _current;
            _current = null;
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

#if AIBODY_HTTP
            if (!string.IsNullOrEmpty(u.Url) && u.Url.StartsWith("http"))
            {
                UnityWebRequest req = UnityWebRequestMultimedia.GetAudioClip(u.Url, GuessAudioType(u.Url));
                req.timeout = Mathf.CeilToInt(LoadTimeout);
                yield return req.SendWebRequest();
                if (req.isNetworkError || req.isHttpError) error = "download failed (" + req.error + "): " + u.Url;
                else
                {
                    AudioClip clip = DownloadHandlerAudioClip.GetContent(req);
                    if (clip != null && clip.length > 0f)
                    {
                        u.Clip = clip;
                        u.OwnsClip = true;
                    }
                    else error = "downloaded audio could not be decoded";
                }
                req.Dispose();
            }
#endif

            if (u.Clip == null && !string.IsNullOrEmpty(u.Path) && !u.Cancelled)
            {
                // TODO(verify): QueueClip accepts a path relative to the VaM folder on 1.22
                // (e.g. "Saves/PluginData/AIBody/default/audio/utt-1.wav") and loads WAV/OGG.
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
                u.Error = error ?? "no audio file given";
            }
        }

        private static string AppendError(string a, string b)
        {
            return string.IsNullOrEmpty(a) ? b : a + "; " + b;
        }

#if AIBODY_HTTP
        private static AudioType GuessAudioType(string url)
        {
            string u = url.ToLowerInvariant();
            if (u.EndsWith(".ogg")) return AudioType.OGGVORBIS;
            if (u.EndsWith(".mp3")) return AudioType.MPEG;
            return AudioType.WAV;
        }
#endif

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
