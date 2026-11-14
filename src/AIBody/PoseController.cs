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
            // TODO(verify): param/action names as used by VaM 1.22's preset manager UI
            // ("presetBrowsePath" + "LoadPreset"). Alternative: "LoadPresetWithPath" if present.
            JSONStorableUrl url = presets.GetUrlJSONParam("presetBrowsePath");
            if (url == null) return "PosePresets has no presetBrowsePath parameter";
            url.val = path;
            presets.CallAction("LoadPreset");
            return null;
        }

        /// <summary>Starts a Timeline animation by name on the given Timeline storable.</summary>
        public string PlayTimeline(string storableHint, string animation)
        {
            if (string.IsNullOrEmpty(animation)) return "Timeline animation name is empty";
            JSONStorable timeline = FindStorable(storableHint);
            if (timeline == null) return "Timeline plugin not found on atom (looked for '" + storableHint + "')";
            // TODO(verify): Timeline exposes one "Play <animation>" action per animation.
            string action = "Play " + animation;
            if (!HasAction(timeline, action)) return "Timeline has no action '" + action + "'";
            timeline.CallAction(action);
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
                if (!HasAction(storable, action)) return "Storable '" + storable.storeId + "' has no action '" + action + "'";
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

        private static bool HasAction(JSONStorable storable, string action)
        {
            List<string> names = storable.GetActionNames();
            return names != null && names.Contains(action);
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
