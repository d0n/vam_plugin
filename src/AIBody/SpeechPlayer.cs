// Speech output: a playback queue on the Person's head audio source.
//
// Each utterance is a WAV/OGG file below the VaM folder, written by the companion app into
// Saves/PluginData/AIBody/<channel>/audio/. Only VaM's own audio path is used, exactly as public
// sandboxed plugins do it (see docs/API_AUDIT.md for the evidence links):
//   - load:  URLAudioClipManager.singleton.QueueClip(SuperController.singleton.NormalizeMediaPath(path))
//            then URLAudioClipManager.singleton.GetClip(clip.uid)          (Dollmaster, FreeMMD)
//   - play:  the "HeadAudioSource" AudioSourceControl's PlayNow(namedClip) (Dollmaster), so VaM's
//            built-in lip sync follows it; Stop() and .audioSource            (FreeMMD); .volume (Dollmaster SFX)
//   - free:  URLAudioClipManager.singleton.RemoveClip(namedClip)           (Dollmaster SFX)
// There is no network code and no readiness API: a clip counts as started when the head
// AudioSource (UnityEngine.AudioSource) is playing a new clip, and as finished when it stops.
// TODO(verify): on 1.22, that a Saves/PluginData relative path works with NormalizeMediaPath +
// QueueClip (the evidence loads paths picked in the file browser), and that PlayNow on a clip
// still loading is retried safely (start detection via AudioSource.isPlaying/clip).
//
// Utterances play strictly in order; the next ones are queued for loading while one plays.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace AIBody
{
    public class SpeechPlayer
    {
        private class Utterance
        {
            public string Id;
            public string Path;
            public bool Queued;              // handed to URLAudioClipManager
            public NamedAudioClip Clip;      // remove from URLAudioClipManager when done
            public string Error;
            public bool Started;
            public AudioClip PreviousClip;   // what the head audio held before our PlayNow
            public AudioClip StartedClip;    // what it plays once our clip started
            public float PlayTime;
            public float RetryTimer;
        }

        private readonly Atom _atom;
        private AudioSourceControl _control;   // looked up lazily (Resolve), retried every 5 s
        private AudioSource _audio;
        private float _retryIn;
        private bool _warned;
        private readonly List<Utterance> _queue = new List<Utterance>();
        private Utterance _current;
        private float _volume = 1f;

        /// <summary>Seconds to wait for a clip to start playing before reporting it as failed.</summary>
        public float StartTimeout = 15f;
        /// <summary>PlayNow is called again at this interval until the clip plays (it may still be loading).</summary>
        public float RetryInterval = 1f;
        public int PrefetchCount = 2;

        /// <summary>(utteranceId, clipLengthSeconds)</summary>
        public Action<string, float> OnStarted;

        /// <summary>(utteranceId, reason): completed | stopped | interrupted | cancelled | failed</summary>
        public Action<string, string> OnEnded;

        /// <summary>(utteranceId, message)</summary>
        public Action<string, string> OnError;

        public SpeechPlayer(Atom atom)
        {
            _atom = atom;
            Resolve();
        }

        /// <summary>Why the head audio is not available (null while it is).</summary>
        public string LookupError { get; private set; }

        public bool Available { get { return Resolve(); } }

        /// <summary>Finds the head AudioSourceControl; a failed lookup is retried every 5 s.</summary>
        private bool Resolve()
        {
            if (_audio != null) return true;
            if (_retryIn > 0f) return false;
            _retryIn = 5f;
            try
            {
                _control = _atom.GetStorableByID("HeadAudioSource") as AudioSourceControl;
                _audio = _control != null ? _control.audioSource : null;
                if (_audio != null)
                {
                    _control.volume = _volume;
                    LookupError = null;
                    if (_warned) Log.Info("HeadAudioSource found; speech output enabled.");
                    return true;
                }
                LookupError = _control == null ? "kein Storable 'HeadAudioSource'" : "HeadAudioSource ohne audioSource";
            }
            catch (Exception e)
            {
                _control = null;
                LookupError = Diag.Describe(e);
            }
            if (!_warned)
            {
                _warned = true;
                Log.Error("Speech output not available yet: " + LookupError + " (retrying every 5 s)");
            }
            return false;
        }
        public bool IsSpeaking { get { return _current != null; } }
        public int QueueLength { get { return _queue.Count; } }

        public float Volume
        {
            get { return _volume; }
            set
            {
                _volume = Mathf.Clamp01(value);
                if (_control != null) _control.volume = _volume;
            }
        }

        /// <summary>
        /// Adds an utterance (path below the VaM folder). interrupt=true stops current speech and
        /// drops the queue first. Returns an error message, or null.
        /// </summary>
        public string Enqueue(string id, string path, bool interrupt)
        {
            if (!Resolve()) return "No HeadAudioSource on this atom (" + LookupError + ")";
            if (string.IsNullOrEmpty(path)) return "speak needs 'audio' (a file path below the VaM folder)";
            if (interrupt) StopAll("interrupted");
            _queue.Add(new Utterance { Id = id, Path = path });
            return null;
        }

        /// <summary>Stops current speech and cancels everything queued.</summary>
        public void StopAll(string reason)
        {
            for (int i = 0; i < _queue.Count; i++)
            {
                Release(_queue[i]);
                Fire(OnEnded, _queue[i].Id, "cancelled");
            }
            _queue.Clear();
            if (_current != null)
            {
                bool ours = _audio != null && (!_current.Started || _audio.clip == _current.StartedClip);
                if (ours && _control != null) _control.Stop();
                Finish(reason);
            }
        }

        public void Update(float deltaTime)
        {
            if (_retryIn > 0f) _retryIn -= deltaTime;
            if (!Resolve()) return;

            int limit = Math.Min(_queue.Count, Math.Max(1, PrefetchCount));
            for (int i = 0; i < limit; i++)
            {
                if (!_queue[i].Queued) Queue(_queue[i]);
            }

            if (_current != null) Track(deltaTime);

            if (_current == null && _queue.Count > 0 && _queue[0].Queued)
            {
                Utterance next = _queue[0];
                _queue.RemoveAt(0);
                if (next.Clip == null)
                {
                    Fire(OnError, next.Id, next.Error ?? "audio could not be queued");
                    Fire(OnEnded, next.Id, "failed");
                }
                else Play(next);
            }
        }

        private void Queue(Utterance u)
        {
            u.Queued = true;
            string url = SuperController.singleton.NormalizeMediaPath(u.Path);
            URLAudioClip queued = URLAudioClipManager.singleton.QueueClip(url);
            if (queued == null)
            {
                u.Error = "could not queue " + u.Path;
                return;
            }
            u.Clip = URLAudioClipManager.singleton.GetClip(queued.uid);
            if (u.Clip == null) u.Error = "no clip registered for " + u.Path;
        }

        private void Play(Utterance u)
        {
            _current = u;
            u.PreviousClip = _audio.clip;
            _control.volume = _volume;
            _control.PlayNow(u.Clip);
        }

        private void Track(float deltaTime)
        {
            Utterance u = _current;
            u.PlayTime += deltaTime;
            if (!u.Started)
            {
                AudioClip clip = _audio.clip;
                if (_audio.isPlaying && clip != null && clip != u.PreviousClip)
                {
                    u.Started = true;
                    u.StartedClip = clip;
                    if (OnStarted != null) OnStarted(u.Id, clip.length);
                    return;
                }
                if (u.PlayTime > StartTimeout)
                {
                    Fire(OnError, u.Id, "did not start playing within " + StartTimeout.ToString("0") + " s: " + u.Path);
                    Finish("failed");
                    return;
                }
                u.RetryTimer += deltaTime;
                if (u.RetryTimer >= RetryInterval)
                {
                    u.RetryTimer = 0f;
                    _control.PlayNow(u.Clip); // the clip may have still been loading
                }
                return;
            }
            if (_audio.clip != u.StartedClip) Finish("interrupted");
            else if (!_audio.isPlaying) Finish("completed");
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

        private static void Release(Utterance u)
        {
            if (u.Clip != null) URLAudioClipManager.singleton.RemoveClip(u.Clip);
            u.Clip = null;
        }
    }
}
