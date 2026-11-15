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

        private readonly AudioSourceControl _control;
        private readonly AudioSource _audio;
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
            _control = atom.GetStorableByID("HeadAudioSource") as AudioSourceControl;
            if (_control != null) _audio = _control.audioSource;
            if (_audio == null) Log.Error("No HeadAudioSource on atom " + atom.uid + "; speech output disabled.");
        }

        public bool Available { get { return _audio != null; } }
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
            if (_audio == null) return "No HeadAudioSource on this atom";
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
                bool ours = !_current.Started || _audio.clip == _current.StartedClip;
                if (ours) _control.Stop();
                Finish(reason);
            }
        }

        public void Update(float deltaTime)
        {
            if (_audio == null) return;

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
