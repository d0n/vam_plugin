// The VaM side of the idle movement (version 60, see IdleMovement.cs): AIBody's own IdlePoser instance on the AI
// character - found by its plugin label, or added to the AI character's plugin list once - and the per-frame checks
// "grabbed" and "posed from outside". Only evidenced calls (docs/API_AUDIT.md E41-E44):
//   - IdlePoser's storable id ends with "_MacGruber.IdlePoser" (E8 pattern), its label is the "pluginLabel" string
//     (E43: saved like that in MacGruber's demo scene);
//   - adding a plugin: PluginManager as MVRPluginManager, CreatePlugin(), pluginURLJSON.val = the .cslist (E41);
//   - the states: LateRestoreFromJSON with an "idlepose" object, exactly what VaM does when it loads a scene with
//     IdlePoser (E43: IdlePoser overrides LateRestoreFromJSON and reads "idlepose");
//   - on / off: the plugin's "enabled" value (E44: stored like that for every plugin) and the component's enabled flag
//     (Unity Behaviour.enabled): off = its Update no longer writes the controllers, she stays where she is;
//   - FreeControllerV3.isGrabbing (E42), SuperController.isLoading (E43), Quaternion.eulerAngles (E43).
// IdlePoser itself is never changed and not shipped. Version 63: optional, off by default; the package does not depend on
// MacGruber.IdlePoser.9 (the user installs it to use the toggle) and Body creates this link only when Idle movement is on.
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;
using MVR.FileManagementSecure;

namespace AIBody
{
    public class IdlePoserLink
    {
        private readonly Atom _atom;
        private JSONStorable _poser;
        private bool _addTried;
        private float _findIn;
        private bool _poserOn;
        private readonly Vector3[] _last = new Vector3[IdleMovementPlan.Controls.Length];
        private readonly bool[] _haveLast = new bool[IdleMovementPlan.Controls.Length];
        private readonly FreeControllerV3[] _controls = new FreeControllerV3[IdleMovementPlan.Controls.Length];

        /// <summary>"" or why IdlePoser is not there (info field, log once).</summary>
        public string Problem = "";
        /// <summary>The base pose of the last start (Rebuild uses it again, so a new liveliness does not drift the pose).</summary>
        public List<IdlePart> BasePose;

        public IdlePoserLink(Atom atom) { _atom = atom; }

        public bool Available { get { return _poser != null; } }
        public bool PoserOn { get { return _poser != null && _poserOn; } }

        /// <summary>Version 61: seconds after a scene load (and after the plugin started) before IdlePoser is looked for
        /// or added. VaM is still restoring the scene's plugins and their storables (pluginLabel, idlepose) meanwhile.</summary>
        public const float LoadGraceSeconds = 3f;
        private float _sinceLoad;
        private bool _duplicatesNoted;

        /// <summary>Finds AIBody's IdlePoser on the AI character (every 2 s until found); adds it once when it is missing,
        /// the package is installed and add is true. Never on a Person named 'Client' (the user's character).
        /// Version 61: does nothing while the scene loads (loading = SuperController.isLoading, E43) and for
        /// LoadGraceSeconds after it: up to v60 it could add a second IdlePoser to the plugin list in the middle of VaM's
        /// scene load, before the scene's own "AIBody Idle Movement" instance had its label back.</summary>
        public void Find(float dt, bool add, bool loading)
        {
            if (_atom == null) return;
            if (loading) { _sinceLoad = 0f; return; }
            if (_sinceLoad < LoadGraceSeconds) { _sinceLoad += dt; return; }
            if (_poser != null)
            {
                if (_poser.containingAtom == _atom) return;   // the instance was removed (Unity null) or moved
                _poser = null;
            }
            _findIn -= dt;
            if (_findIn > 0f) return;
            _findIn = 2f;
            if (_atom.uid == AIBodyPlugin.ClientAtomName) { Problem = "the AI character is the Person 'Client' (the user's character): no idle movement"; return; }
            _poser = Search();
            if (_poser != null) { Adopt(); return; }
            if (!add || _addTried) return;
            _addTried = true;
            bool installed;
            try { installed = FileManagerSecure.FileExists(IdleMovementPlan.PoserCslist); }   // E10, E45 (TODO(verify): package path via FileManagerSecure)
            catch (Exception) { installed = false; }
            if (!installed)
            {
                Problem = IdleMovementPlan.PoserPackage + " is not installed (VaM Hub, free): install MacGruber's IdlePoser to use "
                    + "Idle movement (AIBody does not depend on it), or switch Idle movement off";   // version 63
                Log.Warn("Idle movement: " + Problem);
                return;
            }
            try
            {
                MVRPluginManager manager = _atom.GetStorableByID("PluginManager") as MVRPluginManager;   // E1, E41
                if (manager == null) { Problem = "the AI character has no plugin list"; return; }
                List<string> before = PoserIds();
                MVRPlugin plugin = manager.CreatePlugin();   // E41 (Keybindings PluginReference.cs L99-100)
                plugin.pluginURLJSON.val = IdleMovementPlan.PoserCslist;
                List<string> after = PoserIds();
                for (int i = 0; i < after.Count; i++)
                {
                    if (before.Contains(after[i])) continue;
                    JSONStorable s = _atom.GetStorableByID(after[i]);
                    JSONStorableString label = s != null ? s.GetStringJSONParam("pluginLabel") : null;   // E13, E43
                    if (label != null) label.val = IdleMovementPlan.PoserLabel;
                    _poser = s;
                    break;
                }
                if (_poser == null) { Problem = "IdlePoser was added but did not start (see VaM's error log)"; Log.Warn("Idle movement: " + Problem); return; }
                Log.Info("Idle movement: added " + IdleMovementPlan.PoserPackage + " to '" + _atom.uid + "' as '" + IdleMovementPlan.PoserLabel + "'");
                Adopt();
            }
            catch (Exception e)
            {
                Problem = "adding IdlePoser failed: " + Diag.Describe(e);
                Log.Warn("Idle movement: " + Problem);
            }
        }

        private void Adopt()
        {
            Problem = "";
            SetOn(false);   // nothing moves until the gate allows it (states from her current pose first)
        }

        private List<string> PoserIds()
        {
            List<string> result = new List<string>();
            List<string> ids = _atom.GetStorableIDs();   // E8
            if (ids == null) return result;
            for (int i = 0; i < ids.Count; i++)
                if (ids[i] != null && ids[i].EndsWith(IdleMovementPlan.PoserStorableSuffix)) result.Add(ids[i]);
            return result;
        }

        /// <summary>The IdlePoser instance labelled "AIBody Idle Movement" (other IdlePoser instances stay untouched).
        /// Version 61: a scene saved with v60 can hold more than one of them (v60 could add one during the scene load);
        /// the first is used, every further "AIBody Idle Movement" instance is switched off so only one writes the body.</summary>
        private JSONStorable Search()
        {
            List<string> ids = PoserIds();
            JSONStorable found = null;
            for (int i = 0; i < ids.Count; i++)
            {
                JSONStorable s = _atom.GetStorableByID(ids[i]);
                JSONStorableString label = s != null ? s.GetStringJSONParam("pluginLabel") : null;
                if (label == null || label.val != IdleMovementPlan.PoserLabel) continue;
                if (found == null) { found = s; continue; }
                Switch(s, false);
                if (!_duplicatesNoted)
                {
                    _duplicatesNoted = true;
                    Log.Warn("Idle movement: '" + _atom.uid + "' has more than one '" + IdleMovementPlan.PoserLabel
                             + "' plugin (saved by v60); only the first is used, the others are switched off. Remove them "
                             + "in the Plugins tab and save the scene.");
                }
            }
            return found;
        }

        private static void Switch(JSONStorable plugin, bool on)
        {
            if (plugin == null) return;
            JSONStorableBool enabled = plugin.GetBoolJSONParam("enabled");   // E12, E44
            if (enabled != null) { if (enabled.val != on) enabled.val = on; }
            if (plugin.enabled != on) plugin.enabled = on;
        }

        /// <summary>On = IdlePoser's Update runs and drives the controllers; off = it writes nothing. Through the plugin's
        /// own "enabled" value (VaM's enable toggle of the plugin, saved with the scene, E44), else the component flag.</summary>
        public void SetOn(bool on)
        {
            _poserOn = on;
            if (_poser == null) return;
            Switch(_poser, on);
        }

        /// <summary>The current pose of the controllers IdlePoser will drive, relative to their anchors (root / chest).</summary>
        public List<IdlePart> CaptureBase()
        {
            List<IdlePart> parts = new List<IdlePart>();
            for (int i = 0; i < IdleMovementPlan.Controls.Length; i++)
            {
                string name = IdleMovementPlan.Controls[i];
                FreeControllerV3 c = Control(i);
                FreeControllerV3 anchor = _atom.GetStorableByID(IdleMovementPlan.AnchorOf(name)) as FreeControllerV3;
                if (c == null || anchor == null) continue;
                Transform t = c.transform, at = anchor.transform;
                Quaternion inv = Quaternion.Inverse(at.rotation);
                Vector3 p = inv * (t.position - at.position);   // the same offsets IdlePoser captures (Capture, ANCHORMODE_SINGLE)
                Vector3 e = (inv * t.rotation).eulerAngles;      // E43
                parts.Add(new IdlePart(name, IdleMovementPlan.AnchorOf(name), p.x, p.y, p.z, e.x, e.y, e.z));
            }
            return parts;
        }

        /// <summary>Loads the states into IdlePoser (as a scene load does). Returns an error or null.</summary>
        public string Push(string idlePoseJson)
        {
            if (_poser == null) return "IdlePoser not found";
            if (string.IsNullOrEmpty(idlePoseJson)) return "no states (the AI character has no hipControl)";
            JSONClass jc = new JSONClass();
            jc["id"] = _poser.storeId;
            jc["idlepose"] = JSON.Parse(idlePoseJson);
            _poser.LateRestoreFromJSON(jc, true, true, false);   // E43; setMissingToDefault false: no other value changes
            return null;
        }

        private FreeControllerV3 Control(int i)
        {
            if (_controls[i] == null) _controls[i] = _atom.GetStorableByID(IdleMovementPlan.Controls[i]) as FreeControllerV3;
            return _controls[i];
        }

        /// <summary>True while the user holds any controller of the AI character (mouse or VR hand), E42.</summary>
        public bool Grabbed()
        {
            FreeControllerV3[] all = _atom != null ? _atom.freeControllers : null;   // E12
            if (all == null) return false;
            for (int i = 0; i < all.Length; i++) if (all[i] != null && all[i].isGrabbing) return true;
            return false;
        }

        /// <summary>
        /// True when a driven controller jumped this frame in root space (a pose loaded from outside). Moving the whole
        /// character (Body position, PoseGuard) is not a jump: positions are taken relative to the root controller.
        /// ignore = true while AIBody itself applies a pose or right after the states changed (the baseline is renewed).
        /// </summary>
        public bool Jumped(float dt, bool ignore)
        {
            if (_atom == null || _atom.mainController == null) return false;
            Transform root = _atom.mainController.transform;   // E12
            Quaternion inv = Quaternion.Inverse(root.rotation);
            bool jump = false;
            for (int i = 0; i < _last.Length; i++)
            {
                FreeControllerV3 c = Control(i);
                if (c == null) { _haveLast[i] = false; continue; }
                Vector3 p = inv * (c.transform.position - root.position);
                if (!ignore && _haveLast[i] && IdleMovementPlan.IsJump((p - _last[i]).magnitude, dt)) jump = true;
                _last[i] = p;
                _haveLast[i] = true;
            }
            return jump;
        }
    }
}
