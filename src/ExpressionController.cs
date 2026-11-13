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

        public ExpressionController(MorphHelper morphs)
        {
            _layer = new MorphBlendLayer(morphs);
            LoadDefaults();
        }

        public string Current { get { return _current; } }

        public IEnumerable<string> PresetNames { get { return _presets.Keys; } }

        private void LoadDefaults()
        {
            // TODO(verify): morph names against a stock VaM 1.22 female and male character.
            _presets["neutral"] = new Dictionary<string, float>();
            _presets["happy"] = Preset("Mouth Smile Simple", 0.7f, "Brow Inner Up", 0.15f);
            _presets["smile"] = Preset("Mouth Smile Simple", 0.4f);
            _presets["sad"] = Preset("Mouth Frown", 0.5f, "Brow Inner Up", 0.6f);
            _presets["angry"] = Preset("Brow Down", 0.7f, "Mouth Frown", 0.3f);
            _presets["surprised"] = Preset("Brow Outer Up Left", 0.7f, "Brow Outer Up Right", 0.7f, "Mouth Open", 0.3f);
            _presets["thinking"] = Preset("Brow Down Left", 0.3f, "Mouth Side-Side Left", 0.2f);
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
            ApplyTargets(preset, intensity, blendTime, true);
            _current = name;
            _holdRemaining = hold > 0f ? hold : -1f;
            return true;
        }

        /// <summary>Sets raw morph values (name -> value). Returns names that were not found.</summary>
        public List<string> SetMorphs(Dictionary<string, float> morphs, float blendTime, bool releaseOthers)
        {
            List<string> missing = ApplyTargets(morphs, 1f, blendTime, releaseOthers);
            _current = "custom";
            _holdRemaining = -1f;
            return missing;
        }

        public void Reset(float blendTime)
        {
            SetSpeedFor(1f, blendTime);
            _layer.ReleaseAll();
            _current = "neutral";
            _holdRemaining = -1f;
        }

        public void RestoreNow()
        {
            _layer.RestoreNow();
            _current = "neutral";
        }

        private List<string> ApplyTargets(Dictionary<string, float> targets, float intensity, float blendTime, bool releaseOthers)
        {
            List<string> missing = new List<string>();
            float maxDelta = 0f;
            foreach (KeyValuePair<string, float> kv in targets) maxDelta = Mathf.Max(maxDelta, Mathf.Abs(kv.Value * intensity));
            SetSpeedFor(Mathf.Max(maxDelta, 0.1f), blendTime);

            if (releaseOthers) _layer.ReleaseAllExcept(targets.Keys);
            foreach (KeyValuePair<string, float> kv in targets)
            {
                if (!_layer.SetTarget(kv.Key, kv.Value * intensity)) missing.Add(kv.Key);
            }
            return missing;
        }

        private void SetSpeedFor(float distance, float blendTime)
        {
            _layer.Speed = blendTime <= 0.01f ? 1000f : distance / blendTime;
        }

        public void Update(float deltaTime)
        {
            if (_holdRemaining > 0f)
            {
                _holdRemaining -= deltaTime;
                if (_holdRemaining <= 0f) Reset(0.5f);
            }
            _layer.Update(deltaTime);
        }
    }
}
