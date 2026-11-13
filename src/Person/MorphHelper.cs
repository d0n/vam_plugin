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

        public MorphHelper(Atom atom)
        {
            _atom = atom;
            Refresh();
        }

        /// <summary>Re-resolves the morph UI, e.g. after the character (gender) changed.</summary>
        public void Refresh()
        {
            _cache.Clear();
            _missing.Clear();
            _morphsUI = null;
            DAZCharacterSelector selector = _atom.GetStorableByID("geometry") as DAZCharacterSelector;
            if (selector == null)
            {
                Log.Error("No DAZCharacterSelector ('geometry') on atom " + _atom.uid + "; morph features disabled.");
                return;
            }
            // morphsControlUI follows the currently selected character's gender.
            _morphsUI = selector.morphsControlUI;
        }

        public bool Available { get { return _morphsUI != null; } }

        /// <summary>Looks up a morph by display name first, then by uid. Returns null if unknown.</summary>
        public DAZMorph Find(string name)
        {
            if (_morphsUI == null || string.IsNullOrEmpty(name)) return null;
            DAZMorph morph;
            if (_cache.TryGetValue(name, out morph)) return morph;
            if (_missing.Contains(name)) return null;

            morph = _morphsUI.GetMorphByDisplayName(name);
            if (morph == null) morph = _morphsUI.GetMorphByUid(name);

            if (morph == null)
            {
                _missing.Add(name);
                Log.Info("Morph not found: '" + name + "' (check the name in the Morphs tab).");
                return null;
            }
            _cache[name] = morph;
            return morph;
        }
    }

    /// <summary>
    /// Blends a set of morphs toward target values each frame. Morphs that are released
    /// blend back to the value they had when this layer first touched them.
    /// </summary>
    public class MorphBlendLayer
    {
        private class Entry
        {
            public DAZMorph Morph;
            public float Original;
            public float Target;
            public bool Releasing;
        }

        private readonly MorphHelper _helper;
        private readonly Dictionary<string, Entry> _entries = new Dictionary<string, Entry>();
        private readonly List<string> _finished = new List<string>();

        /// <summary>Blend speed in morph units per second.</summary>
        public float Speed = 3f;

        public MorphBlendLayer(MorphHelper helper)
        {
            _helper = helper;
        }

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
            e.Releasing = false;
            return true;
        }

        public void Release(string morphName)
        {
            Entry e;
            if (_entries.TryGetValue(morphName, out e))
            {
                e.Target = e.Original;
                e.Releasing = true;
            }
        }

        public void ReleaseAllExcept(ICollection<string> keep)
        {
            foreach (KeyValuePair<string, Entry> kv in _entries)
            {
                if (keep != null && keep.Contains(kv.Key)) continue;
                kv.Value.Target = kv.Value.Original;
                kv.Value.Releasing = true;
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
            float step = Speed * deltaTime;
            _finished.Clear();
            foreach (KeyValuePair<string, Entry> kv in _entries)
            {
                Entry e = kv.Value;
                if (e.Morph == null) { _finished.Add(kv.Key); continue; }
                e.Morph.morphValue = Mathf.MoveTowards(e.Morph.morphValue, e.Target, step);
                if (e.Releasing && Mathf.Approximately(e.Morph.morphValue, e.Target)) _finished.Add(kv.Key);
            }
            for (int i = 0; i < _finished.Count; i++) _entries.Remove(_finished[i]);
        }
    }
}
