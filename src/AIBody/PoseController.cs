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

        /// <summary>Version 66: pose files the origin reset skipped this session (a pose that throws the body far away); they are
        /// not applied again until the plugin reloads (ApplyCommand then takes a substitute pose).</summary>
        private readonly HashSet<string> _badPoses = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        public int BadPoseCount { get { return _badPoses.Count; } }

        public PoseController(Atom atom, IdleController idle)
        {
            Guard = new PoseGuard(atom);
            Guard.OnRejected = (string key) =>
            {
                if (string.IsNullOrEmpty(key)) return;
                _badPoses.Add(key);
                string name = PoseNameOfFile(key);
                if (name != null && OnPoseBroken != null) OnPoseBroken(name);   // out of the idle pool for the session, like a broken file
            };
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

        /// <summary>Version 52: called right BEFORE a pose preset is loaded (the idle motion takes its offsets off and holds
        /// still while VaM applies the pose, so only one system writes the body).</summary>
        public Action BeforePoseLoad;

        /// <summary>Version 52: seconds after a pose load in which the result is checked (did any controller move?).</summary>
        public const float SettleSeconds = 1.0f;
        private float _checkIn = -1f;
        private string _checkPose = "";
        private Vector3[] _beforePositions;

        /// <summary>Version 52: the result of the last pose load once it settled ("" while none), for the info field and the log.</summary>
        public string LastLoadCheck { get; private set; }

        /// <summary>Version 54/56: a pose file may store the root node (its world XYZ and turn); VaM then puts the whole person
        /// there and she leaves her place. Every pose change of the plugin goes through ONE wrapper, PoseGuard.Around (this
        /// Guard): her place is taken right before the load and put back right after it and on the following frames while VaM
        /// settles. The pose files are never changed.</summary>
        public readonly PoseGuard Guard;
        /// <summary>Version 54: "" or the last time a pose moved the root and the plugin put the person back (info field).</summary>
        public string LastPlaceNote { get { return Guard.LastNote; } }

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

        /// <summary>Version 54: the folder whose pose files idle poses use on their own (the others only with
        /// the pool "All pose files" of the menu "Idle pose pool", or when a pose command links them).</summary>
        public const string OwnPoseFolder = "Custom/Atom/Person/Pose/AIBody";

        /// <summary>True for a pose file in OwnPoseFolder (the path as GetFiles returned it, any slash, any case).</summary>
        public static bool IsOwnPoseFile(string path)
        {
            string p = (path ?? "").Replace('\\', '/').ToLowerInvariant();
            return p.Contains("/pose/aibody/") || p.StartsWith("pose/aibody/");
        }

        /// <summary>Version 54: the poses idle poses may pick on their own: gestures.json poses and OwnPoseFolder files, or every
        /// listed pose file with allFiles (menu "Idle pose pool" = "All pose files", version 66).</summary>
        public List<string> IdlePoolNames(bool allFiles)
        {
            List<string> names = new List<string>();
            foreach (KeyValuePair<string, JSONClass> kv in _gestures)
                if (kv.Value["kind"].Value == "pose") names.Add(kv.Key);
            foreach (KeyValuePair<string, string> kv in _poseFiles)   // not the key collection (CS584 in VaM)
                if ((allFiles || IsOwnPoseFile(kv.Value)) && !names.Contains(kv.Key)) names.Add(kv.Key);
            return names;
        }

        /// <summary>Version 54: why a listed pose FILE cannot be used (missing), or null (also for gestures.json / unknown names).</summary>
        public string PoseFileProblem(string name)
        {
            string path;
            if (string.IsNullOrEmpty(name) || !_poseFiles.TryGetValue(name, out path)) return null;
            bool exists = true;
            try { exists = FileManagerSecure.FileExists(path); } catch (Exception) { exists = true; }   // E10
            return exists ? null : "pose file not found: " + path;
        }

        /// <summary>Version 57: the file of a listed pose (for log lines), or null (a gestures.json pose, unknown name).</summary>
        public string PathOf(string name)
        {
            string path;
            if (string.IsNullOrEmpty(name) || !_poseFiles.TryGetValue(name, out path)) return null;
            return path;
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
                    // Version 52: pose presets only (.vap); a .json there is no pose preset and PosePresets cannot load it.
                    if (!lower.EndsWith(".vap")) continue;
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

        /// <summary>Version 56: the pose and the command the last ApplyPoseJson resolved (Body: idle poses, status note).</summary>
        public string LastJsonPose { get; private set; }
        public string LastJsonCommand { get; private set; }

        /// <summary>Version 58/59: picks the substitute for a command whose own pose is missing or broken (Body: a random pose
        /// of the idle pool, else the idle default pose); null = none.</summary>
        public Func<PoseCommand, string> SubstituteFor;
        /// <summary>Version 58: the last ApplyPoseJson used a substitute pose.</summary>
        public bool LastJsonSubstitute { get; private set; }

        /// <summary>
        /// The companion app's answer to a pose command: {"pose":"<id>"}. Parsed strictly, the id must belong to a command
        /// of this vocabulary (version 59: a missing or broken pose gets a substitute pose, ApplyCommand); otherwise nothing is
        /// applied. Returns an error
        /// message (the caller logs a short warning), or null on success.
        /// </summary>
        public string ApplyPoseJson(string json)
        {
            string pose;
            string error = PoseVocabulary.ParsePoseJson(json, out pose);
            if (error != null) return error;
            PoseCommand entry = Vocabulary.FindByPoseId(pose);
            if (entry == null) return "'" + pose + "' is not a pose of the pose vocabulary";
            return ApplyCommand(entry);
        }

        /// <summary>Version 59: how many substitute poses a command tries when they fail too (each failure is dropped).</summary>
        public const int MaxSubstituteTries = 5;
        /// <summary>Version 59: why the command's own pose was not used, when LastJsonSubstitute ("" otherwise).</summary>
        public string LastJsonProblem { get; private set; }
        /// <summary>Version 59: a pose file that failed to load (Body drops it from the idle pool for the session).</summary>
        public Action<string> OnPoseBroken;

        /// <summary>
        /// Version 59: ONE failover for every pose command (built-in or the user's own; spoken, typed, realtime or Apply
        /// Pose): its pose is loaded; when that pose is missing or its file is broken, a substitute (SubstituteFor: a random
        /// idle-pool pose without failed files and without the current pose, else the Idle default pose) is loaded instead.
        /// There is no "unavailable" command. Returns null when a pose was applied (LastJsonPose, LastJsonSubstitute).
        /// </summary>
        public string ApplyCommand(PoseCommand entry)
        {
            if (entry == null) return "no pose command";
            LastJsonCommand = entry.Command;
            LastJsonSubstitute = false;
            LastJsonProblem = "";
            string actual = PoseVocabulary.Resolve(entry, PoseNames);
            string problem = actual == null ? "this character has no pose '" + entry.Pose + "'" : TryApply(actual);
            if (problem == null) { LastJsonPose = actual; return null; }
            if (actual != null && OnPoseBroken != null) OnPoseBroken(actual);
            for (int i = 0; i < MaxSubstituteTries && SubstituteFor != null; i++)
            {
                string sub = SubstituteFor(entry);
                if (sub == null) break;
                string subProblem = TryApply(sub);
                if (subProblem == null)
                {
                    LastJsonPose = sub;
                    LastJsonSubstitute = true;
                    LastJsonProblem = problem;
                    return null;
                }
                if (OnPoseBroken != null) OnPoseBroken(sub);
                else break;
            }
            return "pose command '" + entry.Command + "': " + problem + ", and no other pose could be loaded instead";
        }

        /// <summary>Version 59: loads one pose; null = ok, else why not (missing file, load error, exception).</summary>
        private string TryApply(string name)
        {
            try { return PoseFileProblem(name) ?? ApplyPose(name); }
            catch (Exception e) { return "loading '" + name + "' failed: " + e.Message; }
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

        /// <summary>
        /// Loads a pose preset. Returns an error message, or null on success.
        /// Version 52 (Don 20:47, "pose commands do not work, the character twitches"): the pose is loaded ONCE.
        /// Up to v51 the path was set while VaM's "Load On Select" (PosePresets.loadPresetOnSelect, on by default) was on:
        /// setting presetBrowsePath already loaded the pose, and CallAction("LoadPreset") loaded it a second time. And the
        /// idle head / chest motion went on writing the head and chest controllers while VaM applied the pose. Now:
        /// Load On Select off while the path is set (put back afterwards; the same as varManager's loadscene.cs), the idle
        /// motion takes its offsets off before and holds still for SettleSeconds (BeforePoseLoad), a .json (legacy pose,
        /// no preset) is refused with a clear message, and SettleSeconds later the plugin checks that the body moved.
        /// </summary>
        public string LoadPose(string path)
        {
            if (string.IsNullOrEmpty(path)) return "Pose path is empty";
            if (path.ToLowerInvariant().EndsWith(".json"))
                return "'" + path + "' is a .json file, not a pose preset (.vap): load it in VaM and save it as a pose preset (tab Pose)";
            if (_atom == null) return "No AI character";
            if (_badPoses.Contains(path))
                return "'" + path + "' was skipped earlier this session: it threw the character far away (the origin reset refused it); not applied again until the plugin reloads";
            JSONStorable presets = _atom.GetStorableByID("PosePresets");
            if (presets == null) return "Atom has no PosePresets storable";
            // presetBrowsePath = SuperController.singleton.NormalizePath(path), then CallAction("LoadPreset") (E7);
            // loadPresetOnSelect off meanwhile (E40, varManager loadscene.cs).
            JSONStorableUrl url = presets.GetUrlJSONParam("presetBrowsePath");
            if (url == null) return "PosePresets has no presetBrowsePath parameter";
            bool exists = true;
            try { exists = FileManagerSecure.FileExists(path); } catch (Exception) { exists = true; }   // E10; a check only
            if (!exists) Log.Warn("Pose file not found by FileManagerSecure.FileExists (loading it anyway): " + path);
            JSONStorableBool onSelect = presets.GetBoolJSONParam("loadPresetOnSelect");
            bool onSelectWas = onSelect != null && onSelect.val;
            if (BeforePoseLoad != null) BeforePoseLoad();
            StartCheck(path);
            Guard.PoseKey = path;   // version 66: for the bad list when the origin reset skips this pose
            // Version 56: the one position-preserving wrapper of every pose change (capture -> load -> put back, then on the
            // next frames until VaM has settled the pose)
            Guard.Around("pose " + Short(path), () =>
            {
                try
                {
                    if (onSelect != null && onSelectWas) onSelect.val = false;
                    url.val = SuperController.singleton.NormalizePath(path);
                    presets.CallAction("LoadPreset");
                }
                finally
                {
                    if (onSelect != null && onSelectWas) onSelect.val = true;
                }
                return null;
            }, null);
            Log.Debug("Pose preset loaded once: " + path + " on '" + _atom.uid + "' (Load On Select was " + (onSelectWas ? "on" : "off") + ")");
            if (OnPoseLoaded != null) OnPoseLoaded();
            return null;
        }

        private void StartCheck(string path)
        {
            _checkPose = path;
            _checkIn = SettleSeconds;
            FreeControllerV3[] all = _atom.freeControllers;   // E12, E28
            _beforePositions = new Vector3[all != null ? all.Length : 0];
            for (int i = 0; i < _beforePositions.Length; i++) if (all[i] != null) _beforePositions[i] = all[i].transform.position;
        }

        /// <summary>Version 52: SettleSeconds after a pose load, how far the controllers moved (the log says if none did).</summary>
        public void Update(float dt)
        {
            Guard.Update(dt);   // version 56: every frame while VaM settles the pose
            if (_checkIn < 0f) return;
            _checkIn -= dt;
            if (_checkIn > 0f) return;
            _checkIn = -1f;
            FreeControllerV3[] all = _atom != null ? _atom.freeControllers : null;
            int moved = 0;
            float most = 0f;
            for (int i = 0; all != null && i < all.Length && i < _beforePositions.Length; i++)
            {
                if (all[i] == null) continue;
                float d = (all[i].transform.position - _beforePositions[i]).magnitude;
                if (d > 0.01f) moved++;
                if (d > most) most = d;
            }
            LastLoadCheck = moved > 0
                ? "pose " + Short(_checkPose) + ": " + moved + " controllers moved (up to " + (most * 100f).ToString("0") + " cm)"
                : "pose " + Short(_checkPose) + ": no controller moved (it was already in this pose, or VaM did not load the file: open it in VaM's Pose tab to check)";
            if (moved > 0) Log.Debug(LastLoadCheck); else Log.Warn(LastLoadCheck);
        }

        private static string Short(string path)
        {
            string p = (path ?? "").Replace('\\', '/');
            return "'" + p.Substring(p.LastIndexOf('/') + 1) + "'";
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
    /// <summary>Reset poses (version 42, Don 18:27): where a Person's controllers were when the scene had loaded, and
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

    /// <summary>Body position (22.11.2026, Don: body position control in the menu): moves the whole Person by moving every
    /// controller, the same calls as PlacementSnapshot (Atom.freeControllers, E12/E28; FreeControllerV3.transform position /
    /// rotation, E6). Forward / right follow the way the character faces (its main controller, flat); the turn is about the
    /// vertical axis through the main controller.
    /// Version 54 (Don 23:28 "relocating the body does not work"): up to v53 every controller got "+ shift" on top of where
    /// it was, one after the other. In VaM the other controllers of a Person ride on its main controller (the root node
    /// carries the whole person), so moving the main controller first already moved them and the "+ shift" moved them a
    /// second time: the body was pulled apart and physics pulled it back. Now every move is RIGID and ABSOLUTE: all
    /// positions / rotations are read first, the main controller is set first, then every other controller is set to its
    /// own absolute target - right whether VaM moves the others with the main controller or not.</summary>
    /// <summary>
    /// Version 56 (Don, call 24.11.2026 15:27): the ONE position-preserving wrapper of every pose change: pose files and
    /// pose commands, the AI's pose tool (pose command from the companion), idle poses, Apply Pose / Apply idle default pose,
    /// Dollmaster montages. Around(): 1) capture the character's world placement (main controller position X, Y, Z AND
    /// rotation) right before the load, 2) run the load, 3) put her back rigidly (BodyMover.Relocate, the new pose kept).
    /// VaM may apply a pose over several frames (physics settling, a paused simulation), so Update() keeps putting her back
    /// every frame for at least MinSeconds and until nothing moved her for QuietSeconds (at most MaxSeconds). A pose change
    /// that starts while the guard runs keeps the first capture (never a half-moved place). A deliberate move (Body position,
    /// Reset poses, Reset body position) calls Rebase so the guard keeps the new place.
    /// </summary>
    public class PoseGuard
    {
        public const float MinSeconds = PoseController.SettleSeconds + 0.5f;
        public const float QuietSeconds = 0.5f;
        public const float MaxSeconds = 5f;
        /// <summary>Always on (no menu); false only for tests.</summary>
        public bool Enabled = true;
        /// <summary>Version 63: toggle "Center body on control point" (config.json body.pose_root_reset, default on): while the
        /// guard runs the body is also put back over the control point (BodyMover.CenterOnControl), the pose kept.</summary>
        public bool CenterBody = RootReset.DefaultOn;
        /// <summary>The "what" of a Dollmaster montage (DmMontageController passes exactly this text).</summary>
        public const string MontageWhat = "Dollmaster montage";
        private bool _center;
        private bool _centerNoted;

        // ---- version 66 (SOP-10, Don 26.11.2026): the ORIGIN root reset --------------------------------------------------
        // The hips' world position is captured once when the scene has loaded (CaptureOrigin, from Body via AIBodyPlugin.TakePlacement).
        // When a pose has settled (MinSeconds / QuietSeconds, at most MaxSeconds) ONE step moves every controller of the atom by the
        // same flat world delta (origin - hips), the pose's own offsets and every rotation untouched; the height stays (a sitting or
        // lying pose keeps its floor height). Physics is suspended around it (SuspendPhysics: every controller's position state is
        // Lock while the move is made and for UnlockSeconds after it, then put back) so the joints are not whipped by a big move.
        // Body position moves the origin along with her (SetOriginForPlace); Reset poses / Reset body position put it back.
        // A delta over OriginReset.MaxDeltaMetres, a controller that is NaN or that far away: the pose is SKIPPED (Reject): the
        // look from right before the load is put back, the pose goes on the session's bad list and a warning says so.
        // TODO(verify in VaM): FreeControllerV3.PositionState.Lock makes the controller's body follow its transform at once (the
        // enum and currentPositionState are used by Dollmaster, E39; the Lock behaviour itself was not checked in VaM).
        /// <summary>Seconds the controllers stay locked after the origin move.</summary>
        public const float UnlockSeconds = 0.3f;
        private bool _hasOrigin;
        private Vector3 _origin0, _origin;
        private Vector3 _originLocal0;   // the hips in the main controller's frame at capture
        private bool _originDone;
        private float _unlockIn = -1f;
        private FreeControllerV3[] _locked;
        private FreeControllerV3.PositionState[] _lockedStates;
        private PlacementSnapshot _snap;
        /// <summary>The key of the pose being loaded (its file path), for the bad list; set by PoseController before Around.</summary>
        public string PoseKey = "";
        /// <summary>Called with PoseKey when a pose was skipped (PoseController keeps the bad list).</summary>
        public Action<string> OnRejected;
        /// <summary>How many poses were skipped since the start.</summary>
        public int Rejected { get; private set; }
        public bool HasOrigin { get { return _hasOrigin; } }
        /// <summary>The origin now (world), valid when HasOrigin.</summary>
        public Vector3 Origin { get { return _origin; } }
        private bool UseOrigin { get { return _center && _hasOrigin; } }

        /// <summary>Captures the hips' world position now (call once after the scene has loaded).</summary>
        public bool CaptureOrigin()
        {
            if (_atom == null || _atom.mainController == null) return false;
            FreeControllerV3 hip = _atom.GetStorableByID(RootReset.BodyControl) as FreeControllerV3;
            if (hip == null) return false;
            Transform main = _atom.mainController.transform;
            _origin0 = hip.transform.position;
            _origin = _origin0;
            _originLocal0 = Quaternion.Inverse(main.rotation) * (_origin0 - main.position);
            _hasOrigin = !(float.IsNaN(_origin0.x) || float.IsNaN(_origin0.z) || float.IsInfinity(_origin0.x) || float.IsInfinity(_origin0.z));
            if (_hasOrigin)
                Log.Info("Origin of '" + _atom.uid + "' captured: hips at " + _origin0.x.ToString("0.000") + " / " + _origin0.y.ToString("0.000") + " / "
                    + _origin0.z.ToString("0.000") + " (a pose that settles elsewhere is moved back here)");
            return _hasOrigin;
        }

        /// <summary>A deliberate move of her place (Body position): the origin goes with her (same offset to the main controller).</summary>
        public void SetOriginForPlace(Vector3 pos, Quaternion rot)
        {
            if (_hasOrigin) _origin = pos + rot * _originLocal0;
        }

        /// <summary>Back to the origin of the scene load (Reset poses).</summary>
        public void ResetOrigin() { if (_hasOrigin) _origin = _origin0; }

        private string Runaway()
        {
            FreeControllerV3[] all = _atom.freeControllers;
            if (all == null || _atom.mainController == null) return null;
            Vector3 m = _atom.mainController.transform.position;
            for (int i = 0; i < all.Length; i++)
            {
                if (all[i] == null) continue;
                Vector3 p = all[i].transform.position;
                if (!OriginReset.Sane(p.x, p.y, p.z, m.x, m.y, m.z, OriginReset.MaxDeltaMetres))
                    return "controller '" + all[i].name + "' is " + (float.IsNaN(p.x + p.y + p.z) ? "not a number" : (p - m).magnitude.ToString("0") + " m away");
            }
            return null;
        }

        private void SuspendPhysics()
        {
            if (_locked != null || _atom == null || _atom.freeControllers == null) return;
            FreeControllerV3[] all = _atom.freeControllers;
            _locked = new FreeControllerV3[all.Length];
            _lockedStates = new FreeControllerV3.PositionState[all.Length];
            for (int i = 0; i < all.Length; i++)
            {
                if (all[i] == null) continue;
                _locked[i] = all[i];
                _lockedStates[i] = all[i].currentPositionState;
                all[i].currentPositionState = FreeControllerV3.PositionState.Lock;
            }
        }

        private void ResumePhysics()
        {
            if (_locked == null) return;
            for (int i = 0; i < _locked.Length; i++) if (_locked[i] != null) _locked[i].currentPositionState = _lockedStates[i];
            _locked = null;
            _lockedStates = null;
        }

        /// <summary>The other people's hips and chests (flat x, z pairs) for the collision check.</summary>
        private float[] OthersFlat()
        {
            List<float> xz = new List<float>();
            List<Atom> atoms = SuperController.singleton != null ? SuperController.singleton.GetAtoms() : null;
            if (atoms == null) return xz.ToArray();
            for (int i = 0; i < atoms.Count; i++)
            {
                Atom a = atoms[i];
                if (a == null || a == _atom || a.type != "Person") continue;
                string[] ids = { RootReset.BodyControl, "chestControl" };
                for (int k = 0; k < ids.Length; k++)
                {
                    FreeControllerV3 c = a.GetStorableByID(ids[k]) as FreeControllerV3;
                    if (c == null) continue;
                    xz.Add(c.transform.position.x);
                    xz.Add(c.transform.position.z);
                }
            }
            return xz.ToArray();
        }

        /// <summary>Skips the pose: the look from before the load is put back (physics suspended), the pose is reported as bad.</summary>
        private void Reject(string reason)
        {
            Rejected++;
            string key = PoseKey;
            LastNote = Capital(_what) + " skipped: " + reason + "; the previous pose was put back";
            Log.Warn(Capital(_what) + " was NOT applied: " + reason + ". The previous look was put back and the pose is on the bad list for this "
                + "session (it is not applied again until the plugin reloads).");
            if (_snap != null)
            {
                SuspendPhysics();
                _snap.Restore();
                _pos = _atom.mainController.transform.position;
                _rot = _atom.mainController.transform.rotation;
                _unlockIn = UnlockSeconds;
                _originDone = true;
            }
            else _age = -1f;
            if (OnRejected != null) OnRejected(key);
        }

        /// <summary>The ONE origin move of a settled pose; true when the guard has to wait for the unlock (or the pose was skipped).</summary>
        private bool ApplyOrigin()
        {
            FreeControllerV3 hip = _atom.GetStorableByID(RootReset.BodyControl) as FreeControllerV3;
            if (hip == null) return false;
            Vector3 h = hip.transform.position;
            float dx, dz;
            int v = OriginReset.Delta(_origin.x, _origin.z, h.x, h.z, RootReset.ToleranceMetres, out dx, out dz);
            if (v == OriginReset.Tiny) { Log.Debug(Capital(_what) + ": hips already at the origin"); return false; }
            if (v == OriginReset.Absurd)
            {
                Reject("the hips settled " + (h - _origin).magnitude.ToString("0") + " m from her place (limit " + OriginReset.MaxDeltaMetres.ToString("0") + " m)");
                return true;
            }
            float tx = _origin.x, tz = _origin.z;
            bool shifted = OriginReset.Sideways(h.x, h.z, ref tx, ref tz, OthersFlat(), OriginReset.ClearanceMetres);
            if (shifted)
            {
                dx = tx - h.x; dz = tz - h.z;
                Log.Info(Capital(_what) + ": another person stands within " + OriginReset.ClearanceMetres.ToString("0.0") + " m of her place: moved sideways to clear it");
            }
            SuspendPhysics();
            BodyMover.Shift(_atom, new Vector3(dx, 0f, dz));
            string bad = Runaway();
            if (bad != null) { Reject("after the move " + bad); return true; }
            Vector3 after = hip.transform.position;
            float dist = (float)Math.Sqrt((after.x - _origin.x) * (after.x - _origin.x) + (after.z - _origin.z) * (after.z - _origin.z));
            _pos = _atom.mainController.transform.position;   // the guard keeps the new place, not the old one
            _rot = _atom.mainController.transform.rotation;
            _unlockIn = UnlockSeconds;
            Centers++;
            LastCenterNote = _what + ": body moved " + Math.Sqrt(dx * dx + dz * dz).ToString("0.00") + " m back to her place (origin)";
            Log.Info(OriginReset.LogLine(_what, dx, dz, dist, shifted));
            return true;
        }

        /// <summary>"" or the last time a pose change was re-centred over the control point (info field).</summary>
        public string LastCenterNote { get; private set; }
        /// <summary>How often the body was re-centred since the start (Verbose log, tests).</summary>
        public int Centers { get; private set; }
        private readonly Atom _atom;
        private Vector3 _pos;
        private Quaternion _rot;
        private float _age = -1f;
        private float _quiet;
        private bool _noted;
        private string _what = "";
        /// <summary>"" or the last time a pose change moved her and she was put back (info field).</summary>
        public string LastNote { get; private set; }
        /// <summary>How often she was put back since the start (Verbose log, tests).</summary>
        public int Restores { get; private set; }
        public bool Active { get { return _age >= 0f; } }

        public PoseGuard(Atom atom) { _atom = atom; LastNote = ""; LastCenterNote = ""; }

        /// <summary>Capture -> load -> put back. partner (Dollmaster montage: the other person) gets the same correction, so
        /// the two keep their arrangement while the AI stays at her place. Returns load's result (null = ok).</summary>
        public string Around(string what, Func<string> load, Atom partner)
        {
            Begin(what);
            // version 63: a Dollmaster montage (with or without a partner) is never re-centred (RootReset.Applies)
            if (partner != null || what == MontageWhat) _center = RootReset.Applies(CenterBody, true);
            Vector3 fromPos = _pos;
            Quaternion fromRot = _rot;
            string result;
            try { result = load(); }
            finally
            {
                if (partner != null && Active && _atom != null && _atom.mainController != null && partner != _atom
                    && partner.mainController != null)
                {
                    // the correction that takes the AI back, applied to the partner as well (rigid, arrangement kept)
                    Transform t = _atom.mainController.transform;
                    Quaternion back = fromRot * Quaternion.Inverse(t.rotation);
                    Transform p = partner.mainController.transform;
                    BodyMover.Relocate(partner, fromPos + back * (p.position - t.position), back * p.rotation);
                }
                Hold();
            }
            return result;
        }

        /// <summary>Takes her place before a pose change (kept if a guard still runs: that place is the right one).</summary>
        public void Begin(string what)
        {
            if (!Enabled || _atom == null || _atom.mainController == null) return;
            bool wasActive = Active;
            if (!Active)
            {
                _pos = _atom.mainController.transform.position;
                _rot = _atom.mainController.transform.rotation;
            }
            _age = 0f;
            _quiet = 0f;
            _noted = false;
            _what = what ?? "";
            _center = RootReset.Applies(CenterBody, false);   // version 63
            _centerNoted = false;
            ResumePhysics();   // version 66: a new pose change while the controllers are locked: free them first
            _unlockIn = -1f;
            _originDone = false;
            if (!wasActive) _snap = UseOrigin ? PlacementSnapshot.Take(_atom) : null;   // the look right before the load (kept while a guard runs)
        }

        /// <summary>Puts her back if the pose change moved her (position or rotation).</summary>
        public void Hold()
        {
            if (!Active || _atom == null) return;
            if (UseOrigin && _unlockIn < 0f)
            {
                string bad = Runaway();   // version 66: a pose that throws the body far away is skipped at once, not chased
                if (bad != null) { Reject(bad); return; }
            }
            if (!UseOrigin) Center();   // version 63: the body back over the control point (the pose kept); version 66: with an origin ApplyOrigin does it once, settled
            if (_unlockIn >= 0f) return;   // locked after the origin move: nothing else moves her
            if (!BodyMover.Moved(_atom, _pos, _rot)) return;
            float cm = (_atom.mainController.transform.position - _pos).magnitude * 100f;
            BodyMover.Relocate(_atom, _pos, _rot);
            _quiet = 0f;
            Restores++;
            if (_noted) return;   // one note per pose change (VaM may push her again for a frame or two)
            _noted = true;
            LastNote = _what + " stores a root position or turn (" + cm.ToString("0") + " cm away): the character was put back to her place";
            Log.Info(Capital(_what) + " moved the whole character " + cm.ToString("0") + " cm (its file stores the root node): "
                + "put back to her place, the pose kept (the pose file is not changed)");
        }

        /// <summary>Version 63: the body back over the control point (the pose kept), while the guard of a pose change runs.</summary>
        private void Center()
        {
            if (!_center) return;
            float m = BodyMover.CenterOnControl(_atom, RootReset.ToleranceMetres);
            if (m <= 0f) return;
            _quiet = 0f;   // the guard runs on until nothing moved her for QuietSeconds
            Centers++;
            if (_centerNoted) return;   // one note per pose change
            _centerNoted = true;
            LastCenterNote = _what + ": body " + (m * 100f).ToString("0") + " cm away from the control point, put back over it (pose kept)";
            Log.Info(Capital(_what) + ": the body was " + (m * 100f).ToString("0") + " cm away from the control point: put back "
                + "over it, the pose kept (Center body on control point)");
        }

        /// <summary>Version 63: re-centre now, outside a pose change (unused since v64).
        /// Returns the flat distance moved in metres (0 = off or already centred).</summary>
        public float CenterNow()
        {
            if (!RootReset.Applies(CenterBody, false) || _atom == null) return 0f;
            float m = BodyMover.CenterOnControl(_atom, RootReset.ToleranceMetres);
            if (m > 0f) Centers++;
            return m;
        }

        /// <summary>Every frame (PoseController.Update): keeps her place until VaM has settled the pose.</summary>
        public void Update(float dt)
        {
            if (!Active) return;
            if (_unlockIn >= 0f)   // version 66: controllers locked after the origin move (or after a skipped pose)
            {
                _unlockIn -= dt;
                if (_unlockIn < 0f) { ResumePhysics(); _age = -1f; _snap = null; }
                return;
            }
            Hold();
            if (!Active || _unlockIn >= 0f) return;   // Hold skipped the pose
            _age += dt;
            _quiet += dt;
            if ((_age >= MinSeconds && _quiet >= QuietSeconds) || _age >= MaxSeconds)
            {
                if (UseOrigin && !_originDone)
                {
                    _originDone = true;
                    if (ApplyOrigin()) return;
                }
                _age = -1f;
                _snap = null;
            }
        }

        /// <summary>A deliberate move (Body position, Reset poses): the guard keeps the new place, not the old one.</summary>
        public void Rebase()
        {
            if (!Active || _atom == null || _atom.mainController == null) return;
            _pos = _atom.mainController.transform.position;
            _rot = _atom.mainController.transform.rotation;
        }

        private static string Capital(string s)
        {
            return string.IsNullOrEmpty(s) ? "A pose" : char.ToUpperInvariant(s[0]) + s.Substring(1);
        }
    }

    public static class BodyMover
    {
        /// <summary>The flat facing direction of a rotation (forward without its up/down part).</summary>
        public static Vector3 FacingOf(Quaternion rotation)
        {
            Vector3 f = rotation * Vector3.forward;
            f = new Vector3(f.x, 0f, f.z);
            return f.magnitude < 0.001f ? Vector3.forward : f.normalized;
        }

        /// <summary>The flat facing direction of the atom (main controller forward without its up/down part).</summary>
        public static Vector3 Facing(Atom atom)
        {
            if (atom == null || atom.mainController == null) return Vector3.forward;
            return FacingOf(atom.mainController.transform.rotation);
        }

        /// <summary>The world shift of a move of `forward` / `right` metres along the facing.</summary>
        public static Vector3 ShiftFor(Atom atom, float forward, float right)
        {
            Vector3 f = Facing(atom);
            return f * forward + Vector3.Cross(Vector3.up, f) * right;
        }

        /// <summary>Version 54: where the main controller goes for a Body position of `forward` / `right` metres and `degrees`,
        /// counted from its home placement (absolute, so dragging a slider never adds up rounding errors).</summary>
        public static Vector3 TargetPosition(Vector3 homePos, Quaternion homeRot, float forward, float right, float degrees)
        {
            Quaternion turn = Quaternion.Euler(0f, degrees, 0f);
            Vector3 f = FacingOf(turn * homeRot);
            return homePos + f * forward + Vector3.Cross(Vector3.up, f) * right;
        }

        /// <summary>Version 54: moves the whole person RIGIDLY so its main controller ends at `wantPos` / `wantRot`; every
        /// other controller keeps its place relative to the main controller (the pose is kept). Returns how many were set.</summary>
        public static int Relocate(Atom atom, Vector3 wantPos, Quaternion wantRot)
        {
            if (atom == null || atom.freeControllers == null || atom.mainController == null) return 0;
            FreeControllerV3 main = atom.mainController;
            Vector3 fromPos = main.transform.position;
            Quaternion delta = wantRot * Quaternion.Inverse(main.transform.rotation);
            FreeControllerV3[] all = atom.freeControllers;
            Vector3[] pos = new Vector3[all.Length];
            Quaternion[] rot = new Quaternion[all.Length];
            for (int i = 0; i < all.Length; i++)
            {
                if (all[i] == null) continue;
                pos[i] = all[i].transform.position;
                rot[i] = all[i].transform.rotation;
            }
            main.transform.position = wantPos;   // the main controller first ...
            main.transform.rotation = wantRot;
            int moved = 1;
            for (int i = 0; i < all.Length; i++)
            {
                FreeControllerV3 c = all[i];
                if (c == null || c == main) continue;
                c.transform.position = wantPos + delta * (pos[i] - fromPos);   // ... then each other one to its own absolute target
                c.transform.rotation = delta * rot[i];
                moved++;
            }
            return moved;
        }

        /// <summary>Moves the whole person by `shift` (rigid); returns how many controllers were set.</summary>
        public static int Shift(Atom atom, Vector3 shift)
        {
            if (atom == null || atom.mainController == null) return 0;
            return Relocate(atom, atom.mainController.transform.position + shift, atom.mainController.transform.rotation);
        }

        /// <summary>Turns the whole person by `degrees` about the vertical axis through the main controller (rigid).</summary>
        public static int Turn(Atom atom, float degrees)
        {
            if (atom == null || atom.mainController == null) return 0;
            return Relocate(atom, atom.mainController.transform.position, Quaternion.Euler(0f, degrees, 0f) * atom.mainController.transform.rotation);
        }

        /// <summary>Version 63 (root-position reset on pose load): puts the body back over the control point. The hips'
        /// offset from the main controller is taken in the main controller's frame (RootReset.LocalShift: only the flat part,
        /// the height stays) and every controller except the main one is moved by that shift - all read first, then each set
        /// to its own absolute target, like Relocate - so the pose's controllers keep their offsets to each other and the
        /// main controller (the control point) does not move. Returns the flat distance in metres (0 = nothing moved).</summary>
        public static float CenterOnControl(Atom atom, float tolerance)
        {
            if (atom == null || atom.freeControllers == null || atom.mainController == null) return 0f;
            FreeControllerV3 hip = atom.GetStorableByID(RootReset.BodyControl) as FreeControllerV3;   // E1, E6 (Dollmaster: hipControl)
            if (hip == null) return 0f;
            FreeControllerV3 main = atom.mainController;
            Transform root = main.transform;
            Vector3 local = Quaternion.Inverse(root.rotation) * (hip.transform.position - root.position);
            float sx, sy, sz;
            float moved = RootReset.LocalShift(local.x, local.y, local.z, tolerance, out sx, out sy, out sz);
            if (moved <= 0f) return 0f;
            Vector3 shift = root.rotation * new Vector3(sx, sy, sz);
            FreeControllerV3[] all = atom.freeControllers;
            Vector3[] pos = new Vector3[all.Length];
            for (int i = 0; i < all.Length; i++) if (all[i] != null) pos[i] = all[i].transform.position;
            for (int i = 0; i < all.Length; i++)
            {
                FreeControllerV3 c = all[i];
                if (c == null || c == main) continue;
                c.transform.position = pos[i] + shift;
            }
            return moved;
        }

        /// <summary>Version 54: true when the main controller is more than 1 cm or about half a degree away from the placement.</summary>
        public static bool Moved(Atom atom, Vector3 pos, Quaternion rot)
        {
            if (atom == null || atom.mainController == null) return false;
            Transform t = atom.mainController.transform;
            if ((t.position - pos).magnitude > 0.01f) return true;
            return ((t.rotation * Vector3.forward) - (rot * Vector3.forward)).magnitude > 0.01f
                || ((t.rotation * Vector3.up) - (rot * Vector3.up)).magnitude > 0.01f;
        }
    }
}
