// Watches the speech audio and reports speech_started / speech_ended to the companion.
// The companion uses these events to gate its microphone (echo suppression).
using System;
using SimpleJSON;

namespace AIBody
{
    public class StateReporter
    {
        private readonly AudioController _audio;
        private readonly Action<JSONClass> _send;
        private bool _speaking;
        private string _speakingId;
        private float _silenceTimer;
        private bool _stopRequested;

        /// <summary>
        /// Audio must be silent this long before speech_ended fires. Bridges the gap between
        /// loading and playing and very short dropouts.
        /// </summary>
        public float EndGrace = 0.15f;

        public StateReporter(AudioController audio, Action<JSONClass> send)
        {
            _audio = audio;
            _send = send;
        }

        public bool IsSpeaking { get { return _speaking; } }

        /// <summary>Marks the next end as "stopped" instead of "completed".</summary>
        public void NotifyStopRequested()
        {
            _stopRequested = true;
        }

        public void Update(float deltaTime)
        {
            bool playing = _audio.IsPlaying;
            if (playing)
            {
                _silenceTimer = 0f;
                if (!_speaking)
                {
                    _speaking = true;
                    _speakingId = _audio.CurrentId;
                    _stopRequested = false;
                    JSONClass evt = Protocol.NewEvent(Protocol.EvtSpeechStarted);
                    evt["utterance_id"] = _speakingId ?? "";
                    _send(evt);
                }
                else if (_audio.CurrentId != null && _audio.CurrentId != _speakingId)
                {
                    // A new utterance interrupted the previous one without a silent frame.
                    Finish("interrupted");
                    Update(0f);
                }
                return;
            }

            if (!_speaking)
            {
                _stopRequested = false;
                return;
            }
            _silenceTimer += deltaTime;
            if (_silenceTimer >= EndGrace || _stopRequested)
            {
                Finish(_stopRequested ? "stopped" : "completed");
                _audio.OnPlaybackFinished();
            }
        }

        private void Finish(string reason)
        {
            JSONClass evt = Protocol.NewEvent(Protocol.EvtSpeechEnded);
            evt["utterance_id"] = _speakingId ?? "";
            evt["reason"] = reason;
            _send(evt);
            _speaking = false;
            _speakingId = null;
            _silenceTimer = 0f;
            _stopRequested = false;
        }
    }
}
