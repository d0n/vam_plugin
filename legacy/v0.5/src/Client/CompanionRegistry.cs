// Client plugin: finds the AIBody Companion plugins (the AI's bodies) in the current scene and
// exchanges messages with them through their "AIBody Companion Inbox" / "... Outbox" params.
//
// Only plain VaM scene APIs are used (SuperController.singleton.GetAtoms, Atom.GetStorableIDs,
// JSONStorable.GetStringJSONParam), so this works across separately compiled plugins and needs
// no files or network. The scan repeats every second, so Companion plugins added or removed
// later, or a scene change, are picked up automatically.
using System;
using System.Collections.Generic;
using SimpleJSON;
using AIBodyShared;

namespace AIBodyClient
{
    public class CompanionLink
    {
        public string AtomUid;
        public JSONStorable Storable;
        public JSONStorableString Inbox;
        public JSONStorableString Outbox;
        public string Version;
    }

    public class CompanionRegistry
    {
        private List<CompanionLink> _all = new List<CompanionLink>();
        private string _signature = "";
        private float _scanTimer = 999f;

        public float ScanInterval = 1f;

        public List<CompanionLink> All { get { return new List<CompanionLink>(_all); } }

        /// <summary>Atom uids with a Companion plugin, in scene order (an atom appears once per plugin).</summary>
        public List<string> AtomUids
        {
            get
            {
                List<string> uids = new List<string>();
                for (int i = 0; i < _all.Count; i++) if (_all[i].Storable != null) uids.Add(_all[i].AtomUid);
                return uids;
            }
        }

        /// <summary>Companion plugins on one atom (normally zero or one).</summary>
        public List<CompanionLink> OnAtom(string atomUid)
        {
            List<CompanionLink> result = new List<CompanionLink>();
            for (int i = 0; i < _all.Count; i++)
            {
                if (_all[i].AtomUid == atomUid && _all[i].Storable != null) result.Add(_all[i]);
            }
            return result;
        }

        /// <summary>Rescans when due. Returns true if the set of Companions changed.</summary>
        public bool Update(float deltaTime)
        {
            _scanTimer += deltaTime;
            bool dead = false;
            for (int i = 0; i < _all.Count; i++) dead |= _all[i].Storable == null; // Unity null: destroyed
            if (_scanTimer < ScanInterval && !dead) return false;
            _scanTimer = 0f;
            Scan();
            string signature = string.Join(", ", AtomUids.ToArray());
            if (signature == _signature) return false;
            _signature = signature;
            Log.Info("Companion plugins: " + (signature.Length > 0 ? signature : "none"));
            return true;
        }

        public void ForceScan()
        {
            _scanTimer = 999f;
        }

        private void Scan()
        {
            List<CompanionLink> found = new List<CompanionLink>();
            SuperController sc = SuperController.singleton;
            List<Atom> atoms = sc != null ? sc.GetAtoms() : null;
            if (atoms != null)
            {
                for (int a = 0; a < atoms.Count; a++)
                {
                    if (atoms[a] != null) FindPlugins(atoms[a], found);
                }
            }
            _all = found;
        }

        private static void FindPlugins(Atom atom, List<CompanionLink> found)
        {
            List<string> ids = atom.GetStorableIDs();
            if (ids == null) return;
            for (int i = 0; i < ids.Count; i++)
            {
                // Plugin storables are named "plugin#<n>_<Class>".
                // TODO(verify): id prefix on 1.22 (if it differs, drop this filter; the param check suffices).
                if (!ids[i].StartsWith("plugin#", StringComparison.Ordinal)) continue;
                JSONStorable storable = atom.GetStorableByID(ids[i]);
                if (storable == null) continue;
                JSONStorableString inbox = storable.GetStringJSONParam(Protocol.CompanionInboxParam);
                JSONStorableString outbox = storable.GetStringJSONParam(Protocol.CompanionOutboxParam);
                if (inbox == null || outbox == null) continue;
                JSONStorableString version = storable.GetStringJSONParam(Protocol.CompanionVersionParam);
                found.Add(new CompanionLink
                {
                    AtomUid = atom.uid,
                    Storable = storable,
                    Inbox = inbox,
                    Outbox = outbox,
                    Version = version != null ? version.val : "?"
                });
            }
        }

        /// <summary>
        /// Picks the Companion for a command. atomUid = explicit target ("" = none).
        /// Returns the link, or null with error set to no_companion / companion_conflict.
        /// Never picks a different atom than the one asked for.
        /// </summary>
        public CompanionLink Resolve(string atomUid, out string error, out string message)
        {
            error = null;
            message = null;
            List<CompanionLink> candidates = atomUid.Length > 0 ? OnAtom(atomUid) : OnAll();
            if (candidates.Count == 1) return candidates[0];
            if (candidates.Count == 0)
            {
                error = Protocol.ErrNoCompanion;
                message = atomUid.Length > 0
                    ? "No AIBody Companion plugin on atom '" + atomUid + "'"
                    : "No AIBody Companion plugin in the scene (add AIBodyCompanion.cslist to the AI's Person atom)";
                return null;
            }
            error = Protocol.ErrCompanionConflict;
            message = (atomUid.Length > 0 ? "Atom '" + atomUid + "' has " : "The scene has ") + candidates.Count
                + " AIBody Companion plugins (" + string.Join(", ", AtomUidsOf(candidates)) + "); pick one in the Client's 'Companion atom'";
            return null;
        }

        private List<CompanionLink> OnAll()
        {
            List<CompanionLink> result = new List<CompanionLink>();
            for (int i = 0; i < _all.Count; i++) if (_all[i].Storable != null) result.Add(_all[i]);
            return result;
        }

        private static string[] AtomUidsOf(List<CompanionLink> links)
        {
            string[] uids = new string[links.Count];
            for (int i = 0; i < links.Count; i++) uids[i] = links[i].AtomUid;
            return uids;
        }

        /// <summary>Hands one command to a Companion plugin.</summary>
        public void Deliver(CompanionLink link, JSONClass msg, string clientAtomUid)
        {
            msg["via"] = Protocol.ViaClient;
            msg["client"] = clientAtomUid;
            // The Companion plugin's callback runs synchronously and resets the value to "".
            // TODO(verify): setting .val from another plugin fires the setCallbackFunction (it does for
            // UI and trigger changes; JSONStorableString.val's setter calls it unconditionally in 1.22?).
            link.Inbox.val = msg.ToString();
        }

        /// <summary>Collects pending events from every Companion plugin found.</summary>
        public void DrainOutboxes(Action<JSONClass> forward)
        {
            for (int i = 0; i < _all.Count; i++)
            {
                CompanionLink link = _all[i];
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
                    events[e]["atom"] = link.AtomUid; // authoritative: the atom the param belongs to
                    forward(events[e]);
                }
            }
        }

        /// <summary>[{atom, plugin_version}] of every Companion plugin found.</summary>
        public JSONArray ToJson()
        {
            JSONArray arr = new JSONArray();
            for (int i = 0; i < _all.Count; i++)
            {
                if (_all[i].Storable == null) continue;
                JSONClass p = new JSONClass();
                p["atom"] = _all[i].AtomUid;
                p["plugin_version"] = _all[i].Version;
                arr.Add(p);
            }
            return arr;
        }
    }
}
