// Finds DAZ morphs on a Person atom and remembers their original values so the
// plugin can always return a morph to where the scene had it.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace AIBody
{
    public class MorphHelper
    {
        private readonly Atom _atom;
        private GenerateDAZMorphsControlUI _morphsUI;
        private readonly Dictionary<string, DAZMorph> _cache = new Dictionary<string, DAZMorph>();
        private readonly HashSet<string> _missing = new HashSet<string>();

        private float _nextTry;
        private bool _warned;

        public MorphHelper(Atom atom)
        {
            _atom = atom;
            Refresh();
        }

        /// <summary>Why morphs are not available (null while they are).</summary>
        public string LookupError { get; private set; }

        /// <summary>Re-resolves the morph UI, e.g. after the character (gender) changed.</summary>
        public void Refresh()
        {
            _cache.Clear();
            _missing.Clear();
            _morphsUI = null;
            _nextTry = Time.time + 5f;
            try
            {
                DAZCharacterSelector selector = _atom.GetStorableByID("geometry") as DAZCharacterSelector;
                // morphsControlUI follows the currently selected character's gender.
                if (selector != null) _morphsUI = selector.morphsControlUI;
                LookupError = selector == null ? "no DAZCharacterSelector 'geometry'"
                    : (_morphsUI == null ? "morphsControlUI is empty" : null);
            }
            catch (Exception e)
            {
                LookupError = Diag.Describe(e);
            }
            if (_morphsUI == null && !_warned)
            {
                _warned = true;
                Log.Error("The character's morphs are not available yet: " + LookupError + ". Expressions and breathing wait for them; the plugin keeps trying every 5 s.");
            }
            else if (_morphsUI != null && _warned)
            {
                _warned = false;
                Log.Info("Morphs found.");
            }
        }

        /// <summary>True once the morph UI was found; a failed lookup is retried every 5 s.</summary>
        public bool Available
        {
            get
            {
                if (_morphsUI == null && Time.time >= _nextTry) Refresh();
                return _morphsUI != null;
            }
        }

        /// <summary>Looks up a morph by display name first, then by uid. Returns null if unknown.</summary>
        public DAZMorph Find(string name)
        {
            if (string.IsNullOrEmpty(name) || !Available) return null;
            DAZMorph morph;
            if (_cache.TryGetValue(name, out morph)) return morph;
            if (_missing.Contains(name)) return null;

            morph = _morphsUI.GetMorphByDisplayName(name);
            if (morph == null) morph = _morphsUI.GetMorphByUid(name);

            if (morph == null)
            {
                _missing.Add(name);
                Log.Info("Morph '" + name + "' was not found on this character. Check the exact name in the character's Morphs tab.");
                return null;
            }
            _cache[name] = morph;
            return morph;
        }
    }

    /// <summary>
    /// Blends a set of morphs toward target values each frame. Morphs that are released
    /// blend back to the value they had when this layer first touched them.
    /// Version 66: every entry has its OWN speed, set when its target or release is set (distance / BlendSeconds, at least
    /// MinDistance and MinBlend). Up to v65 one layer-wide speed came from the newest targets only: a release to neutral
    /// (distance 0.1) set 0.04 morph units per second, so an older smile took about 17 s to fade and faces mixed.
    /// </summary>
    public class MorphBlendLayer
    {
        private class Entry
        {
            public DAZMorph Morph;
            public float Original;
            public float Target;
            public float Speed;       // morph units per second, this entry only (version 66)
            public bool Releasing;
        }

        /// <summary>Version 66: the smallest distance and blend time used for a speed (no division by ~0, no crawl for a tiny change).</summary>
        public const float MinDistance = 0.05f;
        public const float MinBlend = 0.05f;

        private readonly MorphHelper _helper;
        private readonly Dictionary<string, Entry> _entries = new Dictionary<string, Entry>();
        private readonly List<string> _finished = new List<string>();

        /// <summary>Version 66: seconds the next SetTarget / Release / ReleaseAll calls take to reach their target.</summary>
        public float BlendSeconds = 0.4f;

        public MorphBlendLayer(MorphHelper helper)
        {
            _helper = helper;
        }

        /// <summary>Morph units per second to cover distance in blendSeconds (version 66, the rule of every entry).</summary>
        public static float SpeedFor(float distance, float blendSeconds)
        {
            return Mathf.Max(distance, MinDistance) / Mathf.Max(blendSeconds, MinBlend);
        }

        /// <summary>Morphs this layer still holds (shown, or fading back to their original value).</summary>
        public int ActiveCount { get { return _entries.Count; } }

        public bool SetTarget(string morphName, float value)
        {
            Entry e;
            if (!_entries.TryGetValue(morphName, out e))
            {
                DAZMorph morph = _helper.Find(morphName);
                if (morph == null) return false;
                e = new Entry { Morph = morph, Original = morph.morphValue };
                _entries[morphName] = e;
            }
            e.Target = value;
            e.Speed = SpeedFor(Mathf.Abs(value - e.Morph.morphValue), BlendSeconds);
            e.Releasing = false;
            return true;
        }

        public void Release(string morphName)
        {
            Entry e;
            if (_entries.TryGetValue(morphName, out e)) ReleaseEntry(e);
        }

        private void ReleaseEntry(Entry e)
        {
            e.Target = e.Original;
            e.Speed = e.Morph != null ? SpeedFor(Mathf.Abs(e.Morph.morphValue - e.Target), BlendSeconds) : SpeedFor(0f, BlendSeconds);
            e.Releasing = true;
        }

        public void ReleaseAllExcept(ICollection<string> keep)
        {
            foreach (KeyValuePair<string, Entry> kv in _entries)
            {
                if (keep != null && keep.Contains(kv.Key)) continue;
                ReleaseEntry(kv.Value);
            }
        }

        public void ReleaseAll()
        {
            ReleaseAllExcept(null);
        }

        /// <summary>Immediately restores all original values (used on disable/destroy).</summary>
        public void RestoreNow()
        {
            foreach (KeyValuePair<string, Entry> kv in _entries)
            {
                if (kv.Value.Morph != null) kv.Value.Morph.morphValue = kv.Value.Original;
            }
            _entries.Clear();
        }

        public void Update(float deltaTime)
        {
            if (_entries.Count == 0) return;
            _finished.Clear();
            foreach (KeyValuePair<string, Entry> kv in _entries)
            {
                Entry e = kv.Value;
                if (e.Morph == null) { _finished.Add(kv.Key); continue; }
                e.Morph.morphValue = Mathf.MoveTowards(e.Morph.morphValue, e.Target, e.Speed * deltaTime);
                if (e.Releasing && Mathf.Approximately(e.Morph.morphValue, e.Target)) _finished.Add(kv.Key);
            }
            for (int i = 0; i < _finished.Count; i++) _entries.Remove(_finished[i]);
        }
    }
}
