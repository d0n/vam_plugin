// Plays TTS audio through the Person's HeadAudioSource. VaM's built-in LipSync on the
// Person atom listens to HeadAudioSource, so lip sync comes for free (keep it enabled).
using System;
using System.Collections;
using UnityEngine;

namespace AIBody
{
    public class AudioController
    {
        private readonly MonoBehaviour _host;
        private readonly AudioSourceControl _source;
        private NamedAudioClip _currentClip;
        private string _currentId;
        private string _pendingId;
        private Coroutine _loadRoutine;

        /// <summary>Seconds to wait for a clip to load before giving up.</summary>
        public float LoadTimeout = 15f;

        public AudioController(MonoBehaviour host, Atom atom)
        {
            _host = host;
            _source = atom.GetStorableByID("HeadAudioSource") as AudioSourceControl;
            if (_source == null) Log.Error("No HeadAudioSource on atom " + atom.uid + "; speech output disabled.");
        }

        public bool Available { get { return _source != null; } }

        /// <summary>Id of the utterance currently playing (or loading), else null.</summary>
        public string CurrentId { get { return _currentId ?? _pendingId; } }

        /// <summary>True while the head audio source is actually producing sound.</summary>
        public bool IsPlaying
        {
            get
            {
                // AudioSourceControl wraps a Unity AudioSource.
                return _source != null && _source.audioSource != null && _source.audioSource.isPlaying;
            }
        }

        /// <summary>
        /// Loads an audio file (path relative to the VaM folder, e.g.
        /// "Saves/PluginData/AIBody/Person/audio/utt-1.wav") and plays it immediately,
        /// interrupting anything that is playing. onError is called if loading fails.
        /// </summary>
        public void Play(string id, string path, Action<string, string> onError)
        {
            if (_source == null)
            {
                if (onError != null) onError(id, "No HeadAudioSource on this atom.");
                return;
            }
            Stop();
            _pendingId = id;
            _loadRoutine = _host.StartCoroutine(LoadAndPlay(id, path, onError));
        }

        public void Stop()
        {
            if (_loadRoutine != null)
            {
                _host.StopCoroutine(_loadRoutine);
                _loadRoutine = null;
            }
            _pendingId = null;
            if (_source != null) _source.Stop();
            ReleaseClip();
            _currentId = null;
        }

        /// <summary>Called by the state reporter once playback finished.</summary>
        public void OnPlaybackFinished()
        {
            ReleaseClip();
            _currentId = null;
        }

        private IEnumerator LoadAndPlay(string id, string path, Action<string, string> onError)
        {
            // URLAudioClipManager loads the file asynchronously and owns the clip afterwards.
            // TODO(verify): QueueClip accepts a path relative to the VaM folder on 1.22; if not,
            // prefix with the absolute VaM path or use SuperController.singleton.NormalizeMediaPath.
            NamedAudioClip clip = URLAudioClipManager.singleton.QueueClip(path);
            if (clip == null)
            {
                _pendingId = null;
                if (onError != null) onError(id, "Could not queue audio clip: " + path);
                yield break;
            }

            float waited = 0f;
            while (!IsClipReady(clip))
            {
                waited += Time.unscaledDeltaTime;
                if (waited > LoadTimeout)
                {
                    _pendingId = null;
                    RemoveClip(clip);
                    if (onError != null) onError(id, "Timed out loading audio: " + path);
                    yield break;
                }
                yield return null;
            }

            _currentClip = clip;
            _currentId = id;
            _pendingId = null;
            _loadRoutine = null;
            _source.PlayNow(clip);
        }

        // Isolated because the exact "loaded" field differs between VaM builds.
        // TODO(verify): NamedAudioClip.clipToPlay is null until the URL clip finished loading.
        private static bool IsClipReady(NamedAudioClip clip)
        {
            return clip.clipToPlay != null;
        }

        private void ReleaseClip()
        {
            if (_currentClip != null)
            {
                RemoveClip(_currentClip);
                _currentClip = null;
            }
        }

        private static void RemoveClip(NamedAudioClip clip)
        {
            // Remove from the scene's audio clip list so utterances do not pile up in the scene.
            URLAudioClip urlClip = clip as URLAudioClip;
            if (urlClip != null) URLAudioClipManager.singleton.RemoveClip(urlClip);
        }
    }
}
