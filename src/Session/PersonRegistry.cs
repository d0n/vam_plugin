// Session plugin: finds the AIBody Person plugins in the current scene, by character SLOT, and
// exchanges messages with them through their "<prefix> Inbox" / "<prefix> Outbox" string params.
//
// Slots are strict: slot person1 is the d0n.AIBodyPerson script ("AIBody Inbox"), slot person2
// the d0n.AIBodyPerson2 script ("AIBody2 Inbox"). A slot is only usable when exactly one atom
// hosts its plugin and that atom hosts no other slot; otherwise it is reported as a conflict and
// nothing is delivered to it. There is never a fallback from one slot to another.
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
        public string Slot;
        public string AtomUid;
        public JSONStorable Storable;
        public JSONStorableString Inbox;
        public JSONStorableString Outbox;
        public string Version;
    }

    public class PersonRegistry
    {
        private readonly Dictionary<string, PersonLink> _bySlot = new Dictionary<string, PersonLink>();
        private readonly Dictionary<string, List<string>> _conflicts = new Dictionary<string, List<string>>();
        private List<PersonLink> _all = new List<PersonLink>(); // every plugin found, incl. conflicting ones
        private string _signature = "";
        private float _scanTimer = 999f;

        public float ScanInterval = 1f;

        /// <summary>The usable plugin of a slot, or null (missing or conflicting).</summary>
        public PersonLink Get(string slot)
        {
            PersonLink link;
            return slot != null && _bySlot.TryGetValue(slot, out link) && link.Storable != null ? link : null;
        }

        /// <summary>Atoms that host the slot's plugin if the slot is in conflict, else null.</summary>
        public List<string> Conflict(string slot)
        {
            List<string> atoms;
            return slot != null && _conflicts.TryGetValue(slot, out atoms) ? atoms : null;
        }

        /// <summary>All plugins found on an atom (normally zero or one).</summary>
        public List<PersonLink> OnAtom(string atomUid)
        {
            List<PersonLink> result = new List<PersonLink>();
            for (int i = 0; i < _all.Count; i++)
            {
                if (_all[i].AtomUid == atomUid && _all[i].Storable != null) result.Add(_all[i]);
            }
            return result;
        }

        public List<PersonLink> All { get { return new List<PersonLink>(_all); } }

        /// <summary>Rescans when due. Returns true if slots, atoms or conflicts changed.</summary>
        public bool Update(float deltaTime)
        {
            _scanTimer += deltaTime;
            bool dead = false;
            for (int i = 0; i < _all.Count; i++) dead |= _all[i].Storable == null; // Unity null: destroyed
            if (_scanTimer < ScanInterval && !dead) return false;
            _scanTimer = 0f;
            Scan();
            string signature = BuildSignature();
            if (signature == _signature) return false;
            _signature = signature;
            Log.Info("Characters: " + (signature.Length > 0 ? signature : "none"));
            return true;
        }

        public void ForceScan()
        {
            _scanTimer = 999f;
        }

        private void Scan()
        {
            List<PersonLink> found = new List<PersonLink>();
            SuperController sc = SuperController.singleton;
            List<Atom> atoms = sc != null ? sc.GetAtoms() : null;
            if (atoms != null)
            {
                for (int a = 0; a < atoms.Count; a++)
                {
                    if (atoms[a] != null) FindPlugins(atoms[a], found);
                }
            }

            // Slots hosted per atom (an atom with two slots is ambiguous: refuse both).
            Dictionary<string, int> slotsPerAtom = new Dictionary<string, int>();
            for (int i = 0; i < found.Count; i++)
            {
                int n;
                slotsPerAtom.TryGetValue(found[i].AtomUid, out n);
                slotsPerAtom[found[i].AtomUid] = n + 1;
            }

            _bySlot.Clear();
            _conflicts.Clear();
            for (int s = 0; s < Protocol.Slots.Length; s++)
            {
                string slot = Protocol.Slots[s];
                List<PersonLink> candidates = new List<PersonLink>();
                for (int i = 0; i < found.Count; i++) if (found[i].Slot == slot) candidates.Add(found[i]);
                if (candidates.Count == 0) continue;
                if (candidates.Count == 1 && slotsPerAtom[candidates[0].AtomUid] == 1)
                {
                    _bySlot[slot] = candidates[0];
                    continue;
                }
                List<string> atomsOfSlot = new List<string>();
                for (int i = 0; i < candidates.Count; i++) atomsOfSlot.Add(candidates[i].AtomUid);
                _conflicts[slot] = atomsOfSlot;
            }
            _all = found;
        }

        private static void FindPlugins(Atom atom, List<PersonLink> found)
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
                for (int s = 0; s < Protocol.Slots.Length; s++)
                {
                    string slot = Protocol.Slots[s];
                    JSONStorableString inbox = storable.GetStringJSONParam(Protocol.InboxParam(slot));
                    JSONStorableString outbox = storable.GetStringJSONParam(Protocol.OutboxParam(slot));
                    if (inbox == null || outbox == null) continue;
                    JSONStorableString version = storable.GetStringJSONParam(Protocol.VersionParam(slot));
                    found.Add(new PersonLink
                    {
                        Slot = slot,
                        AtomUid = atom.uid,
                        Storable = storable,
                        Inbox = inbox,
                        Outbox = outbox,
                        Version = version != null ? version.val : "?"
                    });
                }
            }
        }

        private string BuildSignature()
        {
            string sig = "";
            for (int s = 0; s < Protocol.Slots.Length; s++)
            {
                string slot = Protocol.Slots[s];
                PersonLink link = Get(slot);
                List<string> conflict = Conflict(slot);
                if (link != null) sig += (sig.Length > 0 ? ", " : "") + slot + "=" + link.AtomUid;
                if (conflict != null) sig += (sig.Length > 0 ? ", " : "") + slot + "=CONFLICT(" + string.Join("|", conflict.ToArray()) + ")";
            }
            return sig;
        }

        /// <summary>Hands one command to the slot's plugin. Returns false if the slot is not usable.</summary>
        public bool Deliver(string slot, JSONClass msg)
        {
            PersonLink link = Get(slot);
            if (link == null) return false;
            msg["slot"] = slot;
            // The Person plugin's callback runs synchronously and resets the value to "".
            // TODO(verify): setting .val from another plugin fires the setCallbackFunction (it does for
            // UI and trigger changes; JSONStorableString.val's setter calls it unconditionally in 1.22?).
            link.Inbox.val = msg.ToString();
            return true;
        }

        /// <summary>Collects pending events from every Person plugin found (conflicting ones too).</summary>
        public void DrainOutboxes(Action<JSONClass> forward)
        {
            for (int i = 0; i < _all.Count; i++)
            {
                PersonLink link = _all[i];
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
                    // The bridge knows which param the event came from: that is authoritative.
                    events[e]["slot"] = link.Slot;
                    events[e]["atom"] = link.AtomUid;
                    forward(events[e]);
                }
            }
        }

        /// <summary>[{slot, atom, plugin_version}] of the usable slots.</summary>
        public JSONArray ToJson()
        {
            JSONArray arr = new JSONArray();
            for (int s = 0; s < Protocol.Slots.Length; s++)
            {
                PersonLink link = Get(Protocol.Slots[s]);
                if (link == null) continue;
                JSONClass p = new JSONClass();
                p["slot"] = link.Slot;
                p["atom"] = link.AtomUid;
                p["plugin_version"] = link.Version;
                arr.Add(p);
            }
            return arr;
        }

        /// <summary>[{slot, atoms: [...]}] of the slots in conflict.</summary>
        public JSONArray ConflictsJson()
        {
            JSONArray arr = new JSONArray();
            for (int s = 0; s < Protocol.Slots.Length; s++)
            {
                List<string> atoms = Conflict(Protocol.Slots[s]);
                if (atoms == null) continue;
                JSONClass c = new JSONClass();
                c["slot"] = Protocol.Slots[s];
                JSONArray list = new JSONArray();
                for (int i = 0; i < atoms.Count; i++) list.Add(new JSONData(atoms[i]));
                c["atoms"] = list;
                arr.Add(c);
            }
            return arr;
        }
    }
}
