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

        public IEnumerable<string> GestureNames { get { return _gestures.Keys; } }

        /// <summary>VaM's pose preset folders that are listed (top level only, .vap / .json).</summary>
        public static readonly string[] PoseFolders = { "Custom/Atom/Person/Pose", "Custom/Atom/Person/Pose/AIBody" };
        public const int MaxPoseFiles = 200;

        private readonly Dictionary<string, string> _poseFiles =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public string PoseScanNote { get; private set; }

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
                foreach (string n in _poseFiles.Keys)
                    if (!names.Contains(n)) names.Add(n);
                return names;
            }
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
            PoseScanNote = _poseFiles.Count + " Pose-Dateien in " + string.Join(", ", PoseFolders)
                + (folders == 0 ? " (Ordner nicht lesbar oder leer)" : "");
        }

        /// <summary>Self test: null if the pose storage LoadPose uses is there, else why not.</summary>
        public string CheckPoseStorage()
        {
            JSONStorable presets = _atom != null ? _atom.GetStorableByID("PosePresets") : null;
            if (presets == null) return "kein Storable 'PosePresets'";
            if (presets.GetUrlJSONParam("presetBrowsePath") == null) return "PosePresets ohne presetBrowsePath";
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
                foreach (JSONClass def in _gestures.Values) if (def["kind"].Value == "timeline") n++;
                return n;
            }
        }

        public bool HasTimeline
        {
            get
            {
                foreach (JSONClass def in _gestures.Values)
                    if (def["kind"].Value == "timeline"
                        && FindStorable(Protocol.GetString(def, "storable", "VamTimeline.AtomPlugin")) == null) return false;
                return true;
            }
        }

        /// <summary>Applies a pose by name (gestures.json pose, else a listed preset file).</summary>
        public string ApplyPose(string name)
        {
            if (string.IsNullOrEmpty(name)) return "Keine Pose gewählt";
            JSONClass def;
            if (_gestures.TryGetValue(name, out def) && def["kind"].Value == "pose")
                return LoadPose(Protocol.GetString(def, "path", ""));
            string path;
            if (_poseFiles.TryGetValue(name, out path)) return LoadPose(path);
            return "Unbekannte Pose '" + name + "'";
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
                case "pose":
                    return LoadPose(Protocol.GetString(def, "path", ""));
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
}
