// Blinking: AIBody takes over the blinks of this Person (optional, off by default).
//
// VaM has its own automatic blinking (storable "EyelidControl", bool parameter "blinkEnabled").
// While "Blink control" is on, AIBody switches that off and drives the morph "Eyes Closed" itself:
// the same two steps MacGruber's Eyes plugin does (it switches autoBlink off and sets the morph,
// E29 L34-41, L53, L87). The blinks are irregular (every 2.5 to 7 s, sometimes a double blink),
// more frequent while speaking, and a blink is added when the eyes make a larger move (a glance
// away), as people do. Everything is undone when AIBody lets go: autoBlink gets its old value
// back and the morph its old value.
//
// Coexistence: if MacGruber's Life Eyes plugin (class MacGruber.Eyes, E29 L11-13) or Glance is on this
// Person, or if someone else switches "blinkEnabled" on again while AIBody blinks, AIBody stops and
// leaves the eyelids alone (menu: toggling "Blink control" takes them again).
using System;
using System.Collections.Generic;
using UnityEngine;

namespace AIBody
{
    public class BlinkController
    {
        /// <summary>Display name of the closing morph (E29 L38, stock VaM female and male).</summary>
        public const string MorphName = "Eyes Closed";

        private const float CloseSeconds = 0.07f;
        private const float HoldSeconds = 0.04f;
        private const float OpenSeconds = 0.12f;

        private readonly Atom _atom;
        private readonly MorphHelper _morphs;
        private DAZMorph _morph;
        private JSONStorableBool _autoBlink;
        private float _resolveIn;

        private bool _enabled;
        private bool _taken;
        private bool _yielded;
        private bool _autoWas;
        private float _baseValue;
        private string _otherPlugin = "";
        private float _otherCheckIn;
        private string _status = "off";

        private float _nextIn = 3f;
        private float _phase = -1f;     // seconds since the blink started; < 0 = no blink running
        private int _doubleLeft;

        public BlinkController(Atom atom, MorphHelper morphs)
        {
            _atom = atom;
            _morphs = morphs;
        }

        public string Status { get { return _status; } }

        public bool Enabled
        {
            get { return _enabled; }
            set
            {
                _enabled = value;
                _yielded = false;   // picking the switch again takes the eyelids again
                if (!value) Release();
            }
        }

        /// <summary>True while AIBody is blinking (switch on, nothing else on the eyelids).</summary>
        public bool Active { get { return _enabled && _taken && !_yielded; } }

        /// <summary>A blink soon (a glance away starts or ends, speech starts). Ignored when a blink just ran.</summary>
        public void RequestBlink()
        {
            if (!Active || _phase >= 0f) return;
            if (_nextIn > 0.25f) _nextIn = 0.05f;
        }

        public void Update(float dt, bool speaking)
        {
            if (!_enabled) { _status = "off (VaM's own blinking is unchanged)"; return; }
            _otherCheckIn -= dt;
            if (_otherCheckIn <= 0f)
            {
                _otherCheckIn = 3f;
                _otherPlugin = FindOtherBlinkPlugin();
            }
            if (_otherPlugin.Length > 0)
            {
                Release();
                _status = "paused: " + _otherPlugin + " is on this Person and controls the eyelids";
                return;
            }
            if (_yielded) { Release(); _status = "stopped: someone switched VaM's auto blink on again. Toggle 'Blink control' to take over again"; return; }
            if (!Resolve(dt)) { _status = "not available (no EyelidControl or morph '" + MorphName + "' on this Person)"; return; }

            if (!_taken)
            {
                _baseValue = _morph.morphValue;
                _autoWas = _autoBlink.val;     // E29 L41
                _autoBlink.val = false;        // E29 L65 (autoBlink.val = false)
                _taken = true;
            }
            else if (_autoBlink.val)
            {
                // Someone switched the automatic blinking on again: do not fight, give the eyelids back.
                _taken = false;
                _yielded = true;
                _morph.morphValue = _baseValue;
                return;
            }

            if (_phase >= 0f)
            {
                _phase += dt;
                float total = CloseSeconds + HoldSeconds + OpenSeconds;
                float v;
                if (_phase < CloseSeconds) v = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(_phase / CloseSeconds));
                else if (_phase < CloseSeconds + HoldSeconds) v = 1f;
                else v = Mathf.SmoothStep(1f, 0f, Mathf.Clamp01((_phase - CloseSeconds - HoldSeconds) / OpenSeconds));   // E29 L87
                _morph.morphValue = _baseValue + (1f - _baseValue) * v;
                if (_phase >= total)
                {
                    _phase = -1f;
                    _morph.morphValue = _baseValue;
                    _nextIn = _doubleLeft > 0 ? 0.22f : NextInterval(speaking);
                    if (_doubleLeft > 0) _doubleLeft--;
                }
                _status = "blinking by AIBody (VaM auto blink is off)";
                return;
            }

            _nextIn -= dt;
            if (_nextIn <= 0f)
            {
                _phase = 0f;
                if (_doubleLeft == 0 && UnityEngine.Random.Range(0f, 1f) < 0.15f) _doubleLeft = 1;
            }
            _status = "blinking by AIBody (VaM auto blink is off)";
        }

        private static float NextInterval(bool speaking)
        {
            return speaking ? UnityEngine.Random.Range(2.5f, 5.5f) : UnityEngine.Random.Range(3f, 7f);
        }

        private bool Resolve(float dt)
        {
            if (_morph != null && _autoBlink != null) return true;
            _resolveIn -= dt;
            if (_resolveIn > 0f) return false;
            _resolveIn = 5f;
            try
            {
                if (_morph == null && _morphs != null) _morph = _morphs.Find(MorphName);                 // E29 L38
                if (_autoBlink == null)
                {
                    JSONStorable eyelids = _atom.GetStorableByID("EyelidControl");                       // E29 L40
                    if (eyelids != null) _autoBlink = eyelids.GetBoolJSONParam("blinkEnabled");          // E29 L41
                }
            }
            catch (Exception) { _morph = null; _autoBlink = null; }
            return _morph != null && _autoBlink != null;
        }

        /// <summary>Gives the eyelids back: the old morph value and the old automatic blinking.</summary>
        public void Release()
        {
            _phase = -1f;
            if (!_taken) return;
            _taken = false;
            if (_morph != null) _morph.morphValue = _baseValue;
            if (_autoBlink != null && !_yielded) _autoBlink.val = _autoWas;
        }

        public void RestoreNow() { Release(); }

        /// <summary>"Life (MacGruber Eyes)" or "Glance" when one of them is on this Person.</summary>
        private string FindOtherBlinkPlugin()
        {
            try
            {
                List<string> ids = _atom.GetStorableIDs();   // E8, E28
                if (ids == null) return "";
                for (int i = 0; i < ids.Count; i++)
                {
                    if (ids[i].EndsWith("Glance")) return "Glance";
                    if (ids[i].IndexOf("MacGruber") >= 0 && ids[i].EndsWith("Eyes")) return "Life (MacGruber Eyes)";
                }
            }
            catch (Exception) { }
            return "";
        }
    }
}
