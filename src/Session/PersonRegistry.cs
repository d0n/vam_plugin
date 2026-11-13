// Session plugin: finds AIBody Person plugins in the current scene and exchanges messages
// with them through their "AIBody Inbox" / "AIBody Outbox" string params.
//
// Only plain VaM scene APIs are used (SuperController.singleton.GetAtoms, Atom.GetStorableIDs,
// JSONStorable.GetStringJSONParam), so this works across separately compiled plugins and needs
// no files or network. The scan repeats every second, so Person plugins added or removed later,
// or a scene change, are picked up automatically.
using System;
using System.Collections.Generic;
using SimpleJSON;

namespace AIBody
{
    public class PersonLink
    {
        public string AtomUid;
        public JSONStorable Storable;
        public JSONStorableString Inbox;
        public JSONStorableString Outbox;
        public string Version;
    }

    public class PersonRegistry
    {
        private readonly Dictionary<string, PersonLink> _links = new Dictionary<string, PersonLink>();
        private readonly List<string> _order = new List<string>();
        private float _scanTimer = 999f;

        public float ScanInterval = 1f;

        /// <summary>Atom uids with a Person plugin, in discovery order.</summary>
        public List<string> AtomUids { get { return new List<string>(_order); } }

        public int Count { get { return _order.Count; } }

        public PersonLink Get(string atomUid)
        {
            PersonLink link;
            return atomUid != null && _links.TryGetValue(atomUid, out link) ? link : null;
        }

        /// <summary>Rescans when due. Returns true if the set of persons changed.</summary>
        public bool Update(float deltaTime)
        {
            bool changed = RemoveDead();
            _scanTimer += deltaTime;
            if (_scanTimer >= ScanInterval)
            {
                _scanTimer = 0f;
                changed |= Scan();
            }
            return changed;
        }

        public void ForceScan()
        {
            _scanTimer = 999f;
        }

        private bool RemoveDead()
        {
            bool changed = false;
            for (int i = _order.Count - 1; i >= 0; i--)
            {
                PersonLink link = _links[_order[i]];
                // Unity's == null is true for destroyed components (atom deleted, plugin removed).
                if (link.Storable == null)
                {
                    _links.Remove(_order[i]);
                    _order.RemoveAt(i);
                    changed = true;
                }
            }
            return changed;
        }

        private bool Scan()
        {
            SuperController sc = SuperController.singleton;
            if (sc == null) return false;
            List<Atom> atoms = sc.GetAtoms();
            if (atoms == null) return false;

            HashSet<string> seen = new HashSet<string>();
            bool changed = false;
            for (int a = 0; a < atoms.Count; a++)
            {
                Atom atom = atoms[a];
                if (atom == null) continue;
                PersonLink link = FindPlugin(atom);
                if (link == null) continue;
                seen.Add(link.AtomUid);
                PersonLink old;
                if (!_links.TryGetValue(link.AtomUid, out old))
                {
                    _links[link.AtomUid] = link;
                    _order.Add(link.AtomUid);
                    Log.Info("Found AIBody Person plugin on '" + link.AtomUid + "'");
                    changed = true;
                }
                else if (old.Storable != link.Storable)
                {
                    _links[link.AtomUid] = link; // plugin was reloaded
                    changed = true;
                }
            }
            for (int i = _order.Count - 1; i >= 0; i--)
            {
                if (seen.Contains(_order[i])) continue;
                Log.Info("AIBody Person plugin on '" + _order[i] + "' is gone");
                _links.Remove(_order[i]);
                _order.RemoveAt(i);
                changed = true;
            }
            return changed;
        }

        private static PersonLink FindPlugin(Atom atom)
        {
            List<string> ids = atom.GetStorableIDs();
            if (ids == null) return null;
            for (int i = 0; i < ids.Count; i++)
            {
                // Plugin storables are named "plugin#<n>_<Namespace>.<Class>".
                if (!ids[i].StartsWith("plugin#", StringComparison.Ordinal)) continue;
                JSONStorable storable = atom.GetStorableByID(ids[i]);
                if (storable == null) continue;
                JSONStorableString inbox = storable.GetStringJSONParam(Protocol.PersonInboxParam);
                JSONStorableString outbox = storable.GetStringJSONParam(Protocol.PersonOutboxParam);
                if (inbox == null || outbox == null) continue;
                JSONStorableString version = storable.GetStringJSONParam(Protocol.PersonVersionParam);
                return new PersonLink
                {
                    AtomUid = atom.uid,
                    Storable = storable,
                    Inbox = inbox,
                    Outbox = outbox,
                    Version = version != null ? version.val : "?"
                };
            }
            return null;
        }

        /// <summary>Hands one command to a Person plugin. Returns false if it is not available.</summary>
        public bool Deliver(string atomUid, JSONClass msg)
        {
            PersonLink link = Get(atomUid);
            if (link == null || link.Storable == null) return false;
            // The Person plugin's callback runs synchronously and resets the value to "".
            link.Inbox.val = msg.ToString();
            return true;
        }

        /// <summary>Collects pending events from every Person plugin.</summary>
        public void DrainOutboxes(Action<JSONClass> forward)
        {
            for (int i = 0; i < _order.Count; i++)
            {
                PersonLink link = _links[_order[i]];
                if (link.Storable == null) continue;
                string raw = link.Outbox.val;
                if (string.IsNullOrEmpty(raw)) continue;
                link.Outbox.val = "";
                List<JSONClass> events;
                try
                {
                    events = Protocol.ParseMessages(raw);
                }
                catch (Exception e)
                {
                    Log.Error("Bad outbox data from '" + link.AtomUid + "' dropped", e);
                    continue;
                }
                for (int e = 0; e < events.Count; e++)
                {
                    if (!Protocol.Has(events[e], "atom")) events[e]["atom"] = link.AtomUid;
                    forward(events[e]);
                }
            }
        }

        public JSONArray ToJson()
        {
            JSONArray arr = new JSONArray();
            for (int i = 0; i < _order.Count; i++)
            {
                PersonLink link = _links[_order[i]];
                JSONClass p = new JSONClass();
                p["atom"] = link.AtomUid;
                p["plugin_version"] = link.Version;
                arr.Add(p);
            }
            return arr;
        }
    }
}
