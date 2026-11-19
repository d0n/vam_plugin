// Gaze control: where the eyes of this Person look.
//
// Uses VaM's own eye system, like Embody's eye target module and Glance: the Person's "Eyes" storable is
// switched to look mode "Target" and the "eyeTargetControl" controller is moved to the point to look at
// (the eyes follow it by themselves, with VaM's normal eye speed limits). Nothing else is touched:
// no morphs, no head rotation (the idle head motion keeps working).
//
// Targets: the Client Character (its head), the camera / player view, straight ahead, away (a short
// glance to the side), or any atom by name. "default" = AIBody does not touch the eyes at all.
//
// Coexistence (never fight another plugin): if the Glance plugin is on this Person, AIBody stays out of
// the eyes (the same check Embody itself uses against Glance). If anything else (Life, Embody while
// possessing, the user) changes the Eyes look mode while AIBody is steering, AIBody stops and gives the
// eyes back until the user picks a target in the menu again. Every change AIBody made is undone when it lets go (look mode and eye
// target position are restored, like Embody does).
//
// Evidence (docs/API_AUDIT.md, E12 and E28): GetStorableByID("Eyes") as EyesControl, currentLookMode
// get/set with LookMode.Target, freeControllers + name == "eyeTargetControl", eyeTarget.control.position
// get/set, centerCameraTarget.transform, GetAtoms(), atom.mainController.control, rotation * Vector3.forward.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace AIBody
{
    public class GazeController
    {
        // Canonical targets (config.json body.gaze_default and the look_at command).
        public const string KeyDefault = "default";   // do not touch the eyes
        public const string KeyClient = "client";
        public const string KeyCamera = "camera";
        public const string KeyForward = "forward";
        public const string KeyAway = "away";
        public const string KeyOff = "off";           // look_at only: stop directing, back to the default
        public const string KeyAtom = "atom";         // look_at only, with "atom" = the atom's name
        public const string AtomPrefix = "atom:";     // config.json: "atom:<uid>"

        /// <summary>Name of the Client Character atom in the example scene; else the first other Person.</summary>
        public const string ClientAtomName = "Client Character";

        private const float ForwardDistance = 2f;
        private const float AwayYaw = 35f;
        private const float AwayPitch = 12f;
        private const float AwayDefaultSeconds = 3f;
        public const float MaxSeconds = 60f;

        private readonly Atom _atom;
        private EyesControl _eyes;
        private FreeControllerV3 _eyeTarget;
        private FreeControllerV3 _head;
        private float _resolveIn;

        // What the menu / config say.
        public bool Enabled = true;              // "Gaze control" switch
        public bool FollowsSpeaker = false;      // look at the client while someone speaks
        private string _defaultKey = KeyDefault;  // "default" | "client" | "camera" | "forward" | "atom:<uid>"

        // What the AI asked for (look_at): replaces the default until it ends or the user picks something.
        private string _aiKey;                   // key like _defaultKey, or KeyAway
        private float _aiLeft = -1f;             // seconds left; < 0 = until changed
        private int _awaySide = 1;

        // Steering state.
        private bool _taken;
        private EyesControl.LookMode _restoreMode;
        private Vector3 _restorePosition;
        private bool _yielded;                   // someone else changed the look mode: hands off
        private string _otherPlugin = "";        // "Glance" when found on this Person
        private float _otherCheckIn;
        private Atom _targetAtom;                // cached atom for an atom target
        private string _targetAtomName = "";
        private float _atomCheckIn;
        private string _status = "";

        public GazeController(Atom atom)
        {
            _atom = atom;
            Resolve();
        }

        public bool Available { get { return _eyes != null && _eyeTarget != null; } }
        public string Status { get { return _status; } }
        public bool Yielded { get { return _yielded; } }
        public string OtherPlugin { get { return _otherPlugin; } }
        public string DefaultKey { get { return _defaultKey; } }

        /// <summary>True while the AI may direct the gaze (switch on, no other eye plugin, not given back).</summary>
        public bool AiMayDirect { get { return Enabled && Available && _otherPlugin.Length == 0 && !_yielded; } }

        private void Resolve()
        {
            try
            {
                _eyes = _atom.GetStorableByID("Eyes") as EyesControl;                       // E12 L159, E28 L79
                _head = _atom.GetStorableByID("headControl") as FreeControllerV3;           // E6
                _eyeTarget = FindController(_atom, "eyeTargetControl");                    // E12 L178, E28 L83
            }
            catch (Exception)
            {
                _eyes = null;
                _eyeTarget = null;
            }
        }

        private static FreeControllerV3 FindController(Atom atom, string name)
        {
            FreeControllerV3[] all = atom.freeControllers;
            if (all == null) return null;
            for (int i = 0; i < all.Length; i++)
                if (all[i] != null && all[i].name == name) return all[i];
            return null;
        }

        // ---------------------------------------------------------------- commands

        /// <summary>Menu / config: the default gaze. Also ends any AI order and lets the AI-yielded state go.</summary>
        public void SetDefault(string key)
        {
            _defaultKey = string.IsNullOrEmpty(key) ? KeyDefault : key;
            _aiKey = null;
            _yielded = false;
            _targetAtom = null;
            _atomCheckIn = 0f;
        }

        /// <summary>The "look_at" command. Returns null, or a message for the error event.</summary>
        public string LookAt(string target, string atomName, float seconds)
        {
            if (!Enabled) return "Gaze control is off in the plugin menu (tab AI Character > Gaze).";
            if (_otherPlugin.Length > 0)
                return "Another plugin (" + _otherPlugin + ") controls the eyes of this Person, so AIBody leaves them alone.";
            if (_yielded)
                return "Another plugin changed the eyes, so AIBody stopped steering them. Pick 'Default gaze' in the menu to take over again.";
            if (!Available) return "No eye controls found on this Person (Eyes / eyeTargetControl).";
            string t = (target ?? "").Trim().ToLowerInvariant();
            if (seconds > MaxSeconds) seconds = MaxSeconds;
            if (t == KeyOff)
            {
                _aiKey = null;
                return null;
            }
            if (t == KeyAtom)
            {
                if (FindAtom(atomName) == null) return "No atom named '" + atomName + "' in the scene.";
                Own(AtomPrefix + atomName, seconds);
                return null;
            }
            if (t == KeyClient || t == KeyCamera || t == KeyForward)
            {
                Own(t, seconds);
                return null;
            }
            if (t == KeyAway)
            {
                _awaySide = -_awaySide;
                Own(KeyAway, seconds > 0f ? seconds : AwayDefaultSeconds);
                return null;
            }
            return "Unknown gaze target '" + target + "'. Use client, camera, forward, away, off or atom.";
        }

        private void Own(string key, float seconds)
        {
            _aiKey = key;
            _aiLeft = seconds > 0f ? seconds : -1f;
        }

        // ---------------------------------------------------------------- frame loop

        public void Update(float dt, bool aiSpeaking, bool userSpeaking)
        {
            if (_eyes == null || _eyeTarget == null)
            {
                _resolveIn -= dt;
                if (_resolveIn > 0f) { _status = Enabled ? "not available (no Eyes / eyeTargetControl on this Person yet)" : "off"; return; }
                _resolveIn = 5f;
                Resolve();
                if (_eyes == null || _eyeTarget == null) { _status = Enabled ? "not available (no Eyes / eyeTargetControl on this Person yet)" : "off"; return; }
            }
            _otherCheckIn -= dt;
            if (_otherCheckIn <= 0f)
            {
                _otherCheckIn = 3f;
                _otherPlugin = FindOtherEyePlugin();
            }
            if (_aiKey != null && _aiLeft > 0f)
            {
                _aiLeft -= dt;
                if (_aiLeft <= 0f) _aiKey = null;
            }

            // Someone else took the eyes while we were steering: give up (never fight).
            if (_taken && _eyes.currentLookMode != EyesControl.LookMode.Target)
            {
                _taken = false;
                _yielded = true;
            }

            if (!Enabled || _otherPlugin.Length > 0 || _yielded)
            {
                Release();
                if (!Enabled) _status = "off (Gaze control is switched off)";
                else if (_otherPlugin.Length > 0) _status = "paused: " + _otherPlugin + " is on this Person and controls the eyes";
                else _status = "stopped: another plugin changed the eyes. Pick 'Default gaze' to take over again";
                return;
            }

            string key = _aiKey;
            string why = "AI request";
            if (key == null && FollowsSpeaker && (aiSpeaking || userSpeaking))
            {
                key = KeyClient;
                why = aiSpeaking ? "AI is speaking" : "you are speaking";
            }
            if (key == null) { key = _defaultKey; why = "default gaze"; }
            if (key == KeyDefault) { Release(); _status = "VaM default (AIBody is not moving the eyes)"; return; }

            Vector3 point;
            string described;
            if (!TargetPoint(key, dt, out point, out described))
            {
                Release();
                _status = "target not found (" + key + "); eyes released";
                return;
            }
            Take();
            _eyeTarget.control.position = point;   // E12 L678, E28 L209
            _status = "looking at " + described + " (" + why + (_aiKey != null && _aiLeft > 0f ? ", " + _aiLeft.ToString("0") + " s left" : "") + ")";
        }

        private void Take()
        {
            if (_taken) return;
            _restoreMode = _eyes.currentLookMode;                 // E12 L652, E28 L108
            _restorePosition = _eyeTarget.control.position;       // E28 L109
            _eyes.currentLookMode = EyesControl.LookMode.Target;  // E12 L681, E28 L116
            _taken = true;
        }

        /// <summary>Gives the eyes back: restores the look mode and the eye target position (E28 L166-168).</summary>
        public void Release()
        {
            if (!_taken) return;
            _taken = false;
            if (_eyeTarget != null) _eyeTarget.control.position = _restorePosition;
            if (_eyes != null && _eyes.currentLookMode == EyesControl.LookMode.Target) _eyes.currentLookMode = _restoreMode;
        }

        public void RestoreNow()
        {
            Release();
            _aiKey = null;
        }

        // ---------------------------------------------------------------- targets

        private bool TargetPoint(string key, float dt, out Vector3 point, out string described)
        {
            point = Vector3.zero;
            described = key;
            if (key == KeyCamera) return CameraPoint(out point, out described);
            if (key == KeyClient)
            {
                Atom client = FindClient();
                if (client != null && AtomPoint(client, out point)) { described = "the client (" + client.uid + ")"; return true; }
                bool ok = CameraPoint(out point, out described);   // no client in the scene: the viewer
                described = "the camera (no client in the scene)";
                return ok;
            }
            if (key == KeyForward || key == KeyAway)
            {
                if (_head == null || _head.control == null) return false;
                Vector3 origin = _head.control.position;
                Quaternion facing = _atom.transform.rotation;
                if (key == KeyForward)
                {
                    point = origin + (facing * Vector3.forward) * ForwardDistance;
                    described = "straight ahead";
                }
                else
                {
                    point = origin + (facing * Quaternion.Euler(AwayPitch, AwayYaw * _awaySide, 0f) * Vector3.forward) * ForwardDistance;
                    described = "away";
                }
                return true;
            }
            if (key.StartsWith(AtomPrefix))
            {
                string name = key.Substring(AtomPrefix.Length);
                Atom found = CachedAtom(name, dt);
                if (found == null || !AtomPoint(found, out point)) return false;
                described = "atom " + found.uid;
                return true;
            }
            return false;
        }

        private static bool CameraPoint(out Vector3 point, out string described)
        {
            point = Vector3.zero;
            described = "the camera";
            CameraTarget cam = SuperController.singleton != null ? SuperController.singleton.centerCameraTarget : null;   // E12 L647
            if (cam == null) return false;
            point = cam.transform.position;
            return true;
        }

        private static bool AtomPoint(Atom a, out Vector3 point)
        {
            point = Vector3.zero;
            if (a == null) return false;
            FreeControllerV3 fc = null;
            if (a.type == "Person") fc = a.GetStorableByID("headControl") as FreeControllerV3;   // the face
            if (fc == null) fc = a.mainController;                                                // E12 L812, L957
            if (fc == null || fc.control == null) return false;
            point = fc.control.position;
            return true;
        }

        private Atom CachedAtom(string name, float dt)
        {
            _atomCheckIn -= dt;
            if (_targetAtom != null && _targetAtomName == name && _atomCheckIn > 0f) return _targetAtom;
            _atomCheckIn = 2f;
            _targetAtomName = name;
            _targetAtom = FindAtom(name);
            return _targetAtom;
        }

        /// <summary>An atom by uid (case does not matter), not this Person.</summary>
        public Atom FindAtom(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            List<Atom> atoms = SuperController.singleton != null ? SuperController.singleton.GetAtoms() : null;   // E12 L180
            if (atoms == null) return null;
            string wanted = name.Trim().ToLowerInvariant();
            for (int i = 0; i < atoms.Count; i++)
            {
                Atom a = atoms[i];
                if (a == null || a == _atom) continue;
                if (a.uid != null && a.uid.ToLowerInvariant() == wanted) return a;
            }
            return null;
        }

        /// <summary>The Client Character: the atom of that name, else the first other Person.</summary>
        public Atom FindClient()
        {
            Atom named = FindAtom(ClientAtomName);
            if (named != null) return named;
            List<Atom> atoms = SuperController.singleton != null ? SuperController.singleton.GetAtoms() : null;
            if (atoms == null) return null;
            for (int i = 0; i < atoms.Count; i++)
            {
                Atom a = atoms[i];
                if (a != null && a != _atom && a.type == "Person") return a;
            }
            return null;
        }

        /// <summary>Atoms the AI / the menu can look at: every other atom with a main controller, at most 30.</summary>
        public List<string> ListAtoms()
        {
            List<string> names = new List<string>();
            List<Atom> atoms = SuperController.singleton != null ? SuperController.singleton.GetAtoms() : null;
            if (atoms == null) return names;
            for (int i = 0; i < atoms.Count && names.Count < 30; i++)
            {
                Atom a = atoms[i];
                if (a == null || a == _atom || string.IsNullOrEmpty(a.uid)) continue;
                if (a.mainController == null) continue;
                names.Add(a.uid);
            }
            return names;
        }

        /// <summary>"Glance" when that plugin is on this Person: the same check Embody uses against Glance (E28).</summary>
        private string FindOtherEyePlugin()
        {
            try
            {
                List<string> ids = _atom.GetStorableIDs();   // E8, E28
                if (ids == null) return "";
                for (int i = 0; i < ids.Count; i++)
                {
                    if (ids[i].EndsWith("Glance")) return "Glance";
                }
            }
            catch (Exception) { }
            return "";
        }
    }
}
