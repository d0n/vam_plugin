// Body: the AI character's body. A plain component owned by AIBodyPlugin, no MVRScript of its own
// and no I/O: commands arrive in-process from the AppLink, events go out through the send callback.
//
//   - speech on the Person's head audio (VaM lip sync), morphs, expressions, gestures, poses,
//     idle head motion and breathing
//   - per-character settings (volume, idle, breathing, ...) saved with the Person atom
using System;
using System.Collections.Generic;
using SimpleJSON;

namespace AIBody
{
    public class Body
    {
        private readonly MVRScript _plugin;
        private readonly Atom _atom;
        private readonly Action<JSONClass> _send;
        private readonly Diag _diag;

        private JSONStorableFloat _volumeJson;
        private JSONStorableBool _idleJson;
        private JSONStorableFloat _idleIntensityJson;
        private JSONStorableBool _breathingJson;
        private JSONStorableFloat _breathRateJson;
        private JSONStorableFloat _breathDepthJson;
        private JSONStorableString _breathMorphJson;
        private JSONStorableBool _bodyControlJson;
        // Idle poses (version 35): the character changes on its own to an available pose now and then.
        private JSONStorableBool _idlePosesJson;
        private JSONStorableFloat _idlePoseMinJson;
        private JSONStorableFloat _idlePoseMaxJson;
        private JSONStorableStringChooser _idlePoseDefaultJson;
        private IdlePoseScheduler _idlePoses;
        private JSONStorableBool _gazeControlJson;
        private JSONStorableStringChooser _gazeDefaultJson;
        private JSONStorableBool _gazeFollowJson;
        private JSONStorableBool _blinkJson;
        // Scene hooks (since version 26): values other plugins / triggers can read and set.
        private JSONStorableBool _aiSpeakingJson;
        private JSONStorableBool _userSpeakingJson;
        private JSONStorableString _sceneEventJson;
        private bool _sceneEventBusy;

        /// <summary>True while the user is talking (set by the plugin from the companion's level reports).</summary>
        public Func<bool> UserSpeaking;

        /// <summary>The test WAV shipped next to the .cslist (written by tools/build_var.py).</summary>
        public const string TestToneFile = "AIBodyTest.wav";

        /// <summary>Folder of AIBody.cslist ("d0n.AIBody.8:/Custom/Scripts/d0n/AIBody"); set by the plugin.</summary>
        public Func<string> PluginFolder;

        /// <summary>Utterances started inside the plugin (test tone) are not reported to the companion.</summary>
        private const string LocalPrefix = "local-";

        private MorphHelper _morphs;
        private SpeechPlayer _speech;
        private ExpressionController _expressions;
        private BreathingController _breathing;
        private IdleController _idle;
        private PoseController _poses;
        private GazeController _gaze;
        private bool _gazeBroken;
        private BlinkController _blink;
        private bool _blinkBroken;
        private List<string> _gazeAtoms = new List<string>();
        private float _gazeAtomsAge = 999f;
        private JSONStorableStringChooser _poseChoiceJson;
        private JSONStorableStringChooser _expressionChoiceJson;
        private JSONStorableStringChooser _gestureChoiceJson;
        private JSONStorableStringChooser _poseCommandChoiceJson;   // "Pose command": the vocabulary, for Delete Pose
        private JSONStorableString _poseCommandTextJson;            // "New pose command": text for Add Pose
        /// <summary>Last manual pose / expression / gesture result, shown in the status box (Live).</summary>
        public string CharacterNote = "";
        private CommandRouter _router;

        private float _lastCommandAge = 999f;

        public Body(MVRScript plugin, Atom atom, Action<JSONClass> send, Diag diag)
        {
            _plugin = plugin;
            _atom = atom;
            _send = send;
            _diag = diag ?? new Diag();
        }

        // Self test (looked up lazily, so these also turn true once VaM finished loading the atom).
        public bool SpeechAvailable { get { return _speech != null && _speech.Available; } }
        public string SpeechError { get { return _speech != null ? _speech.LookupError : "SpeechPlayer missing"; } }
        public bool MorphsAvailable { get { return _morphs != null && _morphs.Available; } }
        public string MorphsError { get { return _morphs != null ? _morphs.LookupError : "MorphHelper missing"; } }

        // In-game checks for the TODO(verify) points (T3, T5): computed at most every 5 s.
        private float _selfTestAge = 999f;
        private JSONClass _selfTest;

        /// <summary>
        /// Self test of the body parts that can only be checked in VaM: pose storage (PosePresets),
        /// pose files (GetFiles on Custom/), breath morph, expression morphs, Timeline. Same values as
        /// lines for the status box and as "selftest" in ready/heartbeat (the companion logs them).
        /// </summary>
        public JSONClass SelfTestJson()
        {
            if (_selfTest != null && _selfTestAge < 5f) return _selfTest;
            _selfTestAge = 0f;
            JSONClass t = new JSONClass();
            try
            {
                string storage = _poses != null ? _poses.CheckPoseStorage() : "PoseController missing";
                t["pose_storage"] = storage ?? "ok";
                t["pose_files"].AsInt = _poses != null ? _poses.PoseFileCount : 0;
                t["poses"].AsInt = _poses != null ? _poses.PoseNames.Count : 0;
                t["breath_morph"] = _breathing != null ? _breathing.MorphName : "";
                t["breath_morph_found"].AsBool = _breathing != null && _morphs != null && _morphs.Find(_breathing.MorphName) != null;
                int found = 0, total = 0;
                JSONArray missing = new JSONArray();
                if (_expressions != null && _morphs != null && _morphs.Available)
                {
                    foreach (string n in _expressions.MorphNames)
                    {
                        total++;
                        if (_morphs.Find(n) != null) found++;
                        else missing.Add(new JSONData(n));
                    }
                }
                t["expression_morphs_found"].AsInt = found;
                t["expression_morphs_total"].AsInt = total;
                t["expression_morphs_missing"] = missing;
                t["timeline_gestures"].AsInt = _poses != null ? _poses.TimelineGestureCount : 0;
                t["timeline"].AsBool = _poses != null && _poses.HasTimeline;
            }
            catch (Exception e)
            {
                t["error"] = Diag.Describe(e);
            }
            _selfTest = t;
            return t;
        }

        /// <summary>Self test lines for the status box (below head audio / morphs).</summary>
        public string SelfTestText()
        {
            JSONClass t = SelfTestJson();
            if (Protocol.Has(t, "error")) return "  Body check: ERROR " + t["error"].Value + "\n";
            string storage = t["pose_storage"].Value;
            string text = "  Pose storage (PosePresets): " + (storage == "ok" ? "yes" : "NO (" + storage + ")") + "\n";
            text += "  Poses: " + t["poses"].AsInt + " (files in Custom/Atom/Person/Pose: " + t["pose_files"].AsInt + ")\n";
            text += "  Breath morph '" + t["breath_morph"].Value + "': " + (t["breath_morph_found"].AsBool ? "found" : "NOT found (tab AI Character > Breath morph)") + "\n";
            int found = t["expression_morphs_found"].AsInt, total = t["expression_morphs_total"].AsInt;
            text += "  Expression morphs: " + (total == 0 ? "-" : found + " of " + total + " found");
            JSONArray missing = t["expression_morphs_missing"] as JSONArray;
            if (missing != null && missing.Count > 0)
            {
                List<string> names = new List<string>();
                for (int i = 0; i < missing.Count && i < 6; i++) names.Add(missing[i].Value);
                text += " – missing: " + string.Join(", ", names.ToArray()) + (missing.Count > 6 ? ", …" : "");
            }
            text += "\n";
            if (t["timeline_gestures"].AsInt > 0)
                text += "  Timeline for " + t["timeline_gestures"].AsInt + " gesture(s): " + (t["timeline"].AsBool ? "yes" : "NO (Timeline plugin missing on this Person)") + "\n";
            return text;
        }

        // ---------------------------------------------------------------- setup

        public void CreateStorables()
        {
            // Off = the AI / companion side cannot move the body: expression / morph / gesture / pose / trigger / look_at /
            // idle / breathing commands are ignored and there are no idle poses (version 35). Speech still works; the plugin's
            // own idle head motion, breathing, gaze and blinking keep their own toggles.
            _bodyControlJson = new JSONStorableBool("Body control", true, (bool v) =>
            {
                if (!v && _expressions != null) _expressions.Reset(0.4f);
            });
            _plugin.RegisterBool(_bodyControlJson);
            _volumeJson = new JSONStorableFloat("Speech volume", 1f, (float v) => { if (_speech != null) _speech.Volume = v; }, 0f, 1f);
            _plugin.RegisterFloat(_volumeJson);
            _idleJson = new JSONStorableBool("Idle head motion", true, (bool v) => { if (_idle != null) _idle.Enabled = v; });
            _plugin.RegisterBool(_idleJson);
            _idleIntensityJson = new JSONStorableFloat("Idle intensity", 0.5f, (float v) => { if (_idle != null) _idle.Intensity = v; }, 0f, 1f);
            _plugin.RegisterFloat(_idleIntensityJson);
            _breathingJson = new JSONStorableBool("Breathing", true, (bool v) => { if (_breathing != null) _breathing.Enabled = v; });
            _plugin.RegisterBool(_breathingJson);
            _breathRateJson = new JSONStorableFloat("Breaths per minute", 14f, (float v) => { if (_breathing != null) _breathing.Rate = v; }, 4f, 40f);
            _plugin.RegisterFloat(_breathRateJson);
            _breathDepthJson = new JSONStorableFloat("Breath depth", 0.35f, (float v) => { if (_breathing != null) _breathing.Depth = v; }, 0f, 1f);
            _plugin.RegisterFloat(_breathDepthJson);
            // TODO(verify): choose a chest morph that exists on the character.
            _breathMorphJson = new JSONStorableString("Breath morph", "Breath1", (string v) => { if (_breathing != null) _breathing.SetMorph(v); _selfTestAge = 999f; });
            _plugin.RegisterString(_breathMorphJson);
            _idlePosesJson = new JSONStorableBool("Idle poses", true, (bool v) => { if (_idlePoses != null) _idlePoses.Enabled = v; });
            _plugin.RegisterBool(_idlePosesJson);
            _idlePoseMinJson = new JSONStorableFloat("Idle pose min wait (s)", IdlePoseScheduler.DefaultMinSeconds,
                (float v) => { if (_idlePoses != null) _idlePoses.MinSeconds = v; }, IdlePoseScheduler.LowestSeconds, IdlePoseScheduler.HighestSeconds);
            _plugin.RegisterFloat(_idlePoseMinJson);
            _idlePoseMaxJson = new JSONStorableFloat("Idle pose max wait (s)", IdlePoseScheduler.DefaultMaxSeconds,
                (float v) => { if (_idlePoses != null) _idlePoses.MaxSeconds = v; }, IdlePoseScheduler.LowestSeconds, IdlePoseScheduler.HighestSeconds);
            _plugin.RegisterFloat(_idlePoseMaxJson);
            _idlePoseDefaultJson = new JSONStorableStringChooser("Idle default pose", new List<string> { IdlePoseScheduler.DefaultIdlePose },
                IdlePoseScheduler.DefaultIdlePose, "Idle default pose", (string v) => { if (_idlePoses != null) _idlePoses.DefaultPose = v; });
            _idlePoseDefaultJson.popupOpenCallback = RefreshCharacterChoices;
            _plugin.RegisterStringChooser(_idlePoseDefaultJson);

            // Manual pose / expression / gesture menu (tab AI Character). Not registered: only the
            // choice in the menu, nothing new is saved with the scene. Lists refill on opening (E25).
            _poseChoiceJson = new JSONStorableStringChooser("Pose", new List<string>(), "", "Pose", (string v) => { });
            _poseChoiceJson.popupOpenCallback = RefreshCharacterChoices;
            _poseCommandChoiceJson = new JSONStorableStringChooser("Pose command", new List<string>(), "", "Pose command", (string v) => { });
            _poseCommandChoiceJson.popupOpenCallback = RefreshCharacterChoices;
            _poseCommandTextJson = new JSONStorableString("New pose command", "", (string v) => { });   // not registered: only typed text
            _expressionChoiceJson = new JSONStorableStringChooser("Expression", new List<string>(), "", "Expression", (string v) => { });
            _expressionChoiceJson.popupOpenCallback = RefreshCharacterChoices;
            _gestureChoiceJson = new JSONStorableStringChooser("Gesture", new List<string>(), "", "Gesture", (string v) => { });
            _gestureChoiceJson.popupOpenCallback = RefreshCharacterChoices;
            // Gaze (tab AI Character > Gaze): where the eyes look. Saved with the scene like the other body settings.
            _gazeControlJson = new JSONStorableBool("Gaze control", true, (bool v) => { if (_gaze != null) _gaze.Enabled = v; });
            _plugin.RegisterBool(_gazeControlJson);
            _gazeDefaultJson = new JSONStorableStringChooser("Default gaze", GazeFixedChoices(), GazeLabelDefault, "Default gaze",
                (string v) => { if (_gaze != null) _gaze.SetDefault(GazeKey(v)); });
            _gazeDefaultJson.popupOpenCallback = RefreshGazeChoices;
            _plugin.RegisterStringChooser(_gazeDefaultJson);
            _gazeFollowJson = new JSONStorableBool("Gaze follows speaker", false, (bool v) => { if (_gaze != null) _gaze.FollowsSpeaker = v; });
            _plugin.RegisterBool(_gazeFollowJson);
            _blinkJson = new JSONStorableBool("Blink control", false, (bool v) => { if (_blink != null) _blink.Enabled = v; });
            _plugin.RegisterBool(_blinkJson);
            CreateSceneHooks();
            _plugin.RegisterAction(new JSONStorableAction("Stop speaking", StopSpeaking));
            _plugin.RegisterAction(new JSONStorableAction("Reset expression", () => { if (_expressions != null) _expressions.Reset(0.4f); }));
            _plugin.RegisterAction(new JSONStorableAction("Reload config files", ReloadConfigFiles));
        }

        public void CreateControllers()
        {
            // Each controller on its own: a failing one disables only its feature. Atom lookups
            // (HeadAudioSource, geometry, headControl) are lazy and retried, see the controllers.
            _diag.Run("Morphs (MorphHelper)", () => _morphs = new MorphHelper(_atom));
            _diag.Run("Speech output (SpeechPlayer)", () =>
            {
                SpeechPlayer speech = new SpeechPlayer(_atom);
                speech.OnStarted = OnSpeechStarted;
                speech.OnEnded = OnSpeechEnded;
                speech.OnError = (id, message) =>
                {
                    if (!IsLocal(id)) _send(Protocol.NewError(id, "audio_failed", message));
                };
                speech.Volume = _volumeJson != null ? _volumeJson.val : 1f;
                _speech = speech;
            });
            if (_morphs != null)
            {
                _diag.Run("Expressions (ExpressionController)", () => _expressions = new ExpressionController(_morphs));
                _diag.Run("Breathing (BreathingController)", () =>
                {
                    BreathingController breathing = new BreathingController(_morphs, _breathMorphJson != null ? _breathMorphJson.val : "Breath1");
                    if (_breathingJson != null) breathing.Enabled = _breathingJson.val;
                    if (_breathRateJson != null) breathing.Rate = _breathRateJson.val;
                    if (_breathDepthJson != null) breathing.Depth = _breathDepthJson.val;
                    _breathing = breathing;
                });
            }
            _diag.Run("Head motion (IdleController)", () =>
            {
                IdleController idle = new IdleController(_atom);
                if (_idleJson != null) idle.Enabled = _idleJson.val;
                if (_idleIntensityJson != null) idle.Intensity = _idleIntensityJson.val;
                _idle = idle;
            });
            _diag.Run("Poses/gestures (PoseController)", () =>
            {
                _poses = new PoseController(_atom, _idle);
                _poses.Vocabulary.SetStarters();   // until config.json poses.commands is read (LoadPoseCommands)
                _poses.OnPoseLoaded = () => { if (_idle != null) _idle.Rebase(); };
            });
            _diag.Run("Idle poses (IdlePoseScheduler)", () =>
            {
                IdlePoseScheduler idlePoses = new IdlePoseScheduler((int)(DateTime.UtcNow.Ticks & 0x7fffffff));
                idlePoses.Enabled = _idlePosesJson == null || _idlePosesJson.val;
                if (_idlePoseMinJson != null) idlePoses.MinSeconds = _idlePoseMinJson.val;
                if (_idlePoseMaxJson != null) idlePoses.MaxSeconds = _idlePoseMaxJson.val;
                if (_idlePoseDefaultJson != null) idlePoses.DefaultPose = _idlePoseDefaultJson.val;
                _idlePoses = idlePoses;
            });
            _diag.Run("Gaze (GazeController)", () =>
            {
                GazeController gaze = new GazeController(_atom);
                if (_gazeControlJson != null) gaze.Enabled = _gazeControlJson.val;
                if (_gazeFollowJson != null) gaze.FollowsSpeaker = _gazeFollowJson.val;
                if (_gazeDefaultJson != null) gaze.SetDefault(GazeKey(_gazeDefaultJson.val));
                _gaze = gaze;
            });
            _diag.Run("Blinking (BlinkController)", () =>
            {
                BlinkController blink = new BlinkController(_atom, _morphs);
                if (_blinkJson != null) blink.Enabled = _blinkJson.val;
                _blink = blink;
                if (_gaze != null) _gaze.OnShift = () => { if (_blink != null) _blink.RequestBlink(); };
            });
            _diag.Run("Scene actions", RegisterSceneActions);
            _diag.Run("Commands (CommandRouter)", () =>
                _router = new CommandRouter(_send, _speech, _expressions, _poses, _idle, _breathing, _gaze,
                    () => BodyControl));
            _diag.Run("Load config files", ReloadConfigFiles);
        }

        /// <summary>Speech controls on the left, body settings on the right (below the mic menu).</summary>
        // ---------------------------------------------------------------- tabs (see AIBodyPlugin)

        private string _testStatus;

        /// <summary>Sound test in the tab "Voice", section "Voice Mode".</summary>
        public void BuildVoiceModeTab(UiPage page)
        {
            page.Button("Play test tone", () => { _testStatus = PlayTestTone(); });
            page.Button("Stop speaking", StopSpeaking);
        }

        public bool BodyControl { get { return _bodyControlJson == null || _bodyControlJson.val; } }

        public void SetBodyControl(bool on)
        {
            if (_bodyControlJson != null) _bodyControlJson.val = on;
        }

        /// <summary>Set when the pose menu may have to appear or vanish; the plugin rebuilds the tab next frame.</summary>
        public bool RebuildTab;

        /// <summary>Body part of the tab "AI Character" (this Person, i.e. this plugin instance).</summary>
        public void BuildCharacterTab(UiPage page)
        {
            RefreshCharacterChoices();
            page.Header("<b>Poses</b> (pose commands: a pose is applied only when your WHOLE input equals a command)");
            // Pose commands (version 32): the vocabulary that is the only way the AI side applies a pose.
            // No empty menu (version 16): the menus and buttons appear only when there is something to choose.
            if (_poses != null && _poses.Vocabulary.Count > 0)
            {
                page.Popup(_poseCommandChoiceJson);
                page.Button("Delete Pose", DeleteChosenPoseCommand);
            }
            page.Button("Restore starter poses", RestoreStarterPoses);
            if (_poses != null && _poses.PoseNames.Count > 0)
            {
                page.Header("Add Pose: choose the pose below, type the command text in the field, press Add Pose");
                page.ScrollablePopup(_poseChoiceJson);
                page.Button("Apply pose", ApplyChosenPose);
                page.Header("New pose command (the text you say or type)");
                if (!page.TextInput(_poseCommandTextJson))
                    _diag.Warn("Field 'New pose command' is read-only (InputField failed).");
                page.Button("Add Pose", AddPoseCommand);
            }
            page.Button("Reload poses", () => { ReloadGestures(); RefreshCharacterChoices(); RebuildTab = true; });
            page.Header("<b>Idle poses</b> (when nothing happens for a while, the character changes pose by itself)");
            page.Toggle(_idlePosesJson);
            page.ScrollablePopup(_idlePoseDefaultJson);
            page.Slider(_idlePoseMinJson);
            page.Slider(_idlePoseMaxJson);
            page.Header("<b>Expression and gesture</b>");
            page.Popup(_expressionChoiceJson);
            page.Button("Show expression", ShowChosenExpression);
            page.Button("Reset expression", () => { if (_expressions != null) _expressions.Reset(0.4f); });
            page.Button("Reload expressions (expressions.json)", ReloadExpressions);
            page.Popup(_gestureChoiceJson);
            page.Button("Play gesture", PlayChosenGesture);
            page.Header("<b>Gaze and blinking</b> (the eyes)");
            page.Toggle(_gazeControlJson);
            page.ScrollablePopup(_gazeDefaultJson);
            page.Toggle(_gazeFollowJson);
            page.Toggle(_blinkJson);
            page.Header("<b>Body</b> (this Person only)");
            page.Toggle(_bodyControlJson);
            page.Slider(_volumeJson);
            page.Toggle(_idleJson);
            page.Slider(_idleIntensityJson);
            page.Toggle(_breathingJson);
            page.Slider(_breathRateJson);
            page.Slider(_breathDepthJson);
            page.Header("Breath morph: name of the chest morph (field below)");
            if (!page.TextInput(_breathMorphJson))
                _diag.Warn("Field 'Breath morph' is read-only (InputField failed).");
        }

        /// <summary>Info for the tab "AI Character" in the big field on the left.</summary>
        public string CharacterInfoText()
        {
            string text = "Poses: " + (_poses != null ? _poses.PoseNames.Count + " in the menu (" + _poses.PoseScanNote + ")" : "PoseController missing") + "\n";
            text += PoseCommandsInfo();
            text += IdlePosesInfo();
            text += BodyControlHelp + " Breath morph: a name from the character's Morphs tab; without it the chest still rises with each breath.\n";
            text += GazeInfoText();
            return text;
        }

        /// <summary>What the toggle "Body control" does (version 35, the same text as in docs/SPEC.md).</summary>
        public const string BodyControlHelp = "Body control off = the AI and the companion app cannot move the body: no poses (also no "
            + "spoken pose commands), gestures, expressions, morphs, triggers, look_at, idle / breathing commands and no idle poses; "
            + "the character only speaks. Your own menu buttons here (Apply pose, Show expression, Play gesture) still work, and so do "
            + "the plugin's own life signs, each with its own toggle: Idle head motion (with the chest weight shift), Breathing, "
            + "Gaze control, Blink control.";

        private string IdlePosesInfo()
        {
            if (_idlePoses == null) return "Idle poses: not available (see the log)\n";
            List<string> names = _poses != null ? _poses.PoseNames : new List<string>();
            string home = IdlePoseScheduler.ResolveName(_idlePoses.DefaultPose, names);
            int count = _poses != null ? _idlePoses.Candidates(_poses.Vocabulary, names, home).Count : 0;
            return "Idle poses: " + (_idlePoses.Enabled ? _idlePoses.Status : "off") + ". After " + _idlePoses.MinSeconds.ToString("0")
                + "-" + _idlePoses.MaxSeconds.ToString("0") + " s without speech or a pose command the character takes one of the "
                + count + " available pose command poses, and next time goes back to the default idle pose ("
                + (home ?? "'" + _idlePoses.DefaultPose + "' not found, so it does not go back") + "). After your own pose command it waits "
                + IdlePoseScheduler.CooldownSeconds.ToString("0") + " s first. Idle head motion and breathing keep running in every pose.\n";
        }

        // ---------------------------------------------------------------- scene hooks (since version 26)

        /// <summary>
        /// Values for VaM triggers, Timeline and other plugins. "AI speaking" / "User speaking" can be read
        /// (GetBoolJSONParam, E13); "Scene event" is a text a trigger can set (receiver target: Set String,
        /// E13): it is sent to the companion app as event scene_event and cleared again. None of them is saved
        /// with the scene (isStorable / isRestorable false, E12 L66).
        /// </summary>
        private void CreateSceneHooks()
        {
            _aiSpeakingJson = new JSONStorableBool("AI speaking", false, (bool v) => { });
            _aiSpeakingJson.isStorable = false;
            _aiSpeakingJson.isRestorable = false;
            _plugin.RegisterBool(_aiSpeakingJson);
            _userSpeakingJson = new JSONStorableBool("User speaking", false, (bool v) => { });
            _userSpeakingJson.isStorable = false;
            _userSpeakingJson.isRestorable = false;
            _plugin.RegisterBool(_userSpeakingJson);
            _sceneEventJson = new JSONStorableString("Scene event", "", OnSceneEventSet);
            _sceneEventJson.isStorable = false;
            _sceneEventJson.isRestorable = false;
            _plugin.RegisterString(_sceneEventJson);
            _plugin.RegisterAction(new JSONStorableAction("Look at client", () => SceneLook(GazeController.KeyClient)));
            _plugin.RegisterAction(new JSONStorableAction("Look at camera", () => SceneLook(GazeController.KeyCamera)));
            _plugin.RegisterAction(new JSONStorableAction("Look straight ahead", () => SceneLook(GazeController.KeyForward)));
            _plugin.RegisterAction(new JSONStorableAction("Look away", () => SceneLook(GazeController.KeyAway)));
            _plugin.RegisterAction(new JSONStorableAction("Gaze back to default", () => SceneLook(GazeController.KeyOff)));
            _plugin.RegisterAction(new JSONStorableAction("Blink now", () => { if (_blink != null) _blink.RequestBlink(); }));
        }

        private void SceneLook(string target)
        {
            if (_gaze == null || _gazeBroken) return;
            string error = _gaze.LookAt(target, "", 0f);
            CharacterNote = error == null ? "Gaze (scene action): " + target : "<color=red>Gaze (scene action): " + error + "</color>";
        }

        /// <summary>One action per expression and gesture known at start ("Expression: happy", "Gesture: nod"), at most 30 each.</summary>
        private void RegisterSceneActions()
        {
            int count = 0;
            if (_expressions != null)
            {
                foreach (string name in _expressions.PresetNames)
                {
                    if (count++ >= 30) break;
                    string expression = name;
                    _plugin.RegisterAction(new JSONStorableAction("Expression: " + expression, () =>
                    {
                        if (BodyControl && _expressions != null) _expressions.SetExpression(expression, 1f, 0.4f, -1f);
                    }));
                }
            }
            List<string> gestures = new List<string>();
            if (_poses != null) foreach (string n in _poses.GestureNames) gestures.Add(n);
            foreach (string n in new[] { "nod", "shake", "tilt" }) if (!gestures.Contains(n)) gestures.Add(n);
            for (int i = 0; i < gestures.Count && i < 30; i++)
            {
                string gesture = gestures[i];
                _plugin.RegisterAction(new JSONStorableAction("Gesture: " + gesture, () =>
                {
                    if (BodyControl && _poses != null) _poses.PlayGesture(gesture, 0f, 0f);
                }));
            }
        }

        private void OnSceneEventSet(string v)
        {
            if (_sceneEventBusy || string.IsNullOrEmpty(v)) return;
            string text = v.Trim();
            if (text.Length == 0) return;
            _sceneEventBusy = true;
            try
            {
                JSONClass evt = Protocol.NewEvent(Protocol.EvtSceneEvent);
                evt["text"] = text;
                _send(evt);
                CharacterNote = "Scene event sent: " + text;
            }
            finally
            {
                _sceneEventJson.val = "";
                _sceneEventBusy = false;
            }
        }

        // ---------------------------------------------------------------- gaze

        private const string GazeLabelDefault = "VaM default";
        private const string GazeLabelClient = "Client Character";
        private const string GazeLabelCamera = "Camera / player";
        private const string GazeLabelForward = "Straight ahead";
        private const string GazeLabelNatural = "Natural (looks around)";
        private const string GazeLabelAtom = "Atom: ";

        private static List<string> GazeFixedChoices()
        {
            return new List<string> { GazeLabelDefault, GazeLabelNatural, GazeLabelClient, GazeLabelCamera, GazeLabelForward };
        }

        /// <summary>Menu text -> config key ("default", "client", "camera", "forward", "atom:&lt;uid&gt;").</summary>
        public static string GazeKey(string label)
        {
            if (label == GazeLabelNatural) return GazeController.KeyNatural;
            if (label == GazeLabelClient) return GazeController.KeyClient;
            if (label == GazeLabelCamera) return GazeController.KeyCamera;
            if (label == GazeLabelForward) return GazeController.KeyForward;
            if (label != null && label.StartsWith(GazeLabelAtom)) return GazeController.AtomPrefix + label.Substring(GazeLabelAtom.Length);
            return GazeController.KeyDefault;
        }

        public static string GazeLabel(string key)
        {
            if (key == GazeController.KeyNatural) return GazeLabelNatural;
            if (key == GazeController.KeyClient) return GazeLabelClient;
            if (key == GazeController.KeyCamera) return GazeLabelCamera;
            if (key == GazeController.KeyForward) return GazeLabelForward;
            if (key != null && key.StartsWith(GazeController.AtomPrefix)) return GazeLabelAtom + key.Substring(GazeController.AtomPrefix.Length);
            return GazeLabelDefault;
        }

        /// <summary>The "Default gaze" menu: the fixed targets plus the atoms in the scene (refilled when it opens).</summary>
        public void RefreshGazeChoices()
        {
            if (_gazeDefaultJson == null) return;
            List<string> choices = GazeFixedChoices();
            if (_gaze != null && !_gazeBroken)
            {
                List<string> atoms = _gaze.ListAtoms();
                for (int i = 0; i < atoms.Count; i++) choices.Add(GazeLabelAtom + atoms[i]);
            }
            if (!choices.Contains(_gazeDefaultJson.val)) choices.Add(_gazeDefaultJson.val);
            _gazeDefaultJson.choices = choices;   // E9, E25
        }

        /// <summary>Gaze help and live state for the big info field (tab AI Character).</summary>
        public string GazeInfoText()
        {
            string text = "Gaze: the AI can look at the client, at the camera (you in VR or on the screen), straight ahead, away, or at an atom by name. "
                + "Default gaze is where the eyes look when the AI gave no order; 'VaM default' leaves the eyes alone. "
                + "Gaze follows speaker: look at the client while someone is talking (needs the level meter of tab Client Character). "
                + "'Natural (looks around)' keeps the eyes on the client with small eye movements, looks away now and then and looks up while the AI thinks. "
                + "Gaze control off: AIBody never moves the eyes. If the Glance plugin or Life's Gaze is on this Person, AIBody stays out of the eyes. "
                + "Blink control: AIBody switches VaM's automatic blinking off and blinks by itself (irregular, more while speaking, at glances); off = VaM blinks as before. "
                + "Life's Eyes plugin or Glance on this Person: AIBody leaves the eyelids alone.\n";
            string blink = _blink == null || _blinkBroken ? "not available (see the log)" : _blink.Status;
            if (_gaze == null || _gazeBroken) return text + "Gaze now: not available (see the log)\nBlinking now: " + blink + "\n";
            return text + "Gaze now: " + _gaze.Status + "\nBlinking now: " + blink + "\n";
        }

        /// <summary>Fills the pose / expression / gesture menus from what this body really has.</summary>
        public void RefreshCharacterChoices()
        {
            if (_poseChoiceJson == null) return;
            List<string> poses = _poses != null ? _poses.PoseNames : new List<string>();
            SetMenu(_poseChoiceJson, poses);
            List<string> commands = new List<string>();
            if (_poses != null) for (int i = 0; i < _poses.Vocabulary.Count; i++) commands.Add(_poses.Vocabulary.Get(i).Command);
            SetMenu(_poseCommandChoiceJson, commands);
            if (_idlePoseDefaultJson != null)
            {
                List<string> homes = new List<string>(poses);
                if (!homes.Contains(_idlePoseDefaultJson.val)) homes.Add(_idlePoseDefaultJson.val);   // keep the saved choice
                _idlePoseDefaultJson.choices = homes;   // E9, E24, E25
            }
            List<string> expressions = new List<string>();
            if (_expressions != null) foreach (string n in _expressions.PresetNames) expressions.Add(n);
            SetMenu(_expressionChoiceJson, expressions);
            List<string> gestures = new List<string>();
            if (_poses != null) foreach (string n in _poses.GestureNames) if (!poses.Contains(n)) gestures.Add(n);
            foreach (string n in new[] { "nod", "shake", "tilt" }) if (!gestures.Contains(n)) gestures.Add(n);
            SetMenu(_gestureChoiceJson, gestures);
        }

        private static void SetMenu(JSONStorableStringChooser chooser, List<string> names)
        {
            chooser.choices = names;   // E9, E24, E25
            if (names.Count > 0 && !names.Contains(chooser.val)) chooser.val = names[0];
        }

        // ---------------------------------------------------------------- pose commands (version 32)

        private string PoseCommandsInfo()
        {
            if (_poses == null) return "";
            PoseVocabulary v = _poses.Vocabulary;
            List<string> names = _poses.PoseNames;
            int ready = 0;
            string lines = "";
            for (int i = 0; i < v.Count; i++)
            {
                bool ok = PoseVocabulary.Resolve(v.Get(i), names) != null;
                if (ok) ready++;
                lines += "  " + v.Get(i).Command + (ok ? "" : "  - UNAVAILABLE: no pose '" + v.Get(i).Pose + "'") + "\n";
            }
            return "Pose commands: " + v.Count + " (" + ready + " available). Say or type EXACTLY one of them; a command without a pose is never applied.\n" + lines;
        }

        private void AddPoseCommand()
        {
            if (_poses == null) { CharacterNote = "Add Pose: PoseController missing"; return; }
            string error = _poses.Vocabulary.Add(_poseCommandTextJson.val, _poseChoiceJson.val);
            if (error != null) { CharacterNote = "<color=red>Add Pose: " + error + "</color>"; return; }
            CharacterNote = "Pose command added: '" + PoseVocabulary.Collapse(_poseCommandTextJson.val) + "' -> " + _poseChoiceJson.val;
            _poseCommandTextJson.val = "";
            RefreshCharacterChoices();
            RebuildTab = true;
        }

        private void DeleteChosenPoseCommand()
        {
            if (_poses == null) { CharacterNote = "Delete Pose: PoseController missing"; return; }
            string command = _poseCommandChoiceJson.val;
            CharacterNote = _poses.Vocabulary.Remove(command) ? "Pose command deleted: '" + command + "'" : "<color=red>Delete Pose: no command chosen</color>";
            RefreshCharacterChoices();
            RebuildTab = true;
        }

        private void RestoreStarterPoses()
        {
            if (_poses == null) { CharacterNote = "Restore starter poses: PoseController missing"; return; }
            int added = _poses.Vocabulary.RestoreStarters();
            CharacterNote = added == 0 ? "All starter pose commands are already there" : added + " starter pose command(s) restored";
            RefreshCharacterChoices();
            RebuildTab = true;
        }

        /// <summary>Reads config.json poses.commands. A missing key, an empty list or a list without one usable entry =
        /// the ten starter commands (version 35, Leon: they are in the configuration from the start); the next write of
        /// config.json (once a second, when changed) then stores them.</summary>
        public void LoadPoseCommands(JSONClass root)
        {
            if (_poses == null || root == null) return;
            JSONClass poses = root["poses"] as JSONClass;
            JSONArray list = poses != null ? poses["commands"] as JSONArray : null;
            PoseVocabulary v = _poses.Vocabulary;
            v.Clear();
            if (list != null)
            {
                for (int i = 0; i < list.Count; i++)
                {
                    JSONClass entry = list[i] as JSONClass;
                    string error = entry == null ? "not an object" : v.Add(entry["command"].Value, entry["pose"].Value);
                    if (error != null) Log.Warn("config.json poses.commands[" + i + "] ignored: " + error);
                }
            }
            if (v.Count == 0)
            {
                v.SetStarters();
                Log.Info("config.json poses.commands missing or empty: the " + v.Count + " starter pose commands are used and saved");
            }
            RefreshCharacterChoices();
            RebuildTab = true;
        }

        private void ApplyChosenPose()
        {
            if (_poses == null) { CharacterNote = "Pose: PoseController missing"; return; }
            string name = _poseChoiceJson.val;
            string error = _poses.ApplyPose(name);
            if (error == null && _idlePoses != null) _idlePoses.NoteUserPose();
            CharacterNote = error == null ? "Pose applied: " + name : "<color=red>Pose '" + name + "': " + error + "</color>";
            Log.Debug(CharacterNote);
        }

        private void ShowChosenExpression()
        {
            if (_expressions == null) { CharacterNote = "Expression: no morphs on this character"; return; }
            string name = _expressionChoiceJson.val;
            CharacterNote = _expressions.SetExpression(name, 1f, 0.4f, -1f)
                ? "Expression: " + name : "<color=red>Unknown expression '" + name + "'</color>";
        }

        private void PlayChosenGesture()
        {
            if (_poses == null) { CharacterNote = "Gesture: PoseController missing"; return; }
            string name = _gestureChoiceJson.val;
            string error = _poses.PlayGesture(name, 0f, 0f);
            CharacterNote = error == null ? "Gesture: " + name : "<color=red>Gesture '" + name + "': " + error + "</color>";
        }

        // ---------------------------------------------------------------- config.json "body"

        public void WriteSettings(JSONClass root)
        {
            if (_volumeJson == null) return;
            JSONClass body = new JSONClass();
            body["speech_volume"].AsFloat = _volumeJson.val;
            body["body_control"].AsBool = BodyControl;
            body["idle_motion"].AsBool = _idleJson.val;
            body["idle_intensity"].AsFloat = _idleIntensityJson.val;
            body["breathing"].AsBool = _breathingJson.val;
            body["breaths_per_minute"].AsFloat = _breathRateJson.val;
            body["breath_depth"].AsFloat = _breathDepthJson.val;
            body["breath_morph"] = _breathMorphJson.val;
            body["gaze_control"].AsBool = _gazeControlJson.val;
            body["gaze_default"] = GazeKey(_gazeDefaultJson.val);
            body["gaze_follows_speaker"].AsBool = _gazeFollowJson.val;
            body["blink_control"].AsBool = _blinkJson.val;
            body["idle_poses"].AsBool = _idlePosesJson.val;
            body["idle_pose_min_s"].AsFloat = _idlePoseMinJson.val;
            body["idle_pose_max_s"].AsFloat = _idlePoseMaxJson.val;
            body["idle_pose_default"] = _idlePoseDefaultJson.val;
            root["body"] = body;
            JSONClass poses = new JSONClass();
            JSONArray commands = new JSONArray();
            if (_poses != null)
            {
                for (int i = 0; i < _poses.Vocabulary.Count; i++)
                {
                    JSONClass entry = new JSONClass();
                    entry["command"] = _poses.Vocabulary.Get(i).Command;
                    entry["pose"] = _poses.Vocabulary.Get(i).Pose;
                    commands.Add(entry);
                }
            }
            poses["commands"] = commands;
            root["poses"] = poses;
        }

        public void ApplySettings(JSONClass root)
        {
            JSONClass body = root["body"] as JSONClass;
            if (body == null || _volumeJson == null) return;
            _volumeJson.val = Protocol.GetFloat(body, "speech_volume", _volumeJson.val);
            if (_bodyControlJson != null) _bodyControlJson.val = Protocol.GetBool(body, "body_control", _bodyControlJson.val);
            _idleJson.val = Protocol.GetBool(body, "idle_motion", _idleJson.val);
            _idleIntensityJson.val = Protocol.GetFloat(body, "idle_intensity", _idleIntensityJson.val);
            _breathingJson.val = Protocol.GetBool(body, "breathing", _breathingJson.val);
            _breathRateJson.val = Protocol.GetFloat(body, "breaths_per_minute", _breathRateJson.val);
            _breathDepthJson.val = Protocol.GetFloat(body, "breath_depth", _breathDepthJson.val);
            _breathMorphJson.val = Protocol.GetString(body, "breath_morph", _breathMorphJson.val);
            _gazeControlJson.val = Protocol.GetBool(body, "gaze_control", _gazeControlJson.val);
            _gazeDefaultJson.val = GazeLabel(Protocol.GetString(body, "gaze_default", GazeKey(_gazeDefaultJson.val)));
            _gazeFollowJson.val = Protocol.GetBool(body, "gaze_follows_speaker", _gazeFollowJson.val);
            _blinkJson.val = Protocol.GetBool(body, "blink_control", _blinkJson.val);
            _idlePosesJson.val = Protocol.GetBool(body, "idle_poses", _idlePosesJson.val);
            _idlePoseMinJson.val = Protocol.GetFloat(body, "idle_pose_min_s", _idlePoseMinJson.val);
            _idlePoseMaxJson.val = Protocol.GetFloat(body, "idle_pose_max_s", _idlePoseMaxJson.val);
            string home = Protocol.GetString(body, "idle_pose_default", _idlePoseDefaultJson.val);
            if (home.Length > 0) SetChooserValue(_idlePoseDefaultJson, home);
        }

        private static void SetChooserValue(JSONStorableStringChooser chooser, string value)
        {
            if (!chooser.choices.Contains(value))
            {
                List<string> choices = new List<string>(chooser.choices);
                choices.Add(value);
                chooser.choices = choices;
            }
            chooser.val = value;
        }

        /// <summary>Set from config.json (connection.paths) by the plugin.</summary>
        public string ExpressionsPath = AppLink.DataRoot + "/expressions.json";
        public string GesturesPath = AppLink.DataRoot + "/gestures.json";

        public void ReloadConfigFiles()
        {
            ReloadExpressions();
            ReloadGestures();
        }

        public void ReloadExpressions()
        {
            if (_expressions != null) _expressions.LoadPresetFile(ExpressionsPath);
            _selfTestAge = 999f;   // self test checks the new morph names
        }

        public void ReloadGestures()
        {
            if (_poses == null) return;
            _poses.LoadGestureFile(GesturesPath);
            _poses.ScanPoseFiles();
            Log.Info(_poses.PoseScanNote + "; " + _poses.PoseNames.Count + " poses in the menu / available to the AI");
            _selfTestAge = 999f;
        }

        /// <summary>
        /// Plays the WAV shipped in the package on the head audio: checks the sound path without the
        /// companion app (and without Saves/PluginData). Returns a status line.
        /// </summary>
        public string PlayTestTone()
        {
            if (_speech == null) return "Test tone: speech output missing";
            string folder = null;
            try { folder = PluginFolder != null ? PluginFolder() : null; }
            catch (Exception e) { return "Test tone: plugin folder not found (" + Diag.Describe(e) + ")"; }
            if (string.IsNullOrEmpty(folder)) return "Test tone: plugin folder not found";
            string path = folder + "/" + TestToneFile;
            string error = _speech.Enqueue(LocalPrefix + "test-" + DateTime.UtcNow.Ticks, path, true);
            return error == null ? "Test tone: " + path : "Test tone: " + error;
        }

        private static bool IsLocal(string id)
        {
            return id != null && id.StartsWith(LocalPrefix);
        }

        public void StopSpeaking()
        {
            if (_speech != null) _speech.StopAll("stopped");
        }

        // ---------------------------------------------------------------- commands and events

        /// <summary>Handles one body command from the companion app (called by the AppLink).</summary>
        public void Handle(JSONClass msg)
        {
            if (_router == null) return;
            _lastCommandAge = 0f;
            _router.Handle(msg);
            // A pose command of the user (the companion sends one only for an exact command): idle poses wait first.
            if (_idlePoses != null && Protocol.GetString(msg, "type", "") == Protocol.CmdPose) _idlePoses.NoteUserPose();
        }

        /// <summary>Adds the body's state to the link's ready / heartbeat / pong.</summary>
        public void AddStatus(JSONClass s)
        {
            s["atom"] = _atom != null ? _atom.uid : "";
            s["speaking"].AsBool = _speech != null && _speech.IsSpeaking;
            s["speech_queue"].AsInt = _speech != null ? _speech.QueueLength : 0;
            s["expression"] = _expressions != null ? _expressions.Current : "";
            JSONArray expressions = new JSONArray();
            if (_expressions != null) foreach (string n in _expressions.PresetNames) expressions.Add(new JSONData(n));
            s["expressions"] = expressions;
            JSONArray gestures = new JSONArray();
            if (_poses != null) foreach (string n in _poses.GestureNames) gestures.Add(new JSONData(n));
            gestures.Add(new JSONData("nod"));
            gestures.Add(new JSONData("shake"));
            gestures.Add(new JSONData("tilt"));
            s["gestures"] = gestures;
            JSONArray poses = new JSONArray();
            if (_poses != null) foreach (string n in _poses.PoseNames) poses.Add(new JSONData(n));
            s["poses"] = poses;
            JSONArray poseCommands = new JSONArray();   // the vocabulary: the companion matches the user's whole input against it
            if (_poses != null)
            {
                List<string> poseNames = _poses.PoseNames;
                for (int i = 0; i < _poses.Vocabulary.Count; i++)
                {
                    JSONClass entry = new JSONClass();
                    entry["command"] = _poses.Vocabulary.Get(i).Command;
                    entry["pose"] = _poses.Vocabulary.Get(i).Pose;
                    entry["available"].AsBool = PoseVocabulary.Resolve(_poses.Vocabulary.Get(i), poseNames) != null;
                    poseCommands.Add(entry);
                }
            }
            s["pose_commands"] = poseCommands;
            s["body_control"].AsBool = BodyControl;   // off: the companion offers the AI no body tools
            s["gaze_control"].AsBool = _gaze != null && !_gazeBroken && _gaze.AiMayDirect;   // off: no look_at tool
            JSONArray gazeAtoms = new JSONArray();
            for (int i = 0; i < _gazeAtoms.Count; i++) gazeAtoms.Add(new JSONData(_gazeAtoms[i]));
            s["gaze_atoms"] = gazeAtoms;   // atoms the AI may look at by name
            s["selftest"] = SelfTestJson();   // in-game checks, logged by the companion when they change
        }

        private void OnSpeechStarted(string id, float duration)
        {
            if (IsLocal(id)) return;
            if (_blink != null) _blink.RequestBlink();
            JSONClass evt = Protocol.NewEvent(Protocol.EvtSpeechStarted);
            evt["utterance_id"] = id ?? "";
            evt["duration"].AsFloat = duration;
            _send(evt);
        }

        private void OnSpeechEnded(string id, string reason)
        {
            if (IsLocal(id)) return;
            JSONClass evt = Protocol.NewEvent(Protocol.EvtSpeechEnded);
            evt["utterance_id"] = id ?? "";
            evt["reason"] = reason;
            evt["queue_length"].AsInt = _speech != null ? _speech.QueueLength : 0;
            _send(evt);
        }

        // ---------------------------------------------------------------- frame loop

        public void Update(float dt)
        {
            _lastCommandAge += dt;
            _selfTestAge += dt;
            if (_speech != null) _speech.Update(dt);
            bool speaking = _speech != null && _speech.IsSpeaking;
            if (_expressions != null) _expressions.Update(dt);
            if (_breathing != null) _breathing.Update(dt, speaking);
            UpdateGaze(dt, speaking);
            UpdateBlink(dt, speaking);
            UpdateSceneState(speaking);
            UpdateIdlePoses(dt, speaking);
            if (_idle == null) return;
            string finishedGesture = _idle.Update(dt, speaking,
                _breathing != null ? _breathing.Cycle : 0f, _breathing != null ? _breathing.CurrentDepth : 0f);
            if (finishedGesture != null)
            {
                JSONClass done = Protocol.NewEvent(Protocol.EvtGestureDone);
                done["name"] = finishedGesture;
                _send(done);
            }
        }

        private bool _idlePosesBroken;

        private void UpdateIdlePoses(float dt, bool speaking)
        {
            if (_idlePoses == null || _poses == null || _idlePosesBroken) return;
            try
            {
                bool busy = speaking || (UserSpeaking != null && UserSpeaking()) || (_speech != null && _speech.QueueLength > 0);
                string pose = _idlePoses.Update(dt, busy, BodyControl, _poses.Vocabulary, _poses.PoseNames);
                if (pose == null) return;
                string error = _poses.ApplyPose(pose);
                if (error == null) Log.Debug("Idle pose: " + pose);
                else Log.Warn("Idle pose '" + pose + "' failed: " + error);
            }
            catch (Exception e)
            {
                _idlePosesBroken = true;   // only the idle poses stop
                _diag.Fail("Idle poses (stopped)", e);
            }
        }

        private void UpdateBlink(float dt, bool speaking)
        {
            if (_blink == null || _blinkBroken) return;
            try { _blink.Update(dt, speaking); }
            catch (Exception e)
            {
                _blinkBroken = true;   // only the blinking stops
                try { _blink.Release(); } catch (Exception) { }
                _diag.Fail("Blink.Update (blinking stopped)", e);
            }
        }

        private void UpdateSceneState(bool speaking)
        {
            if (_aiSpeakingJson != null && _aiSpeakingJson.val != speaking) _aiSpeakingJson.val = speaking;
            bool user = UserSpeaking != null && UserSpeaking();
            if (_userSpeakingJson != null && _userSpeakingJson.val != user) _userSpeakingJson.val = user;
        }

        private void UpdateGaze(float dt, bool speaking)
        {
            if (_gaze == null || _gazeBroken) return;
            try
            {
                _gaze.Update(dt, speaking, UserSpeaking != null && UserSpeaking());
                _gazeAtomsAge += dt;
                if (_gazeAtomsAge > 3f)
                {
                    _gazeAtomsAge = 0f;
                    _gazeAtoms = _gaze.ListAtoms();
                }
            }
            catch (Exception e)
            {
                _gazeBroken = true;   // only the gaze stops; the rest of the body keeps working
                try { _gaze.Release(); } catch (Exception) { }
                _diag.Fail("Gaze.Update (gaze stopped)", e);
            }
        }

        public string StatusText()
        {
            string text = "Last command: " + (_lastCommandAge < 999f ? _lastCommandAge.ToString("0") + "s ago" : "none yet") + "\n";
            if (_speech != null)
            {
                text += "Speaking: " + (_speech.IsSpeaking ? "yes" : "no") + ", queued: " + _speech.QueueLength
                    + (_volumeJson != null && _volumeJson.val < 0.01f ? " – Speech volume is 0!" : "") + "\n";
                text += "Audio: " + (_speech.Status ?? "nothing played yet") + "\n";
                if (_speech.LastError != null && _speech.LastError != _speech.Status && _speech.LastErrorAge < 300f)
                    text += "<color=red>" + _speech.LastError + "</color> (" + _speech.LastErrorAge.ToString("0") + " s ago)\n";
            }
            if (!BodyControl) text += "Body control: off (speech only; no poses, gestures, expressions or idle poses from the AI side)\n";
            if (_testStatus != null) text += _testStatus + "\n";
            if (CharacterNote.Length > 0) text += CharacterNote + "\n";
            if (_expressions != null) text += "Expression: " + _expressions.Current + "\n";
            if (_breathing != null && _morphs != null)
                text += "Breath morph: " + (_breathing.HasMorph ? _breathing.MorphName : "'" + _breathing.MorphName + "' not found") + "\n";
            return text;
        }

        /// <summary>Stops speech and returns every touched morph / bone to its original state.</summary>
        public void Restore()
        {
            if (_speech != null) _speech.StopAll("stopped");
            if (_expressions != null) _expressions.RestoreNow();
            if (_breathing != null) _breathing.RestoreNow();
            if (_idle != null) _idle.RestoreNow();
            if (_gaze != null) _gaze.RestoreNow();
            if (_blink != null) _blink.RestoreNow();
        }
    }
}
