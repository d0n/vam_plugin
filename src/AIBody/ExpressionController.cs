// Facial expressions as named presets of morph targets, blended over time.
//
// Presets come from built-in defaults and can be overridden/extended by
// Saves/PluginData/AIBody/expressions.json (see examples/expressions.json):
//   { "happy": { "Mouth Smile Simple": 0.6, "Brow Inner Up": 0.2 }, ... }
//
// NOTE: morph display names differ between characters and installed morph packs.
// The defaults below are common VaM 1.x expression morphs but must be checked in the
// Morphs tab of the target character; unknown morphs are logged once and skipped.
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;
using MVR.FileManagementSecure;

namespace AIBody
{
    public class ExpressionController
    {
        private readonly MorphBlendLayer _layer;
        private readonly Dictionary<string, Dictionary<string, float>> _presets =
            new Dictionary<string, Dictionary<string, float>>(StringComparer.OrdinalIgnoreCase);
        private string _current = "neutral";
        private float _holdRemaining = -1f;
        private bool _releasePending;   // version 66: showing ends when the fade back has finished (Auto Expressions stay paused until then)

        public ExpressionController(MorphHelper morphs)
        {
            _layer = new MorphBlendLayer(morphs);
            LoadDefaults();
        }

        public string Current { get { return _current; } }

        /// <summary>Version 53: true while an expression (not neutral) is shown; Body pauses VaM's Auto Expressions meanwhile.</summary>
        public Action<bool> OnShowingChanged;
        private bool _showing;

        /// <summary>Version 53: what the last SetExpression found ("2 of 2 morphs"), (kept for the log / tests; the Show expression button is gone since version 66).</summary>
        public string LastResult { get; private set; }

        /// <summary>Names for the menu (version 53): the visible expressions first in a fixed order, then the others,
        /// "listening" and "neutral" last, so the menu never starts on an expression that shows nothing.</summary>
        public IEnumerable<string> PresetNames
        {
            get
            {
                List<string> names = new List<string>();
                foreach (string n in MenuOrder) if (_presets.ContainsKey(n)) names.Add(n);
                foreach (KeyValuePair<string, Dictionary<string, float>> kv in _presets)   // not the key collection (CS584)
                    if (!ContainsIgnoreCase(names, kv.Key) && !IsQuiet(kv.Key)) names.Add(kv.Key);
                foreach (string n in new[] { "listening", "neutral" })
                    if (_presets.ContainsKey(n) && !ContainsIgnoreCase(names, n)) names.Add(n);
                return names;
            }
        }

        private static readonly string[] MenuOrder = { "happy", "smile", "sad", "angry", "surprised", "thinking" };

        private static bool IsQuiet(string name)
        {
            return string.Equals(name, "neutral", StringComparison.OrdinalIgnoreCase) || string.Equals(name, "listening", StringComparison.OrdinalIgnoreCase);
        }

        private static bool ContainsIgnoreCase(List<string> list, string name)
        {
            for (int i = 0; i < list.Count; i++) if (string.Equals(list[i], name, StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        public int PresetCount { get { return _presets.Count; } }

        /// <summary>Every morph name used by a preset, once (self test: which ones the character has).</summary>
        public List<string> MorphNames
        {
            get
            {
                // Iterate the dictionaries themselves (KeyValuePair): VaM's compiler fails with CS584 on
                // the nested key/value collection enumerators (version 13 did not compile in VaM).
                List<string> names = new List<string>();
                foreach (KeyValuePair<string, Dictionary<string, float>> preset in _presets)
                    foreach (KeyValuePair<string, float> morph in preset.Value)
                        if (!names.Contains(morph.Key)) names.Add(morph.Key);
                return names;
            }
        }

        private void LoadDefaults()
        {
            // TODO(verify): morph names against a stock VaM 1.22 female and male character.
            _presets["neutral"] = new Dictionary<string, float>();
            _presets["happy"] = Preset("Mouth Smile Simple", 0.7f, "Brow Inner Up", 0.15f);
            _presets["smile"] = Preset("Mouth Smile Simple", 0.4f);
            _presets["sad"] = Preset("Mouth Frown", 0.5f, "Brow Inner Up", 0.6f);
            _presets["angry"] = Preset("Brow Down", 0.7f, "Mouth Frown", 0.3f);
            _presets["surprised"] = Preset("Brow Outer Up Left", 0.7f, "Brow Outer Up Right", 0.7f, "Mouth Open", 0.3f);
            // version 66: symmetric and mild (up to v65 one brow down and a one-sided mouth, which looked skeptical)
            _presets["thinking"] = Preset("Brow Inner Up", 0.2f, "Brow Outer Up Left", 0.1f, "Brow Outer Up Right", 0.1f);
            // Version 27: very small "listening" face the companion app shows while the user talks (not offered to the AI).
            _presets["listening"] = Preset("Brow Inner Up", 0.18f, "Mouth Smile Simple", 0.08f);
        }

        private static Dictionary<string, float> Preset(params object[] pairs)
        {
            Dictionary<string, float> d = new Dictionary<string, float>();
            for (int i = 0; i + 1 < pairs.Length; i += 2) d[(string)pairs[i]] = Convert.ToSingle(pairs[i + 1]);
            return d;
        }

        /// <summary>Loads optional preset overrides from a JSON file. Missing file is fine.</summary>
        public void LoadPresetFile(string path)
        {
            try
            {
                if (!FileManagerSecure.FileExists(path)) return;
                JSONClass root = JSON.Parse(FileManagerSecure.ReadAllText(path)) as JSONClass;
                if (root == null)
                {
                    Log.Error("Invalid expressions file: " + path);
                    return;
                }
                int count = 0;
                foreach (KeyValuePair<string, JSONNode> kv in root)
                {
                    JSONClass morphs = kv.Value as JSONClass;
                    if (morphs == null) continue;
                    _presets[kv.Key] = ToFloatMap(morphs);
                    count++;
                }
                Log.Info("Loaded " + count + " expression presets from " + path);
            }
            catch (Exception e)
            {
                Log.Error("Failed to load expressions from " + path, e);
            }
        }

        public static Dictionary<string, float> ToFloatMap(JSONClass obj)
        {
            Dictionary<string, float> d = new Dictionary<string, float>();
            foreach (KeyValuePair<string, JSONNode> kv in obj) d[kv.Key] = kv.Value.AsFloat;
            return d;
        }

        /// <summary>
        /// Blends to a preset. intensity scales all values (0..1+), blendTime is seconds to
        /// reach the target, hold > 0 returns to neutral after that many seconds.
        /// </summary>
        public bool SetExpression(string name, float intensity, float blendTime, float hold)
        {
            Dictionary<string, float> preset;
            if (!_presets.TryGetValue(name ?? "", out preset)) return false;
            List<string> missing = ApplyTargets(preset, intensity, blendTime, true);
            _current = name;
            _holdRemaining = hold > 0f ? hold : -1f;
            LastResult = (preset.Count - missing.Count) + " of " + preset.Count + " morphs found"
                + (missing.Count > 0 ? " (missing: " + string.Join(", ", missing.ToArray()) + ")" : "");
            if (preset.Count > missing.Count) SetShowing(true);
            else EndShowing();   // "neutral" (or nothing found): the others fade out first, then VaM's Auto Expressions come back
            return true;
        }

        /// <summary>Sets raw morph values (name -> value). Returns names that were not found.</summary>
        public List<string> SetMorphs(Dictionary<string, float> morphs, float blendTime, bool releaseOthers)
        {
            List<string> missing = ApplyTargets(morphs, 1f, blendTime, releaseOthers);
            _current = "custom";
            _holdRemaining = -1f;
            if (morphs.Count > missing.Count) SetShowing(true);
            else EndShowing();
            return missing;
        }

        public void Reset(float blendTime)
        {
            _layer.BlendSeconds = blendTime;
            _layer.ReleaseAll();   // back to the look the scene had (not to 0)
            _current = "neutral";
            _holdRemaining = -1f;
            EndShowing();
        }

        public void RestoreNow()
        {
            _layer.RestoreNow();
            _current = "neutral";
            SetShowing(false);
        }

        /// <summary>Version 66: the expression ends. Auto Expressions are given back only when every morph has finished fading back
        /// (Update), so VaM's own writer does not fight the fade (two writers on the face).</summary>
        private void EndShowing()
        {
            if (!_showing) return;
            if (_layer.ActiveCount == 0) { _releasePending = false; SetShowing(false); }
            else _releasePending = true;
        }

        private void SetShowing(bool on)
        {
            if (on) _releasePending = false;
            if (on == _showing) return;
            _showing = on;
            if (OnShowingChanged != null) OnShowingChanged(on);
        }

        private List<string> ApplyTargets(Dictionary<string, float> targets, float intensity, float blendTime, bool releaseOthers)
        {
            List<string> missing = new List<string>();
            _layer.BlendSeconds = blendTime;   // version 66: every morph gets its own speed from its own distance (MorphBlendLayer)
            if (releaseOthers) _layer.ReleaseAllExcept(targets.Keys);
            foreach (KeyValuePair<string, float> kv in targets)
            {
                if (_layer.SetTarget(kv.Key, kv.Value * intensity)) continue;
                // Version 53: a two-sided name the character only has as Left / Right morphs (e.g. "Brow Inner Up").
                bool left = _layer.SetTarget(kv.Key + " Left", kv.Value * intensity);
                bool right = _layer.SetTarget(kv.Key + " Right", kv.Value * intensity);
                if (!left && !right) missing.Add(kv.Key);
            }
            return missing;
        }

        public void Update(float deltaTime)
        {
            if (_holdRemaining > 0f)
            {
                _holdRemaining -= deltaTime;
                if (_holdRemaining <= 0f) Reset(0.5f);
            }
            _layer.Update(deltaTime);
            if (_releasePending && _layer.ActiveCount == 0) { _releasePending = false; SetShowing(false); }
        }
    }
}
