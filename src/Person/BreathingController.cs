// Simple procedural breathing: a sine wave on a configurable chest morph plus an optional
// tiny head bob. For realistic breathing (chest physics, breast motion, sounds) use
// MacGruber's "Life" plugin on the same atom and drive it through the "trigger" command;
// this controller is a dependency free fallback.
using System;
using UnityEngine;

namespace AIBody
{
    public class BreathingController
    {
        private readonly MorphHelper _morphs;
        private DAZMorph _morph;
        private string _morphName;
        private float _baseValue;
        private float _phase;
        private float _currentDepth;

        public bool Enabled = true;

        /// <summary>Breaths per minute at rest.</summary>
        public float Rate = 14f;

        /// <summary>Peak morph value added at full inhale.</summary>
        public float Depth = 0.35f;

        /// <summary>Depth multiplier while speaking (speech takes over the breathing rhythm).</summary>
        public float SpeakingDepthFactor = 0.3f;

        public BreathingController(MorphHelper morphs, string morphName)
        {
            _morphs = morphs;
            SetMorph(morphName);
        }

        public string MorphName { get { return _morphName; } }

        /// <summary>
        /// TODO(verify): there is no single standard "breath" morph in stock VaM. Pick a chest
        /// expansion morph available on the character (or one from a morph pack) in the UI.
        /// </summary>
        public void SetMorph(string morphName)
        {
            RestoreNow();
            _morphName = morphName;
            _morph = _morphs.Find(morphName);
            if (_morph != null) _baseValue = _morph.morphValue;
        }

        public void RestoreNow()
        {
            if (_morph != null) _morph.morphValue = _baseValue;
        }

        public void Update(float deltaTime, bool speaking)
        {
            float targetDepth = Enabled ? Depth * (speaking ? SpeakingDepthFactor : 1f) : 0f;
            _currentDepth = Mathf.MoveTowards(_currentDepth, targetDepth, deltaTime * 0.5f);
            if (_morph == null) return;
            if (!Enabled && _currentDepth <= 0f)
            {
                _morph.morphValue = _baseValue;
                return;
            }

            _phase += deltaTime * Mathf.Max(1f, Rate) / 60f;
            if (_phase > 1f) _phase -= 1f;
            // Inhale is slightly faster than exhale: shape the sine a little.
            float s = 0.5f - 0.5f * Mathf.Cos(_phase * Mathf.PI * 2f);
            s = Mathf.Pow(s, 1.3f);
            _morph.morphValue = _baseValue + s * _currentDepth;
        }

        /// <summary>Current breathing cycle position 0..1 (0 = exhaled). Used for the head bob.</summary>
        public float Cycle
        {
            get { return 0.5f - 0.5f * Mathf.Cos(_phase * Mathf.PI * 2f); }
        }

        public float CurrentDepth { get { return _currentDepth; } }
    }
}
