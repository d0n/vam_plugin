// Poses, gestures and generic triggers.
//
// - Poses: loads a VaM pose preset (.vap / .json) through the atom's "PosePresets" storable,
//   which is how VaM's own preset UI loads poses. Poses from VaMHub (.var packages) can be
//   referenced with the usual "Author.Package.version:/Custom/Atom/Person/Pose/x.vap" path.
// - Triggers: calls an action or sets a parameter on any storable of the atom, e.g. another
//   plugin such as Timeline ("plugin#0_VamTimeline.AtomPlugin"), Life, Glance or E-Motion.
// - Gestures: named shortcuts defined in Saves/PluginData/AIBody/gestures.json that map to a
//   built-in head gesture, a pose, a Timeline animation or a trigger (see examples/gestures.json).
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;
using MVR.FileManagementSecure;

namespace AIBody
{
    public class PoseController
    {
        private readonly Atom _atom;
        private readonly IdleController _idle;
        private readonly Dictionary<string, JSONClass> _gestures =
            new Dictionary<string, JSONClass>(StringComparer.OrdinalIgnoreCase);

        public PoseController(Atom atom, IdleController idle)
        {
            _atom = atom;
            _idle = idle;
        }

        public IEnumerable<string> GestureNames { get { return new List<string>(_gestures.Keys); } }   // copy, no key enumerator

        /// <summary>VaM's pose preset folders that are listed (top level only, .vap / .json).</summary>
        public static readonly string[] PoseFolders = { "Custom/Atom/Person/Pose", "Custom/Atom/Person/Pose/AIBody" };
        public const int MaxPoseFiles = 200;

        private readonly Dictionary<string, string> _poseFiles =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public string PoseScanNote { get; private set; }

        /// <summary>
        /// Pose commands (version 32): the ONLY way the companion app applies a pose. Set up by Body from config.json
        /// poses.commands. A pose from the app is applied only through ApplyPoseJson, which checks it against this list.
        /// </summary>
        public readonly PoseVocabulary Vocabulary = new PoseVocabulary();

        /// <summary>Called after a pose preset was loaded (version 35: the idle motion forgets its old offsets).</summary>
        public Action OnPoseLoaded;

        /// <summary>
        /// Pose presets by name: gestures.json entries of kind "pose" first, then the preset files in
        /// PoseFolders (name = file name without "Preset_" and extension). Used by the pose menu in
        /// the tab AI Character and by the AI's pose tool (the plugin reports them as "poses").
        /// </summary>
        public List<string> PoseNames
        {
            get
            {
                List<string> names = new List<string>();
                foreach (KeyValuePair<string, JSONClass> kv in _gestures)
                    if (kv.Value["kind"].Value == "pose") names.Add(kv.Key);
                foreach (KeyValuePair<string, string> kv in _poseFiles)   // not the key collection (CS584 in VaM)
                    if (!names.Contains(kv.Key)) names.Add(kv.Key);
                return names;
            }
        }

        /// <summary>The menu name of a listed pose file (Add Pose, version 42), or null if the file is not in PoseFolders.</summary>
        public string PoseNameOfFile(string path)
        {
            if (string.IsNullOrEmpty(path)) return null;
            string want = path.Replace('\\', '/').ToLowerInvariant();
            foreach (KeyValuePair<string, string> kv in _poseFiles)   // not the key collection (CS584 in VaM)
                if (kv.Value.ToLowerInvariant() == want) return kv.Key;
            return null;
        }

        /// <summary>Lists the pose preset files (FileManagerSecure.GetFiles, E11).</summary>
        public void ScanPoseFiles()
        {
            _poseFiles.Clear();
            int folders = 0;
            foreach (string folder in PoseFolders)
            {
                string[] files = null;
                // TODO(verify): GetFiles on a Custom/ folder in the sandbox (E11 lists Saves/PluginData).
                try { files = FileManagerSecure.GetFiles(folder); }
                catch (Exception) { files = null; }   // folder missing or not readable
                if (files == null) continue;
                folders++;
                foreach (string f in files)
                {
                    if (_poseFiles.Count >= MaxPoseFiles) break;
                    string lower = f.ToLowerInvariant();
                    if (!lower.EndsWith(".vap") && !lower.EndsWith(".json")) continue;
                    string name = f.Replace('\\', '/');
                    name = name.Substring(name.LastIndexOf('/') + 1);
                    name = name.Substring(0, name.LastIndexOf('.'));
                    if (name.StartsWith("Preset_")) name = name.Substring(7);
                    if (name.Length > 0 && !_poseFiles.ContainsKey(name)) _poseFiles[name] = f.Replace('\\', '/');
                }
            }
            PoseScanNote = _poseFiles.Count + " pose files in " + string.Join(", ", PoseFolders)
                + (folders == 0 ? " (folders not readable or empty)" : "");
        }

        /// <summary>Self test: null if the pose storage LoadPose uses is there, else why not.</summary>
        public string CheckPoseStorage()
        {
            JSONStorable presets = _atom != null ? _atom.GetStorableByID("PosePresets") : null;
            if (presets == null) return "no storable 'PosePresets'";
            if (presets.GetUrlJSONParam("presetBrowsePath") == null) return "PosePresets without presetBrowsePath";
            return null;
        }

        /// <summary>Number of preset files found by ScanPoseFiles (GetFiles on Custom/...).</summary>
        public int PoseFileCount { get { return _poseFiles.Count; } }

        /// <summary>gestures.json entries of kind timeline; HasTimeline: their Timeline storables are all on the atom.</summary>
        public int TimelineGestureCount
        {
            get
            {
                int n = 0;
                foreach (KeyValuePair<string, JSONClass> kv in _gestures) if (kv.Value["kind"].Value == "timeline") n++;
                return n;
            }
        }

        public bool HasTimeline
        {
            get
            {
                foreach (KeyValuePair<string, JSONClass> kv in _gestures)
                    if (kv.Value["kind"].Value == "timeline"
                        && FindStorable(Protocol.GetString(kv.Value, "storable", "VamTimeline.AtomPlugin")) == null) return false;
                return true;
            }
        }

        /// <summary>
        /// The companion app's answer to a pose command: {"pose":"<id>"}. Parsed strictly, the id must belong to a command
        /// of this vocabulary and the character must have that pose; otherwise nothing is applied. Returns an error
        /// message (the caller logs a short warning), or null on success.
        /// </summary>
        public string ApplyPoseJson(string json)
        {
            string pose;
            string error = PoseVocabulary.ParsePoseJson(json, out pose);
            if (error != null) return error;
            PoseCommand entry = Vocabulary.FindByPoseId(pose);
            if (entry == null) return "'" + pose + "' is not a pose of the pose vocabulary";
            string actual = PoseVocabulary.Resolve(entry, PoseNames);
            if (actual == null) return "pose command '" + entry.Command + "' is unavailable: the character has no pose '" + entry.Pose + "'";
            return ApplyPose(actual);
        }

        /// <summary>Applies a pose by name (gestures.json pose, else a listed preset file). Only for the menu button and ApplyPoseJson.</summary>
        public string ApplyPose(string name)
        {
            if (string.IsNullOrEmpty(name)) return "No pose selected";
            if (PoseVocabulary.IsPosePath(name)) return LoadPose(name);   // a file chosen with Add Pose (version 42)
            JSONClass def;
            if (_gestures.TryGetValue(name, out def) && def["kind"].Value == "pose")
                return LoadPose(Protocol.GetString(def, "path", ""));
            string path;
            if (_poseFiles.TryGetValue(name, out path)) return LoadPose(path);
            return "Unknown pose '" + name + "'";
        }

        public void LoadGestureFile(string path)
        {
            try
            {
                if (!FileManagerSecure.FileExists(path)) return;
                JSONClass root = JSON.Parse(FileManagerSecure.ReadAllText(path)) as JSONClass;
                if (root == null)
                {
                    Log.Error("Invalid gestures file: " + path);
                    return;
                }
                _gestures.Clear();
                foreach (KeyValuePair<string, JSONNode> kv in root)
                {
                    JSONClass def = kv.Value as JSONClass;
                    if (def != null) _gestures[kv.Key] = def;
                }
                Log.Info("Loaded " + _gestures.Count + " gestures from " + path);
            }
            catch (Exception e)
            {
                Log.Error("Failed to load gestures from " + path, e);
            }
        }

        /// <summary>Plays a gesture by name. Returns an error message, or null on success.</summary>
        public string PlayGesture(string name, float duration, float amplitude)
        {
            JSONClass def;
            if (_gestures.TryGetValue(name ?? "", out def)) return RunDefinition(def, duration, amplitude);
            if (_idle != null && _idle.PlayHeadGesture(name, duration, amplitude)) return null;
            return "Unknown gesture '" + name + "'";
        }

        private string RunDefinition(JSONClass def, float duration, float amplitude)
        {
            string kind = Protocol.GetString(def, "kind", "");
            switch (kind)
            {
                case "head":
                    if (_idle == null) return "Head motion unavailable";
                    return _idle.PlayHeadGesture(Protocol.GetString(def, "name", ""),
                        duration > 0f ? duration : Protocol.GetFloat(def, "duration", 1.2f),
                        amplitude > 0f ? amplitude : Protocol.GetFloat(def, "amplitude", 1f))
                        ? null : "Unknown head gesture";
                case "pose":   // version 32: poses are applied only through the pose vocabulary (ApplyPoseJson), never as a gesture
                    return "Poses are applied only through pose commands, not as a gesture";
                case "timeline":
                    return PlayTimeline(Protocol.GetString(def, "storable", "VamTimeline.AtomPlugin"),
                        Protocol.GetString(def, "animation", ""));
                case "trigger":
                    return Trigger(def);
                default:
                    return "Gesture definition has unknown kind '" + kind + "'";
            }
        }

        /// <summary>Loads a pose preset. Returns an error message, or null on success.</summary>
        public string LoadPose(string path)
        {
            if (string.IsNullOrEmpty(path)) return "Pose path is empty";
            JSONStorable presets = _atom.GetStorableByID("PosePresets");
            if (presets == null) return "Atom has no PosePresets storable";
            // Same pattern as vamdeluxe's PresetRandomizer for the Morph/Hair/Skin preset storables:
            // presetBrowsePath = SuperController.singleton.NormalizePath(path), then CallAction("LoadPreset").
            // TODO(verify): the "PosePresets" storable follows the same pattern on 1.22.
            JSONStorableUrl url = presets.GetUrlJSONParam("presetBrowsePath");
            if (url == null) return "PosePresets has no presetBrowsePath parameter";
            url.val = SuperController.singleton.NormalizePath(path);
            presets.CallAction("LoadPreset");
            if (OnPoseLoaded != null) OnPoseLoaded();
            return null;
        }

        /// <summary>Starts a Timeline animation by name on the given Timeline storable.</summary>
        public string PlayTimeline(string storableHint, string animation)
        {
            if (string.IsNullOrEmpty(animation)) return "Timeline animation name is empty";
            JSONStorable timeline = FindStorable(storableHint);
            if (timeline == null) return "Timeline plugin not found on atom (looked for '" + storableHint + "')";
            // Timeline registers one "Play <animation>" action per animation and its own
            // ControllerPlugin calls it exactly like this (vam-timeline AtomPlugin / ControllerPlugin).
            timeline.CallAction("Play " + animation);
            return null;
        }

        /// <summary>
        /// Generic trigger. msg fields: storable (id or suffix), and either
        /// action, or param + value (+ optional value_type: float|bool|string|chooser).
        /// </summary>
        public string Trigger(JSONClass msg)
        {
            string hint = Protocol.GetString(msg, "storable", "");
            JSONStorable storable = FindStorable(hint);
            if (storable == null) return "Storable not found: '" + hint + "'";

            string action = Protocol.GetString(msg, "action", "");
            if (action.Length > 0)
            {
                storable.CallAction(action);
                return null;
            }

            string param = Protocol.GetString(msg, "param", "");
            if (param.Length == 0) return "Trigger needs 'action' or 'param'";
            string value = Protocol.GetString(msg, "value", "");
            string type = Protocol.GetString(msg, "value_type", "");
            return SetParam(storable, param, value, type);
        }

        private static string SetParam(JSONStorable storable, string param, string value, string type)
        {
            if (type == "" || type == "float")
            {
                JSONStorableFloat f = storable.GetFloatJSONParam(param);
                if (f != null)
                {
                    float v;
                    if (!float.TryParse(value, System.Globalization.NumberStyles.Float,
                        System.Globalization.CultureInfo.InvariantCulture, out v)) return "Value is not a number: " + value;
                    f.val = v;
                    return null;
                }
                if (type == "float") return "No float param '" + param + "'";
            }
            if (type == "" || type == "bool")
            {
                JSONStorableBool b = storable.GetBoolJSONParam(param);
                if (b != null)
                {
                    b.val = value == "true" || value == "1" || value == "True";
                    return null;
                }
                if (type == "bool") return "No bool param '" + param + "'";
            }
            if (type == "" || type == "chooser")
            {
                JSONStorableStringChooser c = storable.GetStringChooserJSONParam(param);
                if (c != null)
                {
                    c.val = value;
                    return null;
                }
                if (type == "chooser") return "No chooser param '" + param + "'";
            }
            JSONStorableString s = storable.GetStringJSONParam(param);
            if (s != null)
            {
                s.val = value;
                return null;
            }
            return "Param '" + param + "' not found on '" + storable.storeId + "'";
        }

        /// <summary>
        /// Finds a storable by exact id, or by suffix (plugin storables are named
        /// "plugin#N_Namespace.ClassName", so "VamTimeline.AtomPlugin" matches any slot).
        /// </summary>
        public JSONStorable FindStorable(string hint)
        {
            if (string.IsNullOrEmpty(hint)) return null;
            JSONStorable exact = _atom.GetStorableByID(hint);
            if (exact != null) return exact;
            List<string> ids = _atom.GetStorableIDs();
            for (int i = 0; i < ids.Count; i++)
            {
                if (ids[i].EndsWith(hint, StringComparison.Ordinal)) return _atom.GetStorableByID(ids[i]);
            }
            return null;
        }
    }
    /// <summary>Reset poses (version 42, Leon 18:27): where a Person's controllers were when the scene had loaded, and
    /// putting them back. Atom.freeControllers (E12, E28); FreeControllerV3.transform position / rotation read and set
    /// like IdleController does (E6).</summary>
    public class PlacementSnapshot
    {
        public readonly Atom Atom;
        private readonly FreeControllerV3[] _controllers;
        private readonly Vector3[] _positions;
        private readonly Quaternion[] _rotations;

        private PlacementSnapshot(Atom atom, FreeControllerV3[] controllers)
        {
            Atom = atom;
            _controllers = controllers;
            _positions = new Vector3[controllers.Length];
            _rotations = new Quaternion[controllers.Length];
            for (int i = 0; i < controllers.Length; i++)
            {
                if (controllers[i] == null) continue;
                _positions[i] = controllers[i].transform.position;
                _rotations[i] = controllers[i].transform.rotation;
            }
        }

        public int Count { get { return _controllers.Length; } }

        /// <summary>The placement of the atom now, or null without controllers.</summary>
        public static PlacementSnapshot Take(Atom atom)
        {
            if (atom == null || atom.freeControllers == null || atom.freeControllers.Length == 0) return null;
            FreeControllerV3[] copy = new FreeControllerV3[atom.freeControllers.Length];
            for (int i = 0; i < copy.Length; i++) copy[i] = atom.freeControllers[i];
            return new PlacementSnapshot(atom, copy);
        }

        /// <summary>Puts every controller back; returns how many were moved.</summary>
        public int Restore()
        {
            int moved = 0;
            for (int i = 0; i < _controllers.Length; i++)
            {
                if (_controllers[i] == null) continue;
                _controllers[i].transform.position = _positions[i];
                _controllers[i].transform.rotation = _rotations[i];
                moved++;
            }
            return moved;
        }
    }

    /// <summary>Body position (22.11.2026, Leon: body position control in the menu): moves the whole Person by moving every
    /// controller, the same calls as PlacementSnapshot (Atom.freeControllers, E12/E28; FreeControllerV3.transform position /
    /// rotation, E6). Forward / right follow the way the character faces (its main controller, flat); the turn is about the
    /// vertical axis through the main controller.</summary>
    public static class BodyMover
    {
        /// <summary>The flat facing direction of the atom (main controller forward without its up/down part).</summary>
        public static Vector3 Facing(Atom atom)
        {
            if (atom == null || atom.mainController == null) return Vector3.forward;
            Vector3 f = atom.mainController.transform.rotation * Vector3.forward;
            f = new Vector3(f.x, 0f, f.z);
            return f.magnitude < 0.001f ? Vector3.forward : f.normalized;
        }

        /// <summary>The world shift of a move of `forward` / `right` metres along the facing.</summary>
        public static Vector3 ShiftFor(Atom atom, float forward, float right)
        {
            Vector3 f = Facing(atom);
            return f * forward + Vector3.Cross(Vector3.up, f) * right;
        }

        /// <summary>Moves every controller by `shift`; returns how many moved.</summary>
        public static int Shift(Atom atom, Vector3 shift)
        {
            if (atom == null || atom.freeControllers == null) return 0;
            int moved = 0;
            for (int i = 0; i < atom.freeControllers.Length; i++)
            {
                FreeControllerV3 c = atom.freeControllers[i];
                if (c == null) continue;
                c.transform.position = c.transform.position + shift;
                moved++;
            }
            return moved;
        }

        /// <summary>Turns every controller by `degrees` about the vertical axis through the main controller.</summary>
        public static int Turn(Atom atom, float degrees)
        {
            if (atom == null || atom.freeControllers == null || atom.mainController == null) return 0;
            Vector3 pivot = atom.mainController.transform.position;
            Quaternion turn = Quaternion.Euler(0f, degrees, 0f);
            int moved = 0;
            for (int i = 0; i < atom.freeControllers.Length; i++)
            {
                FreeControllerV3 c = atom.freeControllers[i];
                if (c == null) continue;
                c.transform.position = pivot + turn * (c.transform.position - pivot);
                c.transform.rotation = turn * c.transform.rotation;
                moved++;
            }
            return moved;
        }
    }
}
