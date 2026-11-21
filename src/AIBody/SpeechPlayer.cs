// Speech output: a playback queue on the Person's head audio source.
//
// Each utterance is a WAV/OGG file below the VaM folder, written by the companion app into
// Custom/Sounds/AIBody/<channel>/ (or Saves/PluginData/AIBody/<channel>/audio/ after the app's
// automatic switch, or connection.paths.audio). Only VaM's own audio path is used, exactly as public
// sandboxed plugins do it (see docs/API_AUDIT.md for the evidence links):
//   - load:  URLAudioClipManager.singleton.QueueClip(SuperController.singleton.NormalizeMediaPath(path))
//            then URLAudioClipManager.singleton.GetClip(clip.uid)          (Dollmaster, FreeMMD)
//   - play:  the "HeadAudioSource" AudioSourceControl's PlayNow(namedClip) (Dollmaster), so VaM's
//            built-in lip sync follows it; Stop() and .audioSource            (FreeMMD); .volume (Dollmaster SFX)
//   - free:  URLAudioClipManager.singleton.RemoveClip(namedClip)           (Dollmaster SFX)
// Audio fix (21.11.2026, after version 40; Leon: audio never played in any version). Root cause analysis from first
// principles against the audited plugins (docs/API_AUDIT.md E36): "loaded" was taken as NamedAudioClip.sourceClip != null,
// but that only means Unity has read the WAV header (its length is known); the sample data can still be Unloaded or
// Loading, and an AudioSource with such a clip does not start (AudioSource.isPlaying stays false: Leon's log said
// "playing=False, clip=1.3 s long" for every file, the packaged test tone too). mmd2timeline calls
// sourceClip.LoadAudioData() and waits for loadState == Loaded; this player now does the same, uses the load sequence of
// Dollmaster / FreeMMD / mmd2timeline (GetClip(NormalizeLoadPath) for an already loaded clip, else QueueClip +
// GetClip(uid)), starts the clip ONCE with PlayNowClearQueue (FreeMMD) when it is Loaded, and only if it does not start
// tries PlayNow (Dollmaster) and the storable action "PlayNow" with the clip (MacGruber Breathe), one per second.
// Start detection: the head audio plays our clipToPlay (vam-timeline E33) or AudioSourceControl.playingClip is our
// clip (Dollmaster BreathController). With Verbose log on, every step is logged with the prefix "[audio]".
// Readiness (version 36, latency): PlayNow is called the moment the clip has loaded, i.e. when
// NamedAudioClip.sourceClip is no longer null (the check vam-timeline's CustomTrigger.cs makes, E33).
// Before, PlayNow ran right after QueueClip; a clip still loading did not start and the next try came
// 1 s later, so a first sentence could wait up to a second for nothing. If sourceClip never shows up
// (Since the audio fix there is no time cap: a clip is started only when its data is loaded, see above.)
// A clip counts as started when the head AudioSource (UnityEngine.AudioSource) is playing a new clip,
// and as finished when it stops.
// TODO(verify): on 1.22, that a Saves/PluginData relative path works with NormalizeMediaPath +
// QueueClip (the evidence loads paths picked in the file browser), and that PlayNow on a clip
// still loading is retried safely (start detection via AudioSource.isPlaying/clip).
//
// Utterances play strictly in order; the next ones are queued for loading while one plays.
//
// Status for the user (live status box): Status = "Loading: <file>" / "Speaking: <file> (2.3 s)" /
// "Done: <file>"; LastError = "Audio error: <reason>" with the step that failed (file missing,
// QueueClip, no head audio, clip never started), so a silent body shows where it breaks.
using System;
using System.Collections.Generic;
using MVR.FileManagementSecure;
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
            public string ShortError;        // short wording sent to the companion app (audio_failed)
            public bool WaitingForFile;      // the file was not visible yet when speak arrived: re-checked every frame batch
            public float WaitTime;           // seconds spent waiting for the file
            public float CheckTimer;         // time since the last FileExists check
            public bool Started;
            public AudioClip PreviousClip;   // what the head audio held before our PlayNow
            public AudioClip StartedClip;    // what it plays once our clip started
            public float PlayTime;
            public float RetryTimer;
            public int Plays;                // PlayNow calls (first + retries)
            public bool Reused;              // GetClip(NormalizeLoadPath(path)) found an already loaded clip: not ours to remove
            public float LoadTimer;          // time since the last LoadAudioData() call
            public string LastState = "";    // last logged readiness (Verbose log)
            public bool LoadFailed;          // sourceClip.loadState == Failed: Unity could not decode the file
        }

        private readonly Atom _atom;
        private AudioSourceControl _control;   // looked up lazily (Resolve), retried every 5 s
        private JSONStorable _storable;         // the same "HeadAudioSource" storable, for CallAction("PlayNow", clip) (E29)
        private AudioSource _audio;
        private float _retryIn;
        private bool _warned;
        private readonly List<Utterance> _queue = new List<Utterance>();
        private Utterance _current;
        private float _volume = 1f;

        /// <summary>Seconds to wait for a clip to start playing before reporting it as failed.</summary>
        public float StartTimeout = 15f;
        /// <summary>PlayNow is called again at this interval until the clip plays (it may still be loading).</summary>
        public float RetryInterval = 0.5f;
        /// <summary>A clip that was handed to the head audio but did not start gets the next play call after this time.</summary>
        public float PlayRetryInterval = 1f;

        /// <summary>Longest wait for sourceClip before PlayNow is tried anyway (fallback, old behaviour).</summary>
        public float ReadyWaitMax = 2f;   // unused since the audio fix (kept for old callers); readiness = loadState Loaded
        public int PrefetchCount = 2;
        /// <summary>While a speech file is not visible yet, FileExists is asked again at this interval (no sleeping).</summary>
        public float FileCheckInterval = 0.25f;

        /// <summary>(utteranceId, clipLengthSeconds)</summary>
        public Action<string, float> OnStarted;

        /// <summary>(utteranceId, reason): completed | stopped | interrupted | cancelled | failed</summary>
        public Action<string, string> OnEnded;

        /// <summary>(utteranceId, message)</summary>
        public Action<string, string> OnError;

        /// <summary>What the speech output does right now (for the status box).</summary>
        public string Status { get; private set; }

        /// <summary>The last audio error ("Audio error: ..."), null if none since start.</summary>
        public string LastError { get; private set; }
        private float _lastErrorAge;

        /// <summary>Seconds since LastError was set.</summary>
        public float LastErrorAge { get { return _lastErrorAge; } }

        private void SetError(string message)
        {
            LastError = "Audio error: " + message;
            _lastErrorAge = 0f;
            Status = LastError;
            Log.Error(LastError);
        }

        private static string FileName(string path)
        {
            if (string.IsNullOrEmpty(path)) return "(no path)";
            int slash = Math.Max(path.LastIndexOf('/'), path.LastIndexOf('\\'));
            return slash >= 0 ? path.Substring(slash + 1) : path;
        }

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
                _storable = _atom.GetStorableByID("HeadAudioSource");
                _control = _storable as AudioSourceControl;
                _audio = _control != null ? _control.audioSource : null;
                if (_audio != null)
                {
                    _control.volume = _volume;
                    LookupError = null;
                    if (_warned) Log.Info("HeadAudioSource found; speech output enabled.");
                    Log.Debug("[audio] head audio of '" + _atom.uid + "': HeadAudioSource found, " + SourceState());
                    return true;
                }
                LookupError = _control == null ? "this atom has no 'HeadAudioSource' (is the plugin on a Person atom?)" : "the head audio source has no audio output yet (the character may still be loading)";
            }
            catch (Exception e)
            {
                _control = null;
                LookupError = Diag.Describe(e);
            }
            if (!_warned)
            {
                _warned = true;
                Log.Error("The character cannot speak yet: " + LookupError + ". The plugin keeps trying every 5 s; it must sit on a Person atom with head audio.");
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
            if (!Resolve())
            {
                string why = "The character has no head audio (HeadAudioSource), so it cannot speak: " + LookupError + ". Add AIBody to a Person atom.";
                SetError(why);
                return "The character has no head audio (HeadAudioSource): " + LookupError;
            }
            if (string.IsNullOrEmpty(path))
            {
                SetError("The companion app sent a speak command without an audio file. This is a bug in the app; see its companion.log.");
                return "the speak command has no audio file path";
            }
            // Plain paths below the VaM folder can be checked (E10); package paths ("pkg:/...") cannot.
            // A check that throws (folder the sandbox does not let us look into) does not block loading.
            bool missing = false;
            if (path.IndexOf(':') < 0)
            {
                try { missing = !FileManagerSecure.FileExists(path); }
                catch (Exception e) { Log.Debug("FileExists(" + path + ") failed: " + e.Message + " – loading anyway"); }
            }
            // The companion app writes the WAV completely (temp name, fsync, rename) BEFORE it writes the
            // speak command, so a visible command normally means a ready file. If the file is not visible
            // yet anyway (slow disk, another VaM folder), the utterance stays queued and Update asks again
            // each time FileCheckInterval has passed; an error comes only after StartTimeout.
            if (interrupt) StopAll("interrupted");
            _queue.Add(new Utterance { Id = id, Path = path, WaitingForFile = missing });
            if (missing) Log.Debug("Audio file not visible yet, waiting for it: " + path);
            if (_current == null) Status = (missing ? "Waiting for file: " : "Loading: ") + FileName(path);
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
            _lastErrorAge += deltaTime;
            if (_retryIn > 0f) _retryIn -= deltaTime;
            if (!Resolve()) return;

            int limit = Math.Min(_queue.Count, Math.Max(1, PrefetchCount));
            for (int i = 0; i < limit; i++)
            {
                Utterance u = _queue[i];
                if (u.Queued) continue;
                if (u.WaitingForFile && !FileReady(u, deltaTime)) continue;
                Queue(u);
            }

            if (_current != null) Track(deltaTime);

            if (_current == null && _queue.Count > 0 && _queue[0].Queued)
            {
                Utterance next = _queue[0];
                _queue.RemoveAt(0);
                if (next.Clip == null)
                {
                    SetError((next.Error ?? "VaM could not load the audio file") + " File: " + next.Path);
                    Fire(OnError, next.Id, next.ShortError ?? next.Error ?? "VaM could not load the audio file");
                    Fire(OnEnded, next.Id, "failed");
                }
                else Play(next);
            }
        }

        /// <summary>
        /// Readiness signal for a speech file that was not visible when speak arrived: asks FileExists
        /// (E10) again each FileCheckInterval, driven by Update (no sleeping). After StartTimeout the
        /// utterance fails with a clear message (it is marked queued with an error, which the normal
        /// failure path reports). Returns true once the file can be loaded.
        /// </summary>
        private bool FileReady(Utterance u, float deltaTime)
        {
            u.WaitTime += deltaTime;
            u.CheckTimer += deltaTime;
            if (u.CheckTimer >= FileCheckInterval)
            {
                u.CheckTimer = 0f;
                try { if (FileManagerSecure.FileExists(u.Path)) { u.WaitingForFile = false; return true; } }
                catch (Exception e) { Log.Debug("FileExists(" + u.Path + ") failed: " + e.Message + " - loading anyway"); u.WaitingForFile = false; return true; }
            }
            if (u.WaitTime > StartTimeout)
            {
                u.Queued = true;
                u.Error = "Audio file not found after waiting " + StartTimeout.ToString("0") + " s. The companion app writes speech files into "
                    + "the VaM folder it was started with: make sure its --vam-root is the VaM folder you start VaM from.";
                u.ShortError = "audio file not found after " + StartTimeout.ToString("0") + " s: " + u.Path;
            }
            return false;
        }

        private void Queue(Utterance u)
        {
            u.Queued = true;
            try
            {
                // Already loaded (same file played before)? Dollmaster L295-296, FreeMMD L318-319, mmd2timeline L194-195.
                NamedAudioClip existing = URLAudioClipManager.singleton.GetClip(SuperController.singleton.NormalizeLoadPath(u.Path));
                if (existing != null)
                {
                    u.Clip = existing;
                    u.Reused = true;
                    Log.Debug("[audio] " + u.Id + ": clip already loaded, reused (" + u.Path + ")");
                    return;
                }
                string url = SuperController.singleton.NormalizeMediaPath(u.Path);
                URLAudioClip queued = URLAudioClipManager.singleton.QueueClip(url);
                if (queued == null)
                {
                    u.Error = "VaM would not load the audio file '" + url + "'. Check that the file exists in that folder and is a normal WAV; the companion app then tries its other audio folder.";
                    return;
                }
                u.Clip = URLAudioClipManager.singleton.GetClip(queued.uid);
                Log.Debug("[audio] " + u.Id + ": QueueClip(" + url + ") -> uid " + queued.uid + (u.Clip == null ? ", GetClip returned null" : ""));
                if (u.Clip == null) u.Error = "VaM loaded the audio file but could not find the clip afterwards (clip id " + queued.uid + "). Press 'Play test tone' again; if it keeps failing, restart VaM.";
            }
            catch (Exception e)
            {
                u.Error = "Loading the audio file failed: " + Diag.Describe(e) + ". Check that the file exists and is a normal WAV.";
            }
        }

        private void Play(Utterance u)
        {
            _current = u;
            u.PreviousClip = _audio.clip;
            _control.volume = _volume;
            Status = "Loading: " + FileName(u.Path) + (_volume < 0.01f ? " (note: Speech volume is 0)" : "");
            if (ClipReady(u, 0f)) PlayNow(u);   // else Track() calls it the frame the clip data has loaded
        }

        /// <summary>
        /// First try PlayNowClearQueue (FreeMMD L176: nothing queued on the head audio delays our clip), then, if the clip
        /// still does not play, PlayNow (Dollmaster L246) and the storable action "PlayNow" with the clip (Breathe L209) in turn.
        /// </summary>
        private void PlayNow(Utterance u)
        {
            u.Plays++;
            u.RetryTimer = 0f;
            string how;
            if (u.Plays == 1) { _control.PlayNowClearQueue(u.Clip); how = "PlayNowClearQueue"; }
            else if (u.Plays % 2 == 0) { _control.PlayNow(u.Clip); how = "PlayNow"; }
            else if (_storable != null) { _storable.CallAction("PlayNow", u.Clip); how = "CallAction(\"PlayNow\", clip)"; }
            else { _control.PlayNow(u.Clip); how = "PlayNow"; }
            Log.Debug("[audio] " + u.Id + ": " + how + " (try " + u.Plays + ") -> " + SourceState() + ", " + ClipState(u.Clip));
        }

        /// <summary>
        /// True once the clip's audio DATA is loaded: sourceClip set (E33) and sourceClip.loadState == Loaded (E36,
        /// mmd2timeline L168-185). Unloaded: LoadAudioData() is asked again every RetryInterval. Failed: the error says so.
        /// A check that throws counts as ready (the old behaviour).
        /// </summary>
        private bool ClipReady(Utterance u, float deltaTime)
        {
            string state;
            bool ready;
            try
            {
                if (u.Clip == null) return false;
                AudioClip source = u.Clip.sourceClip;
                if (source == null) { state = "header not loaded yet (sourceClip null)"; ready = false; }
                else
                {
                    AudioDataLoadState load = source.loadState;
                    state = "loadState " + load;
                    ready = load == AudioDataLoadState.Loaded;
                    if (load == AudioDataLoadState.Unloaded)
                    {
                        u.LoadTimer += deltaTime;
                        if (u.LoadTimer >= RetryInterval || u.LastState.Length == 0)
                        {
                            u.LoadTimer = 0f;
                            source.LoadAudioData();
                            state += ", LoadAudioData() called";
                        }
                    }
                    else if (load == AudioDataLoadState.Failed)
                    {
                        u.LoadFailed = true;
                    }
                }
            }
            catch (Exception e)
            {
                state = "check failed (" + e.Message + "), trying to play anyway";
                ready = true;
            }
            if (state != u.LastState)
            {
                u.LastState = state;
                Log.Debug("[audio] " + u.Id + ": " + state);
            }
            return ready;
        }

        /// <summary>One line about the head AudioSource for the [audio] debug lines and the error text.</summary>
        private string SourceState()
        {
            if (_audio == null) return "head AudioSource missing";
            string text = "head audio playing=" + _audio.isPlaying;
            try
            {
                AudioClip clip = _audio.clip;
                text += ", clip=" + (clip != null ? clip.length.ToString("0.00") + " s, " + clip.loadState : "none")
                    + ", time=" + _audio.time.ToString("0.00")
                    + ", enabled=" + _audio.enabled + ", active=" + _audio.gameObject.activeInHierarchy
                    + ", playingClip=" + (_control.playingClip == null ? "none" : _control.playingClip.uid)
                    + ", volume=" + _control.volume.ToString("0.00");
            }
            catch (Exception e) { text += " (" + e.Message + ")"; }
            return text;
        }

        private static string ClipState(NamedAudioClip c)
        {
            if (c == null) return "clip none";
            try
            {
                return "clip " + c.uid + ": sourceClip=" + (c.sourceClip == null ? "null" : c.sourceClip.length.ToString("0.00") + " s " + c.sourceClip.loadState)
                    + ", clipToPlay=" + (c.clipToPlay == null ? "null" : "set");
            }
            catch (Exception e) { return "clip state unknown (" + e.Message + ")"; }
        }

        /// <summary>Our clip is on the head audio and playing (E33 compare, E36 playingClip).</summary>
        private bool OursPlaying(Utterance u)
        {
            if (!_audio.isPlaying || u.Clip == null) return false;
            AudioClip clip = _audio.clip;
            if (clip == null) return false;
            if (clip == u.Clip.clipToPlay || clip == u.Clip.sourceClip) return true;
            if (_control.playingClip == u.Clip) return true;
            return clip != u.PreviousClip;   // the old test (a new clip is playing)
        }

        private void Track(float deltaTime)
        {
            Utterance u = _current;
            u.PlayTime += deltaTime;
            if (!u.Started)
            {
                AudioClip clip = _audio.clip;
                if (u.Plays > 0 && OursPlaying(u))
                {
                    u.Started = true;
                    u.StartedClip = clip;
                    Status = "Speaking: " + FileName(u.Path) + " (" + clip.length.ToString("0.0") + " s"
                        + (_volume < 0.01f ? ", Speech volume is 0 – nothing audible" : "") + ")";
                    Log.Debug("[audio] " + u.Id + ": playing (" + clip.length.ToString("0.0") + " s, " + u.Plays + " play call(s), " + u.PlayTime.ToString("0.00") + " s after the start)");
                    if (OnStarted != null) OnStarted(u.Id, clip.length);
                    return;
                }
                if (u.LoadFailed)
                {
                    SetError("Unity could not decode the audio file " + u.Path + " (loadState Failed). It must be a normal PCM WAV; "
                        + "see the companion log for how it was written. (" + ClipState(u.Clip) + ")");
                    Fire(OnError, u.Id, "audio data could not be loaded (loadState Failed): " + u.Path);
                    Finish("failed");
                    return;
                }
                if (u.PlayTime > StartTimeout)
                {
                    SetError("The audio did not start playing within " + StartTimeout.ToString("0") + " s (" + u.Plays
                        + " play calls): " + u.Path + ". " + (u.Plays == 0 ? "Its audio data never finished loading. " : "")
                        + "Check that it is a valid WAV, that the character's head audio is not muted or blocked, that VaM's "
                        + "Freeze Motion/Sound is off, and that Speech volume (tab AI Character) is above 0. Switch on Verbose log "
                        + "(tab Config) for the [audio] lines. (" + SourceState() + "; " + ClipState(u.Clip) + ".)");
                    Fire(OnError, u.Id, "did not start playing within " + StartTimeout.ToString("0") + " s: " + u.Path);
                    Finish("failed");
                    return;
                }
                if (u.Plays == 0)
                {
                    // Not handed to the head audio yet: start it the frame the clip DATA is loaded (no time cap any more:
                    // playing a clip whose data is not loaded is exactly what never started).
                    if (ClipReady(u, deltaTime)) PlayNow(u);
                    return;
                }
                u.RetryTimer += deltaTime;
                if (u.RetryTimer >= PlayRetryInterval) PlayNow(u);   // it did not start: the next of the three evidenced calls
                return;
            }
            if (_audio.clip != u.StartedClip) Finish("interrupted");
            else if (!_audio.isPlaying) Finish("completed");
        }

        private void Finish(string reason)
        {
            Utterance done = _current;
            _current = null;
            if (reason != "failed") Status = (reason == "completed" ? "Done: " : "Cancelled (" + reason + "): ") + FileName(done.Path);
            Release(done);
            Log.Debug("End " + done.Id + ": " + reason);
            Fire(OnEnded, done.Id, reason);
        }

        private static void Fire(Action<string, string> cb, string a, string b)
        {
            if (cb != null) cb(a, b);
        }

        private static void Release(Utterance u)
        {
            // A clip found with GetClip(path) belongs to whoever loaded it first (e.g. a scene's audio): not removed.
            if (u.Clip != null && !u.Reused) URLAudioClipManager.singleton.RemoveClip(u.Clip);
            u.Clip = null;
        }
    }
}
