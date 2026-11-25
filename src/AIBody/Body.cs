// Body: the AI character's body. A plain component owned by AIBodyPlugin, no MVRScript of its own
// and no I/O: commands arrive in-process from the AppLink, events go out through the send callback.
//
//   - speech on the AI person's head audio (VaM lip sync); since version 42 the AI person can be another atom than
//     the plugin's host (AIBodyPlugin.FindAiCharacter: the Person named 'AI'), morphs, expressions, gestures, poses,
//     idle head motion and breathing
//   - per-character settings (volume, idle, breathing, ...) saved with the Person atom
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;
using MVR.FileManagementSecure;

namespace AIBody
{
    public class Body
    {
        private readonly MVRScript _plugin;
        private Atom _atom;   // the AI person; SetAtom before CreateControllers (version 42)
        private readonly Action<JSONClass> _send;
        private readonly Diag _diag;

        private JSONStorableFloat _volumeJson;         // "Speech volume (%)" 0..1000 (Don 22.11.2026 04:15/04:16); the factor is _volumeJson.val / 100
        private JSONStorableFloat _legacyVolumeJson;   // "Speech volume" factor (0..3 up to v45, now 0..10): no slider, kept for saved scenes
        private bool _syncingVolume;
        private JSONStorableFloat _distanceJson;   // version 48: "Full volume distance (m)", applied by SpeechPlayer.UpdateDistance from Update
        private JSONStorableBool _idleJson;
        private JSONStorableFloat _idleIntensityJson;
        private JSONStorableBool _breathingJson;
        private JSONStorableFloat _breathRateJson;
        private JSONStorableFloat _breathDepthJson;
        private JSONStorableString _breathMorphJson;
        private JSONStorableBool _bodyControlJson;
        // Idle poses (version 35): the character changes on its own to an available pose now and then.
        private JSONStorableBool _idlePosesJson;
        private JSONStorableBool _idleAllFilesJson;   // version 54
        private bool _poolDirty = true;               // version 54: the info field recounts the pool only after a change
        private int _poolCount, _poolVocabCount = -1, _poolNamesCount = -1;
        private JSONStorableFloat _idlePoseIntervalJson;   // version 59: one slider
        private JSONStorableFloat _idlePoseMinJson;        // v51-v58, kept only to read old scenes (not shown, not saved)
        private JSONStorableFloat _idlePoseMaxJson;
        private JSONStorableStringChooser _idlePoseDefaultJson;
        private IdlePoseScheduler _idlePoses;
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
        // Idle movement (version 60, Don): MacGruber's IdlePoser on the AI character, states built from her current pose.
        private JSONStorableBool _idleMoveJson;
        private JSONStorableFloat _idleMoveLivelyJson;
        private IdleMovementGate _idleMove;
        private IdlePoserLink _poser;
        private bool _idleMoveFresh;          // the states just changed: no jump check this frame
        private float _idleMoveStandIn;       // the standing check runs at most twice a second
        private bool _idleMoveStanding;       // its last result
        private float _idleMoveRebuildIn = -1f;   // a new liveliness is applied 1 s after the slider stopped moving
#endif
        // Character configuration wizard (after version 37): gate + recorded gender settings.
        public CharacterWizard Characters;
        /// <summary>Called when a recorded character setting changes (the plugin marks config dirty).</summary>
        public Action OnSettingsChanged;
        // Scene hooks (since version 26): values other plugins / triggers can read and set.
        private JSONStorableBool _aiSpeakingJson;
        private JSONStorableBool _userSpeakingJson;
        private JSONStorableString _sceneEventJson;
        private bool _sceneEventBusy;

        /// <summary>True while the user is talking (set by the plugin from the companion's level reports).</summary>
        public Func<bool> UserSpeaking;

        /// <summary>The test WAV shipped next to the .cslist (written by tools/build_var.py).</summary>
        public const string TestToneFile = "AIBodyTest.wav";

        /// <summary>Version 44: louder copies of the bundled tone for Speech volume above 1 (tools/build_var.py writes them
        /// with the same plain linear gain as the companion's speech, no limiter): 2x and 3x. Takes the factor (percent / 100):
        /// below 150 % the normal tone (head audio at the volume), 150 to 250 % the 2x copy, from 250 % the 3x copy (both at full
        /// head volume), i.e. 200 % = 2x and 300 % = 3x; above 300 % the 3x copy too (no new files, Don 04:16).</summary>
        public static string TestToneFileFor(float volume)
        {
            if (volume >= 2.5f) return "AIBodyTest3.wav";
            if (volume >= 1.5f) return "AIBodyTest2.wav";
            return TestToneFile;
        }

        /// <summary>Speech volume in percent (0..1000, default 100) = the factor 0..10 the companion, config.json and the config
        /// event keep using (Don 22.11.2026 04:15; maximum 1000 at 04:16; plain linear gain, no limiter).</summary>
        public const float VolumePercentMax = 1000f;
        public const string SpeechVolumeLabel = "Speech volume (%)";

        private void SetSpeechVolume(float percent)
        {
            if (!_syncingVolume && _legacyVolumeJson != null)
            {
                _syncingVolume = true;   // keeps the old factor storable equal (no valNoCallback, docs/API_AUDIT.md)
                _legacyVolumeJson.val = percent / 100f;
                _syncingVolume = false;
            }
            if (_speech != null) _speech.Volume = percent / 100f;
            if (OnSettingsChanged != null) OnSettingsChanged();   // the companion learns it from the config event "body"
        }

        /// <summary>A scene saved up to v45 has the factor in "Speech volume" (e.g. 1.0): shown as percent (100), not 1 %.</summary>
        private void SetLegacySpeechVolume(float factor)
        {
            if (_syncingVolume || _volumeJson == null) return;
            _syncingVolume = true;
            _volumeJson.val = PercentFromFactor(factor);
            _syncingVolume = false;
        }

        public static float PercentFromFactor(float factor)
        {
            return Math.Max(0f, Math.Min(factor, VolumePercentMax / 100f)) * 100f;
        }

        /// <summary>Speech volume as the factor 0..10, sent to the companion in the config event "body".</summary>
        public float SpeechVolume { get { return _volumeJson != null ? _volumeJson.val / 100f : 1f; } }

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
        private JSONStorableStringChooser _expressionChoiceJson;
        private JSONStorableStringChooser _gestureChoiceJson;
        private JSONStorableStringChooser _poseCommandChoiceJson;   // "Pose command": choosing only selects; Apply Pose applies (v52)
        private JSONStorableString _poseCommandTextJson;            // "New pose command": the spoken command for Add Pose
        private bool _syncingPoseMenu;                              // true while code (not the user) sets the menu value
        private string _addPosePose;                                // Add Pose step 2: the chosen pose (name or file path)
        private string _addPoseFile;                                // ... and its file, for the left field
        /// <summary>Reset poses (version 42): set by the plugin; restores the scene placement, AI first, then Client.</summary>
        public Func<string> ResetPosesRequested;
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

        /// <summary>The AI person (version 42: may differ from the plugin's host). Only before CreateControllers.</summary>
        public Atom Atom { get { return _atom; } }
        public void SetAtom(Atom atom) { if (atom != null && _speech == null && _poses == null) _atom = atom; }

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
            text += "  Breath morph '" + t["breath_morph"].Value + "': " + (t["breath_morph_found"].AsBool ? "found" : "NOT found (config.json body.breath_morph)") + "\n";
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
            // Off = the AI / companion side cannot move the body: expression / morph / gesture / pose / trigger /
            // idle / breathing commands are ignored and there are no idle poses (version 35). Speech still works; the plugin's
            // own idle head motion and breathing keep their own toggles. The eyes are left to VaM.
            _bodyControlJson = new JSONStorableBool("Body control", true, (bool v) =>
            {
                if (!v && _expressions != null) _expressions.Reset(0.4f);
            });
            SettingsDefaults.Bool(_plugin, _bodyControlJson);
            // Body position (22.11.2026, Don). Not registered on purpose: VaM saves the moved controllers with the scene, so a
            // saved slider value would move the character a second time on load. The sliders show the offset since the
            // plugin loaded; Reset body position takes it back.
            _moveForwardJson = new JSONStorableFloat("Move forward / back (m)", 0f, (float v) => OnBodyMove(), -5f, 5f);
            _moveRightJson = new JSONStorableFloat("Move right / left (m)", 0f, (float v) => OnBodyMove(), -5f, 5f);
            _turnJson = new JSONStorableFloat("Turn (degrees)", 0f, (float v) => OnBodyMove(), -180f, 180f);
            // Version 44: up to 3 (above 1 the companion makes its speech louder; it learns the value from the config event "body").
            // 22.11.2026 (Don 04:15/04:16): percent 0..1000, default 100; the old factor storable stays registered (no slider) so a
            // scene saved with "Speech volume": 1.0 loads as 100 %.
            _volumeJson = new JSONStorableFloat("Speech volume (%)", 100f, (float v) => SetSpeechVolume(v), 0f, VolumePercentMax);
            SettingsDefaults.Float(_plugin, _volumeJson);
            _legacyVolumeJson = new JSONStorableFloat("Speech volume", 1f, (float v) => SetLegacySpeechVolume(v), 0f, 10f);   // = VolumePercentMax / 100
            SettingsDefaults.Float(_plugin, _legacyVolumeJson);
            // Version 48 (Don 12:58): back, EasyMoan pattern. The callback only stores the value; Update applies it when idle.
            _distanceJson = new JSONStorableFloat("Full volume distance (m)", SpeechPlayer.DefaultFullVolumeDistance,
                (float v) => { if (OnSettingsChanged != null) OnSettingsChanged(); }, SpeechPlayer.MinFullVolumeDistance, SpeechPlayer.MaxFullVolumeDistance);
            SettingsDefaults.Float(_plugin, _distanceJson);
            _idleJson = new JSONStorableBool("Idle head motion", true, (bool v) => { if (_idle != null) _idle.Enabled = v; });
            SettingsDefaults.Bool(_plugin, _idleJson);
            _idleIntensityJson = new JSONStorableFloat("Idle intensity", 0.5f, (float v) => { if (_idle != null) _idle.Intensity = v; }, 0f, 1f);
            SettingsDefaults.Float(_plugin, _idleIntensityJson);
            _breathingJson = new JSONStorableBool("Breathing", true, (bool v) => { if (_breathing != null) _breathing.Enabled = v; });
            SettingsDefaults.Bool(_plugin, _breathingJson);
            _breathRateJson = new JSONStorableFloat("Breaths per minute", 14f, (float v) => { if (_breathing != null) _breathing.Rate = v; }, 4f, 40f);
            SettingsDefaults.Float(_plugin, _breathRateJson);
            _breathDepthJson = new JSONStorableFloat("Breath depth", 0.35f, (float v) => { if (_breathing != null) _breathing.Depth = v; }, 0f, 1f);
            SettingsDefaults.Float(_plugin, _breathDepthJson);
            // TODO(verify): choose a chest morph that exists on the character.
            _breathMorphJson = new JSONStorableString("Breath morph", "Breath1", (string v) => { if (_breathing != null) _breathing.SetMorph(v); _selfTestAge = 999f; });
            SettingsDefaults.Text(_plugin, _breathMorphJson);
            _idlePosesJson = new JSONStorableBool("Idle poses", true, (bool v) => { if (_idlePoses != null) _idlePoses.Enabled = v; });
            SettingsDefaults.Bool(_plugin, _idlePosesJson);
            // Version 54 (Don 23:31): idle poses use the AIBody pose folder (+ the poses linked by pose commands and the Idle
            // default pose); this toggle adds every pose file of the library again (as in v51-v53). Off by default.
            _idleAllFilesJson = new JSONStorableBool("Idle poses from all pose files", false, (bool v) => { _poolDirty = true; });
            SettingsDefaults.Bool(_plugin, _idleAllFilesJson);
            // Version 59: ONE slider sets how often the random idle pose changes; each wait = the interval +/- 25 % at random
            // (default 165 s, 30 - 18000 s). Up to v58 two sliders (min / max wait, version 51).
            _idlePoseIntervalJson = new JSONStorableFloat(IdleIntervalLabel, IdlePoseScheduler.DefaultIntervalSeconds,
                (float v) => { if (_idlePoses != null) _idlePoses.IntervalSeconds = v; },
                IdlePoseScheduler.LowestSeconds, IdlePoseScheduler.HighestSeconds);
            SettingsDefaults.Float(_plugin, _idlePoseIntervalJson);
            // The old storables, registered AFTER the interval: a scene saved with v51-v58 restores them and the interval
            // becomes their mean. Not shown, not saved (isStorable false), not part of Reset to Default.
            _idlePoseMinJson = new JSONStorableFloat("Idle pose min wait (s)", IdlePoseScheduler.OldDefaultMinSeconds,
                (float v) => MigrateIdleInterval(), IdlePoseScheduler.LowestSeconds, IdlePoseScheduler.HighestSeconds);
            _idlePoseMinJson.isStorable = false;
            _plugin.RegisterFloat(_idlePoseMinJson);
            _idlePoseMaxJson = new JSONStorableFloat("Idle pose max wait (s)", IdlePoseScheduler.OldDefaultMaxSeconds,
                (float v) => MigrateIdleInterval(), IdlePoseScheduler.LowestSeconds, IdlePoseScheduler.HighestSeconds);
            _idlePoseMaxJson.isStorable = false;
            _plugin.RegisterFloat(_idlePoseMaxJson);
            _idlePoseDefaultJson = new JSONStorableStringChooser("Idle default pose", new List<string> { IdlePoseScheduler.DefaultIdlePose },
                IdlePoseScheduler.DefaultIdlePose, "Idle default pose", (string v) => { if (_idlePoses != null) _idlePoses.DefaultPose = v; _poolDirty = true; });
            _idlePoseDefaultJson.popupOpenCallback = RefreshCharacterChoices;
            SettingsDefaults.Chooser(_plugin, _idlePoseDefaultJson);
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
            // Version 60 (Don, call 24.11.2026): idle movement - almost no settings: on / off and how lively.
            _idleMoveJson = new JSONStorableBool("Idle movement", true, (bool v) => { if (_idleMove != null) _idleMove.Enabled = v; });
            SettingsDefaults.Bool(_plugin, _idleMoveJson);
            _idleMoveLivelyJson = new JSONStorableFloat("Idle movement liveliness", IdleMovementPlan.DefaultLiveliness,
                (float v) => { if (_idleMove != null) _idleMove.Liveliness = v; }, 0f, 1f);
            SettingsDefaults.Float(_plugin, _idleMoveLivelyJson);
#endif

            Characters = new CharacterWizard(_plugin, () => { if (OnSettingsChanged != null) OnSettingsChanged(); });
            Characters.RequestRebuild = () => { RebuildTab = true; };
            Characters.CreateStorables();

            // Manual pose / expression / gesture menu (tab AI Character). Not registered: only the
            // choice in the menu, nothing new is saved with the scene. Lists refill on opening (E25).
            // Version 52 (Don 20:48): choosing an entry in "Pose command" only selects it; Apply Pose applies it (choosing the
            // same entry again fired nothing, so "applies on choosing" worked once and then seemed broken).
            _poseCommandChoiceJson = new JSONStorableStringChooser("Pose command", new List<string>(), "", "Pose command",
                OnPoseCommandChosen);
            _poseCommandChoiceJson.popupOpenCallback = RefreshCharacterChoices;
            _poseCommandTextJson = new JSONStorableString("New pose command", "", (string v) => { });   // not registered: only typed text
            _expressionChoiceJson = new JSONStorableStringChooser("Expression", new List<string>(), "", "Expression", (string v) => { });
            _expressionChoiceJson.popupOpenCallback = RefreshCharacterChoices;
            _gestureChoiceJson = new JSONStorableStringChooser("Gesture", new List<string>(), "", "Gesture", (string v) => { });
            _gestureChoiceJson.popupOpenCallback = RefreshCharacterChoices;
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
                speech.Volume = SpeechVolume;
                _speech = speech;
            });
            if (_morphs != null)
            {
                _diag.Run("Expressions (ExpressionController)", () =>
                {
                    _expressions = new ExpressionController(_morphs);
                    _expressions.OnShowingChanged = PauseAutoExpressions;   // version 53: one writer on the face
                });
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
                _poses.SubstituteFor = SubstitutePose;   // version 58/59: every command whose pose is missing or broken
                _poses.OnPoseBroken = (string name) =>
                {
                    // version 59: a pose file that failed for a command is dropped from the idle pool too (for the session)
                    if (_idlePoses != null) _idlePoses.Exclude(name);
                    _poolDirty = true;
                    Log.Warn("Pose '" + name + "' (" + IdlePoseFile(name) + ") failed to load and is dropped from the idle pool for this session");
                };
                _poses.Vocabulary.SetStarters();   // until config.json poses.commands is read (LoadPoseCommands)
                _poses.OnPoseLoaded = () => { if (_idle != null) _idle.Rebase(); };
                // Version 52: one writer at a time - the idle motion holds still while VaM applies the pose.
                _poses.BeforePoseLoad = () =>
                {
                    if (_idle != null) _idle.HoldForPose(PoseController.SettleSeconds);
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
                    StopIdleMovement("paused while a pose is applied");   // version 60: IdlePoser off before VaM applies the pose
#endif
                };
            });
            _diag.Run("Idle poses (IdlePoseScheduler)", () =>
            {
                IdlePoseScheduler idlePoses = new IdlePoseScheduler((int)(DateTime.UtcNow.Ticks & 0x7fffffff));
                idlePoses.Enabled = _idlePosesJson == null || _idlePosesJson.val;
                if (_idlePoseIntervalJson != null) idlePoses.IntervalSeconds = _idlePoseIntervalJson.val;
                if (_idlePoseDefaultJson != null) idlePoses.DefaultPose = _idlePoseDefaultJson.val;
                _idlePoses = idlePoses;
            });
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
            _diag.Run("Idle movement (IdlePoser)", () =>
            {
                IdleMovementGate gate = new IdleMovementGate();
                gate.Enabled = _idleMoveJson == null || _idleMoveJson.val;
                if (_idleMoveLivelyJson != null) gate.Liveliness = _idleMoveLivelyJson.val;
                _idleMove = gate;
                _poser = new IdlePoserLink(_atom);
            });
#endif
            _diag.Run("Scene actions", RegisterSceneActions);
            _diag.Run("Commands (CommandRouter)", () =>
            {
                _router = new CommandRouter(_send, _speech, _expressions, _poses, _idle, _breathing,
                    () => BodyControl);
                _router.ApplyPoseFromCompanion = ApplyCompanionPose;   // version 56
            });
            _diag.Run("Load config files", ReloadConfigFiles);
        }

        /// <summary>Speech controls on the left, body settings on the right (below the mic menu).</summary>
        // ---------------------------------------------------------------- tabs (see AIBodyPlugin)

        private string _testStatus;

        /// <summary>Tab "Voice", section "Voice and sound": the character's speech volume and the local sound test
        /// (Speech volume moved here from tab AI Character on 20.11.2026; storable and config key unchanged).</summary>
        public void BuildSoundSection(UiPage page)
        {
            page.Slider(_volumeJson);
            page.Slider(_distanceJson);
            page.Button("Play test tone", () => { _testStatus = PlayTestTone(); });
            page.Button("Stop speaking", StopSpeaking);
        }

        public bool BodyControl { get { return (_bodyControlJson == null || _bodyControlJson.val) && !DollmasterOwns; } }
        /// <summary>Tab Dollmaster, Activate on: Dollmaster owns the body (AIBody keeps speech; see AIBodyPlugin).</summary>
        public Func<bool> DollmasterOwnsBody;
        public bool DollmasterOwns { get { return DollmasterOwnsBody != null && DollmasterOwnsBody(); } }
        public bool IsSpeaking { get { return _speech != null && (_speech.IsSpeaking || _speech.QueueLength > 0); } }

        /// <summary>Set when the pose menu may have to appear or vanish; the plugin rebuilds the tab next frame.</summary>
        public bool RebuildTab;

        /// <summary>Body part of the tab "AI Character" (this Person, i.e. this plugin instance).</summary>
        public void BuildCharacterTab(UiPage page)
        {
            RefreshCharacterChoices();
            // Don (20.11.2026): ordered by topic, only category headers and controls (help and status: left field).
            // Characters first: the optional setup wizard (gate, then gender steps and a clothing hint).
            if (Characters != null) Characters.Build(page);
            page.Header("<b>Body control</b>");
            page.Toggle(_bodyControlJson);
            page.Header("<b>Body position</b>");
            page.Slider(_moveForwardJson);
            page.Slider(_moveRightJson);
            page.Slider(_turnJson);
            page.Button("Reset body position", ResetBodyPosition);
            page.Header("<b>Idle poses</b>");
            page.Toggle(_idlePosesJson);
            page.Toggle(_idleAllFilesJson);
            page.ScrollablePopup(_idlePoseDefaultJson);
            page.Button("Apply idle default pose", ApplyIdleDefaultPose);   // 22.11.2026 (Don): go there now
            page.Slider(_idlePoseIntervalJson);
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
            page.Header("<b>Idle movement</b>");   // version 60: MacGruber's IdlePoser, weight shift from leg to leg
            page.Toggle(_idleMoveJson);
            page.Slider(_idleMoveLivelyJson);
#endif
            page.Header("<b>Idle motion and breathing</b>");
            page.Toggle(_idleJson);
            page.Slider(_idleIntensityJson);
            page.Toggle(_breathingJson);
            page.Slider(_breathRateJson);
            page.Slider(_breathDepthJson);
            // Version 47 (Don 22.11.2026, screenshot): the "Breath morph" header and its "Breath1" input box are gone from the
            // menu. The storable "Breath morph" (default Breath1, saved with scenes) and config.json body.breath_morph still set it.
            page.Header("<b>Expression and gesture</b>");
            page.Popup(_expressionChoiceJson);
            page.Button("Show expression", ShowChosenExpression);
            page.Button("Reset expression", () => { if (_expressions != null) _expressions.Reset(0.4f); });
            // Version 53 (Don 20:57): no separate "Reload expressions (expressions.json)" button; Reload Config JSON (tab
            // Config) and the trigger action "Reload config files" reload expressions.json.
            page.Popup(_gestureChoiceJson);
            page.Button("Play gesture", PlayChosenGesture);
            page.Header("<b>Poses</b>");
            // Version 52: Pose command (choosing selects) + Apply Pose, Add Pose, Delete Pose, Reset poses; then the list tools.
            // No empty menu (version 16): the menu and Delete Pose appear only when there is a command.
            if (_poses != null && _poses.Vocabulary.Count > 0)
            {
                page.ScrollablePopup(_poseCommandChoiceJson);
                page.Button("Apply Pose", ApplyPoseCommandNow);   // version 52: the only way the menu applies a pose
            }
            page.Button("Add Pose", StartAddPose);
            if (_addPosePose != null)
            {
                page.Header(NewPoseCommandLabel);   // the label of the field below
                if (!page.TextInput(_poseCommandTextJson))
                    _diag.Warn("Field 'New pose command' is read-only (InputField failed).");
                page.Button("Save pose command", SaveNewPoseCommand);
                page.Button("Cancel Add Pose", CancelAddPose);
            }
            if (_poses != null && _poses.Vocabulary.Count > 0) page.Button("Delete Pose", DeleteChosenPoseCommand);
            page.Button("Reset poses", ResetPoses);
            page.Button("Restore starter poses", RestoreStarterPoses);
            page.Button("Reload poses", () => { ReloadGestures(); RefreshCharacterChoices(); RebuildTab = true; });
        }

        /// <summary>Labels above the two input fields of the tab (an input field shows only its value).</summary>
        public const string BreathMorphLabel = "Breath morph";   // after version 40: "(from the Morphs tab)" is explained on the left (BreathingHelp)
        public const string NewPoseCommandLabel = "New pose command";
        /// <summary>Where Add Pose opens VaM's file browser (VaM's own pose folder, PoseController.PoseFolders[0]).</summary>
        public const string PoseBrowseFolder = "Custom/Atom/Person/Pose";

        /// <summary>Info for the tab "AI Character" in the big field on the left.</summary>
        public string CharacterInfoText()
        {
            // Version 42: the result of the last pose / expression button first, where it is seen (before, it was at the
            // very end of this long text, so Add Pose / Delete Pose looked as if they did nothing).
            string text = CharacterNote.Length > 0 ? "Last action: " + CharacterNote + "\n" : "";
            text += Characters != null ? Characters.InfoText() : "";
            text += "Poses: " + (_poses != null ? _poses.PoseNames.Count + " in the menu (" + _poses.PoseScanNote + ")" : "PoseController missing") + "\n";
            if (_poses != null && !string.IsNullOrEmpty(_poses.LastLoadCheck)) text += "Last pose load: " + _poses.LastLoadCheck + "\n";
            if (_poses != null && !string.IsNullOrEmpty(_poses.LastPlaceNote)) text += "Last place kept: " + _poses.LastPlaceNote + "\n";   // version 54
            text += PoseCommandsInfo();
            text += IdlePosesInfo();
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
            text += IdleMovementInfo();
#endif
            text += ExpressionHelp + "\n" + BodyControlHelp + "\n" + BodyPositionHelp + "\n" + BreathingHelp + "\n";
            return text;
        }

        /// <summary>What the toggle "Body control" does (version 35, the same text as in docs/SPEC.md).</summary>
        public const string BodyControlHelp = "With <b>Body control</b> off the AI and the companion app cannot move the body: no poses (also no "
            + "spoken pose commands), gestures, expressions, morphs, triggers, idle or breathing commands and no idle poses, so "
            + "the character only speaks. Your own controls <b>Pose command</b>, <b>Reset poses</b>, <b>Show expression</b> and <b>Play gesture</b> still work, and so do "
            + "the plugin's own life signs, each with its own toggle: <b>Idle head motion</b> (with the chest weight shift) and <b>Breathing</b>.";

        /// <summary>The breathing controls in running prose (20.11.2026, Don's style rule for the left fields).</summary>
        public const string BreathingHelp = "<b>Idle intensity</b> sets how much the head moves while idle. <b>Breaths per minute</b> controls how fast "
            + "the chest breathes and <b>Breath depth</b> how deep. The breathing morph is Breath1 (another name: body.breath_morph in config.json); "
            + "without it the chest still rises with each breath.";

        private string IdlePosesInfo()
        {
            if (_idlePoses == null) return "Idle poses: not available (see the log)\n";
            List<string> names = _poses != null ? _poses.PoseNames : new List<string>();
            // Version 54: the pool is counted only after something changed (Reload poses, the toggle, the default pose, a
            // dropped pose), not on every refresh of the open menu (up to v53 every 0.5 s over up to 200 poses).
            if (_poses != null && (_poses.Vocabulary.Count != _poolVocabCount || names.Count != _poolNamesCount)) _poolDirty = true;
            if (_poolDirty && _poses != null)
            {
                _poolDirty = false;
                _poolVocabCount = _poses.Vocabulary.Count;
                _poolNamesCount = names.Count;
                _poolCount = _idlePoses.Pool(_poses.Vocabulary, _poses.IdlePoolNames(IdleAllFiles), names).Count;
            }
            int pool = _poolCount;
            string home = IdlePoseScheduler.ResolveName(_idlePoses.DefaultPose, names);
            return "<b>Idle poses</b> is " + (_idlePoses.Enabled ? _idlePoses.Status : "off") + ". <b>" + IdleIntervalLabel + "</b> sets how often the "
                + "idle pose changes: each wait is the interval plus or minus 25 % at random (now between "
                + WaitText(_idlePoses.Lo) + " and " + WaitText(_idlePoses.Hi) + "); after that wait without speech or a pose command the "
                + "character takes a random pose of its " + pool + " idle poses (the pose files in " + PoseController.OwnPoseFolder
                + ", gestures.json poses, the poses of your pose commands and the Idle default pose; <b>Idle poses from all pose files</b> "
                + "(" + (IdleAllFiles ? "on" : "off") + ") adds every pose file of your library), never the same one twice in a row"
                + (_idlePoses.ExcludedCount > 0 ? "; " + _idlePoses.ExcludedCount + " pose(s) that failed to load are left out" : "")
                + ". A pose that stores its own root position no longer moves her away: she is put back to her place. Default 165 s, "
                + "range 30 to 18000 s (300 min). For an exact value type the number into the slider's value field, or set "
                + "body.idle_pose_interval_s in config.json (older min / max values become their mean). "
                + "<b>Idle default pose</b> (" + (home ?? "'" + _idlePoses.DefaultPose + "' not found") + ") is one of the poses and "
                + "<b>Apply idle default pose</b> goes there now; after your own pose command it waits "
                + IdlePoseScheduler.CooldownSeconds.ToString("0") + " s first, while Dollmaster is active it pauses, and "
                + "<b>Idle head motion</b> and <b>Breathing</b> keep running in every pose.\n";
        }

        public const string IdleMovementLabel = "Idle movement";
        public const string IdleMovementLivelinessLabel = "Idle movement liveliness";

#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
        /// <summary>Version 60: the idle movement in running prose (left field).</summary>
        private string IdleMovementInfo()
        {
            if (_idleMove == null) return "Idle movement: not available (see the log)\n";
            string problem = _poser != null && _poser.Problem.Length > 0 ? " (" + _poser.Problem + ")" : "";
            return "<b>Idle movement</b> is " + (_idleMove.Enabled ? _idleMove.Status + problem : "off") + ". While nobody moves or "
                + "poses her she stands like someone who waits: the weight goes from one leg to the other, hips and chest turn a "
                + "little, the free foot rests on its toes, the arms hang as they are. It runs in MacGruber's IdlePoser ("
                + IdleMovementPlan.PoserPackage + ", free on the VaM Hub) on the AI character only, starts from her current "
                + "standing pose and stops at once when you grab her, load a pose on her or give a pose command; then it waits "
                + "like the idle poses (" + IdlePoseScheduler.CooldownSeconds.ToString("0") + " s). <b>Idle movement liveliness</b> "
                + "sets how far and how often she shifts (0 = calm, 1 = restless).\n";
        }
#endif

        /// <summary>"300 s (5 min)": seconds, with minutes from one minute on.</summary>
        public static string WaitText(float seconds)
        {
            string text = seconds.ToString("0") + " s";
            if (seconds >= 60f) text += " (" + (seconds / 60f).ToString(seconds % 60f < 0.5f ? "0" : "0.0") + " min)";
            return text;
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

        /// <summary>Fills the pose / expression / gesture menus from what this body really has.</summary>
        public void RefreshCharacterChoices()
        {
            if (_poseCommandChoiceJson == null) return;
            List<string> poses = _poses != null ? _poses.PoseNames : new List<string>();
            List<string> commands = new List<string>();
            if (_poses != null) for (int i = 0; i < _poses.Vocabulary.Count; i++) commands.Add(_poses.Vocabulary.Get(i).Command);
            _syncingPoseMenu = true;
            try
            {
                _poseCommandChoiceJson.choices = commands;   // E9, E24, E25
                // version 58 (Don 16:09: no empty dropdown): the first command when none is chosen; choosing only selects
                // since version 52 (Apply Pose applies), so this applies nothing
                if (!commands.Contains(_poseCommandChoiceJson.val)) _poseCommandChoiceJson.val = commands.Count > 0 ? commands[0] : "";
            }
            finally { _syncingPoseMenu = false; }
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
                // version 59: no "unavailable" command: a missing (or broken) pose gets a substitute pose
                lines += "  " + v.Get(i).Command + (ok ? "" : "  - no pose '" + v.Get(i).Pose + "': uses another pose (substitute)") + "\n";
            }
            return "There are " + v.Count + " pose commands (" + ready + " with their own pose); say or type one of them, also inside a sentence "
                + "(\"please sit down now\"; not after \"don't\" or \"never\"). Any command whose pose file is missing or broken loads "
                + "a random pose of the idle pool instead (substitute; failed files and the current pose skipped), else the Idle default pose. Choosing an entry in <b>Pose command</b> only selects it; <b>Apply Pose</b> applies it (as often as "
                + "you press it). A pose is loaded once and the idle head motion holds still for a second meanwhile; while Dollmaster "
                + "is active it poses the body and pose commands wait. Only pose presets (.vap) work. <b>Add Pose</b> opens VaM's file browser in " + PoseBrowseFolder + ": choose the pose file, then type "
                + "the spoken command into <b>New pose command</b> (it starts with the file name) and press <b>Save pose command</b>"
                + " (<b>Cancel Add Pose</b> drops it). <b>Delete Pose</b> removes the command chosen in <b>Pose command</b>. "
                + "<b>Reset poses</b> puts both people back where the scene placed them, first the AI, then the client. "
                + "<b>Restore starter poses</b> brings back missing starter commands. Every change is saved in config.json at once.\n" + lines;
        }

        /// <summary>Add Pose step 1 (version 42, Don 18:27): VaM's file browser for the pose file (E37).</summary>
        private void StartAddPose()
        {
            if (_poses == null) { Note("<color=red>Add Pose: PoseController missing</color>", true); return; }
            try
            {
                // E37: vam-timeline calls GetMediaPathDialog(callback, ext, folder, false, true) on 1.20+; false = only
                // VaM's folders and packages (a file outside VaM could not be loaded in the sandbox anyway).
                SuperController.singleton.GetMediaPathDialog(OnPoseFileChosen, "vap", PoseBrowseFolder, false, true);
                Note("Add Pose: choose the pose file in VaM's file browser (" + PoseBrowseFolder + ").", false);
            }
            catch (Exception e)
            {
                Note("<color=red>Add Pose: the file browser could not open: " + e.Message + "</color>", true);
            }
        }

        /// <summary>Add Pose step 2: the file is chosen; the field asks for the spoken command.</summary>
        private void OnPoseFileChosen(string path)
        {
            if (string.IsNullOrEmpty(path)) { Note("Add Pose cancelled (no file chosen).", false); return; }
            try { path = FileManagerSecure.NormalizePath(path); }   // E37 (Timeline L214)
            catch (Exception) { }
            path = path.Replace('\\', '/');
            string name = _poses != null ? _poses.PoseNameOfFile(path) : null;
            _addPosePose = name ?? path;   // a listed pose keeps its name (the AI and the left field show it); else the path
            _addPoseFile = path;
            string label = path.Substring(path.LastIndexOf('/') + 1);
            int dot = label.LastIndexOf('.');
            if (dot > 0) label = label.Substring(0, dot);
            if (label.StartsWith("Preset_")) label = label.Substring(7);
            _poseCommandTextJson.val = label;
            Note("Add Pose: pose file " + path + ". Type the spoken command into <b>New pose command</b> and press <b>Save pose command</b>"
                + ".", false);
            RebuildTab = true;
        }

        private void SaveNewPoseCommand()
        {
            if (_poses == null || _addPosePose == null) { Note("<color=red>Add Pose: choose a pose file first</color>", true); return; }
            string command = _poseCommandTextJson.val;
            string error = _poses.Vocabulary.Add(command, _addPosePose);
            if (error != null) { Note("<color=red>Add Pose: " + error + "</color>", true); return; }
            string added = PoseVocabulary.Collapse(command);
            Note("Pose command added: '" + added + "' -> " + _addPoseFile, false);
            _addPosePose = null;
            _addPoseFile = null;
            _poseCommandTextJson.val = "";
            RefreshCharacterChoices();
            PoseCommand entry = _poses.Vocabulary.Match(added);
            SelectPoseCommandQuietly(entry != null ? entry.Command : "");
            PoseCommandsChanged();
        }

        private void CancelAddPose()
        {
            _addPosePose = null;
            _addPoseFile = null;
            _poseCommandTextJson.val = "";
            Note("Add Pose cancelled.", false);
            RebuildTab = true;
        }

        private void DeleteChosenPoseCommand()
        {
            if (_poses == null) { Note("<color=red>Delete Pose: PoseController missing</color>", true); return; }
            string command = _poseCommandChoiceJson.val;
            if (string.IsNullOrEmpty(command)) { Note("<color=red>Delete Pose: choose the command in <b>Pose command</b> first</color>", true); return; }
            if (!_poses.Vocabulary.Remove(command)) { Note("<color=red>Delete Pose: '" + command + "' is not in the list</color>", true); return; }
            Note("Pose command deleted: '" + command + "'", false);
            RefreshCharacterChoices();
            SelectPoseCommandQuietly("");
            PoseCommandsChanged();
        }

        private void RestoreStarterPoses()
        {
            if (_poses == null) { Note("<color=red>Restore starter poses: PoseController missing</color>", true); return; }
            int added = _poses.Vocabulary.RestoreStarters();
            Note(added == 0 ? "All starter pose commands are already there" : added + " starter pose command(s) restored", false);
            RefreshCharacterChoices();
            if (added > 0) PoseCommandsChanged();
            else RebuildTab = true;
        }

        private void ResetPoses()
        {
            string result = ResetPosesRequested != null ? ResetPosesRequested() : "<color=red>Reset poses: not available</color>";
            if (_idlePoses != null) _idlePoses.NoteUserPose();
            if (_poses != null) _poses.Guard.Rebase();   // version 56: back to the scene placement is a deliberate move
            if (_idle != null) _idle.Rebase();
            Note(result, result.StartsWith("<color=red>"));
        }

        /// <summary>Version 42 (root cause of "Add / Delete Pose do nothing", part 2): a change of the list was never written
        /// to config.json (no MarkConfigDirty), so it was lost with the next config.json load. Now written at once.</summary>
        private void PoseCommandsChanged()
        {
            if (OnSettingsChanged != null) OnSettingsChanged();
            RebuildTab = true;
        }

        private void SelectPoseCommandQuietly(string command)
        {
            _syncingPoseMenu = true;
            try { _poseCommandChoiceJson.val = command; }
            finally { _syncingPoseMenu = false; }
        }

        /// <summary>The result of a pose button: in the left field (first line) and always in VaM's log.</summary>
        private void Note(string text, bool problem)
        {
            CharacterNote = text;
            string plain = text.Replace("<color=red>", "").Replace("</color>", "").Replace("<b>", "").Replace("</b>", "");
            if (problem) Log.Warn(plain); else Log.Info(plain);
        }

        /// <summary>Reads config.json poses.commands. A missing key, an empty list or a list without one usable entry =
        /// the ten starter commands (version 35, Don: they are in the configuration from the start); the next write of
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
            if (v.Count > 0 && v.MigrateBuiltIns())
                Log.Info("config.json poses.commands: the v32-v58 starter commands were replaced by the " + PoseVocabulary.StarterCommands.Length + " built-in commands of version 59");
            if (v.Count == 0)
            {
                v.SetStarters();
                Log.Info("config.json poses.commands missing or empty: the " + v.Count + " starter pose commands are used and saved");
            }
            RefreshCharacterChoices();
            RebuildTab = true;
        }

        /// <summary>Version 52 (Don 20:48, decision): choosing an entry in "Pose command" only selects it; <b>Apply Pose</b>
        /// applies it (also again and again). Same rule as "Idle default pose" + "Apply idle default pose".</summary>
        private void OnPoseCommandChosen(string command)
        {
            if (_syncingPoseMenu || string.IsNullOrEmpty(command)) return;
            Note("Pose command chosen: '" + command + "' - press Apply Pose", false);
        }

        // ---------------------------------------------------------------- body position (22.11.2026)

        private JSONStorableFloat _moveForwardJson;
        private JSONStorableFloat _moveRightJson;
        private JSONStorableFloat _turnJson;
        // Version 54 (Don 23:28): the sliders are offsets from her HOME placement (the main controller when the first slider
        // moved away from 0); every change puts her there ABSOLUTELY and rigidly (BodyMover.Relocate), Reset puts her home.
        private bool _homeSet;
        private Vector3 _homePos;
        private Quaternion _homeRot;
        private bool _syncingMove;

        public const string BodyPositionHelp = "<b>Body position</b> moves the whole AI character: <b>Move forward / back (m)</b> and "
            + "<b>Move right / left (m)</b> go the way she faces, <b>Turn (degrees)</b> turns her on the spot, and <b>Reset body position</b> "
            + "takes all of it back. Save the scene to keep the new place. Since version 54 the whole character moves as one piece, and a "
            + "pose that stores its own root position (idle poses, pose commands) no longer pulls her away: she is put back to her place.";

        /// <summary>A slider changed: the person goes to home + the three offsets (absolute; a slider fires while it is dragged).</summary>
        private void OnBodyMove()
        {
            if (_syncingMove || _atom == null || _atom.mainController == null) return;
            if (!_homeSet)
            {
                _homePos = _atom.mainController.transform.position;
                _homeRot = _atom.mainController.transform.rotation;
                _homeSet = true;
            }
            Vector3 pos = BodyMover.TargetPosition(_homePos, _homeRot, _moveForwardJson.val, _moveRightJson.val, _turnJson.val);
            Quaternion rot = Quaternion.Euler(0f, _turnJson.val, 0f) * _homeRot;
            int n = BodyMover.Relocate(_atom, pos, rot);
            if (_poses != null) _poses.Guard.Rebase();   // version 56: a pose guard still running keeps the NEW place
            if (_idle != null) _idle.Rebase();   // the idle head motion starts from the new place
            Log.Debug("Body position: forward " + _moveForwardJson.val.ToString("0.00") + " m, right " + _moveRightJson.val.ToString("0.00")
                + " m, turn " + _turnJson.val.ToString("0") + " degrees (" + n + " controllers)");
        }

        /// <summary>Button "Reset body position": back to the home placement; the sliders show 0 again.</summary>
        private void ResetBodyPosition()
        {
            if (_atom == null) return;
            if (_homeSet) BodyMover.Relocate(_atom, _homePos, _homeRot);
            if (_poses != null) _poses.Guard.Rebase();   // version 56
            _homeSet = false;
            _syncingMove = true;
            try { _moveForwardJson.val = 0f; _moveRightJson.val = 0f; _turnJson.val = 0f; }
            finally { _syncingMove = false; }
            if (_idle != null) _idle.Rebase();
            Note("Body position reset", false);
        }

        /// <summary>Version 54: Reset poses put her back to the scene placement; the Body position offsets start at 0 again.</summary>
        public void ForgetBodyPosition()
        {
            _homeSet = false;
            _syncingMove = true;
            try { _moveForwardJson.val = 0f; _moveRightJson.val = 0f; _turnJson.val = 0f; }
            finally { _syncingMove = false; }
        }

        /// <summary>Version 59: the slider label (the storable name).</summary>
        public const string IdleIntervalLabel = "Idle pose interval (s)";

        /// <summary>Version 59: an old scene restored "Idle pose min / max wait (s)": the interval becomes their mean.</summary>
        private void MigrateIdleInterval()
        {
            if (_idlePoseIntervalJson == null || _idlePoseMinJson == null || _idlePoseMaxJson == null) return;
            // both back at their old defaults (a v59 scene without the old keys resets them): keep the interval
            if (_idlePoseMinJson.val == IdlePoseScheduler.OldDefaultMinSeconds && _idlePoseMaxJson.val == IdlePoseScheduler.OldDefaultMaxSeconds) return;
            _idlePoseIntervalJson.val = IdlePoseScheduler.MigrateInterval(_idlePoseMinJson.val, _idlePoseMaxJson.val);
        }

        /// <summary>Button "Apply idle default pose" (22.11.2026, Don: idle pose control in the menu): the pose chosen in
        /// "Idle default pose", applied now; the idle poses then wait their full time again.</summary>
        private void ApplyIdleDefaultPose()
        {
            if (_poses == null || _idlePoses == null) { Note("<color=red>Apply idle default pose: poses not available</color>", true); return; }
            if (DollmasterOwns) { Note("<color=red>Apply idle default pose: " + DollmasterPoseNote + "</color>", true); return; }
            string pose = IdlePoseScheduler.ResolveName(_idlePoseDefaultJson.val, _poses.PoseNames);
            if (pose == null) { Note("<color=red>Apply idle default pose: this character has no pose '" + _idlePoseDefaultJson.val + "' (Reload poses)</color>", true); return; }
            string error = _poses.ApplyPose(pose);
            if (error == null) { _idlePoses.NoteUserPose(); _idlePoses.NoteShown(pose); Note("Idle default pose applied: " + pose, false); }
            else Note("<color=red>Apply idle default pose '" + pose + "': " + error + "</color>", true);
        }

        /// <summary>
        /// Version 56 (Don 15:28): a pose command from the companion (spoken or typed pose command, the AI's pose tool) takes
        /// the same path as the menu's Apply Pose: refused while Dollmaster poses the body, applied through PoseController
        /// (PoseGuard.Around: her place is kept), the idle poses wait CooldownSeconds and do not repeat it, a status note.
        /// </summary>
        public string ApplyCompanionPose(string json)
        {
            if (_poses == null) return "PoseController missing";
            if (DollmasterOwns) { Note("<color=red>Pose command (voice): " + DollmasterPoseNote + "</color>", true); return DollmasterPoseNote; }
            string error = _poses.ApplyPoseJson(json);
            if (error == null)
            {
                if (_idlePoses != null) { _idlePoses.NoteUserPose(); _idlePoses.NoteShown(_poses.LastJsonPose); }
                if (_poses.LastJsonSubstitute)
                    Note("Pose command (voice) '" + _poses.LastJsonCommand + "': " + _poses.LastJsonProblem
                         + ", used '" + _poses.LastJsonPose + "' instead (substitute)", false);
                else Note("Pose command (voice) applied: '" + _poses.LastJsonCommand + "' -> " + _poses.LastJsonPose, false);
            }
            else Note("<color=red>Pose command (voice): " + error + "</color>", true);
            return error;
        }

        private readonly System.Random _substituteRandom = new System.Random();

        /// <summary>
        /// Version 58 (Don 23.11.2026 / 24.11.2026 16:07): the substitute for a built-in command (Sit Down, ...) whose own
        /// pose file the character does not have: a random pose of the idle pool (AIBody pose folder + linked poses, without
        /// failed ones and without the pose shown last), else the Idle default pose; null = no pose at all. Logged.
        /// </summary>
        public string SubstitutePose(PoseCommand entry)
        {
            if (_poses == null) return null;
            List<string> pool = new List<string>();
            if (_idlePoses != null)
            {
                List<string> all = _idlePoses.WithoutLast(_idlePoses.Pool(_poses.Vocabulary, _poses.IdlePoolNames(IdleAllFiles), _poses.PoseNames));
                for (int i = 0; i < all.Count; i++) if (_poses.PoseFileProblem(all[i]) == null) pool.Add(all[i]);
            }
            string pick = pool.Count > 0 ? pool[_substituteRandom.Next(pool.Count)]
                : IdlePoseScheduler.ResolveName(_idlePoseDefaultJson != null ? _idlePoseDefaultJson.val : "", _poses.PoseNames);
            string command = entry != null ? entry.Command : "?";
            if (pick == null) Log.Warn("Pose command '" + command + "': no pose '" + command + "' and no other pose to use instead");
            else Log.Info("Pose command '" + command + "': no pose '" + command + "' on this character, substitute '" + pick + "'"
                          + (pool.Count > 0 ? " (random of " + pool.Count + " poses of the idle pool)" : " (the Idle default pose)"));
            return pick;
        }

        /// <summary>Version 56: Dollmaster montages keep her place with the same wrapper (PoseGuard.Around).</summary>
        public PoseGuard PoseGuard { get { return _poses != null ? _poses.Guard : null; } }

        /// <summary>Version 52: while Dollmaster is active it poses the body itself; a second pose system would fight it.</summary>
        public const string DollmasterPoseNote = "Dollmaster is active and poses the body itself (tab Dollmaster: turn Activate off to use pose commands)";

        /// <summary>Button "Apply Pose" (22.11.2026): the command chosen in "Pose command", applied now.</summary>
        private void ApplyPoseCommandNow()
        {
            string command = _poseCommandChoiceJson != null ? _poseCommandChoiceJson.val : "";
            if (string.IsNullOrEmpty(command)) { Note("<color=red>Apply Pose: choose the command in <b>Pose command</b> first</color>", true); return; }
            ApplyPoseCommand(command);
        }

        private void ApplyPoseCommand(string command)
        {
            if (_poses == null) { Note("<color=red>Pose command: PoseController missing</color>", true); return; }
            if (DollmasterOwns) { Note("<color=red>Pose command '" + command + "': " + DollmasterPoseNote + "</color>", true); return; }
            PoseCommand entry = _poses.Vocabulary.Match(command);
            // version 59: the same failover as a spoken command (PoseController.ApplyCommand: substitute pose)
            string error = entry == null ? "'" + command + "' is not in the list" : _poses.ApplyCommand(entry);
            string pose = error == null ? _poses.LastJsonPose : null;
            if (error == null && _idlePoses != null) { _idlePoses.NoteUserPose(); _idlePoses.NoteShown(pose); }
            if (error == null && _poses.LastJsonSubstitute)
                Note("Pose command '" + command + "': " + _poses.LastJsonProblem + ", used '" + pose + "' instead (substitute)", false);
            else if (error == null) Note("Pose command applied: '" + command + "' -> " + pose, false);
            else Note("<color=red>Pose command '" + command + "': " + error + "</color>", true);
        }

        /// <summary>Button "Show expression" (version 53: works without opening the menu first, never starts on "neutral",
        /// and says how many of the expression's morphs the character has).</summary>
        private void ShowChosenExpression()
        {
            if (_expressions == null) { Note("<color=red>Show expression: no morphs on this character (see the Self-test in tab Config)</color>", true); return; }
            if (DollmasterOwns) { Note("<color=red>Show expression: Dollmaster is active and owns the face (tab Dollmaster)</color>", true); return; }
            if (string.IsNullOrEmpty(_expressionChoiceJson.val)) RefreshCharacterChoices();
            string name = _expressionChoiceJson.val;
            if (!_expressions.SetExpression(name, 1f, 0.4f, -1f)) { Note("<color=red>Show expression: unknown expression '" + name + "'</color>", true); return; }
            bool none = _expressions.LastResult.StartsWith("0 of ") && !_expressions.LastResult.StartsWith("0 of 0");
            Note((none ? "<color=red>" : "") + "Expression '" + name + "': " + _expressions.LastResult
                + (none ? " - check the morph names in expressions.json against the character's Morphs tab</color>" : ""), none);
        }

        // ---------------------------------------------------------------- VaM's Auto Expressions (version 53)

        private bool _autoPaused;
        private bool _autoWasOn;

        /// <summary>
        /// Version 53 (Don 20:49, "expressions do not work / are not visible"): VaM's own Auto Expressions (storable
        /// "AutoExpressions", param "enabled", on by default) animates the same face morphs every frame and covered ours -
        /// two writers on the face, the same pattern as the pose twitching. While an AIBody expression is shown it is paused,
        /// afterwards it is put back as it was. Dollmaster switches it off the same way (DmConfig, E39).
        /// </summary>
        private void PauseAutoExpressions(bool showing)
        {
            try
            {
                JSONStorable auto = _atom != null ? _atom.GetStorableByID("AutoExpressions") : null;
                JSONStorableBool enabled = auto != null ? auto.GetBoolJSONParam("enabled") : null;
                if (enabled == null) return;
                if (showing && !_autoPaused)
                {
                    _autoWasOn = enabled.val;
                    _autoPaused = true;
                    if (_autoWasOn) { enabled.val = false; Log.Debug("Auto Expressions paused while an AIBody expression shows"); }
                }
                else if (!showing && _autoPaused)
                {
                    _autoPaused = false;
                    if (_autoWasOn) { enabled.val = true; Log.Debug("Auto Expressions back on"); }
                }
            }
            catch (Exception e) { Log.Warn("Auto Expressions could not be switched: " + Diag.Describe(e)); }
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
            body["speech_volume"].AsFloat = SpeechVolume;   // config.json keeps the factor 0..10
            if (_distanceJson != null) body["full_volume_distance"].AsFloat = _distanceJson.val;
            // Version 52: the user's own toggle. Up to v51 the EFFECTIVE value (false while Dollmaster owns the body) was
            // written, read back with the next config.json load, and Body control stayed off after Dollmaster was used.
            body["body_control"].AsBool = _bodyControlJson == null || _bodyControlJson.val;
            body["idle_motion"].AsBool = _idleJson.val;
            body["idle_intensity"].AsFloat = _idleIntensityJson.val;
            body["breathing"].AsBool = _breathingJson.val;
            body["breaths_per_minute"].AsFloat = _breathRateJson.val;
            body["breath_depth"].AsFloat = _breathDepthJson.val;
            body["breath_morph"] = _breathMorphJson.val;
            body["idle_poses"].AsBool = _idlePosesJson.val;
            body["idle_poses_all_files"].AsBool = _idleAllFilesJson.val;   // version 54
            body["idle_pose_interval_s"].AsFloat = _idlePoseIntervalJson.val;   // version 59 (was idle_pose_min_s / _max_s)
            body["idle_pose_default"] = _idlePoseDefaultJson.val;
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
            body["idle_movement"].AsBool = _idleMoveJson.val;                    // version 60
            body["idle_movement_liveliness"].AsFloat = _idleMoveLivelyJson.val;
#endif
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
            if (Characters != null) Characters.WriteSettings(root);
        }

        public void ApplySettings(JSONClass root)
        {
            if (Characters != null) Characters.ApplySettings(root);
            JSONClass body = root["body"] as JSONClass;
            if (body == null || _volumeJson == null) return;
            _volumeJson.val = PercentFromFactor(Protocol.GetFloat(body, "speech_volume", SpeechVolume));   // factor -> percent
            if (_distanceJson != null) _distanceJson.val = Protocol.GetFloat(body, "full_volume_distance", _distanceJson.val);
            if (_bodyControlJson != null) _bodyControlJson.val = Protocol.GetBool(body, "body_control", _bodyControlJson.val);
            _idleJson.val = Protocol.GetBool(body, "idle_motion", _idleJson.val);
            _idleIntensityJson.val = Protocol.GetFloat(body, "idle_intensity", _idleIntensityJson.val);
            _breathingJson.val = Protocol.GetBool(body, "breathing", _breathingJson.val);
            _breathRateJson.val = Protocol.GetFloat(body, "breaths_per_minute", _breathRateJson.val);
            _breathDepthJson.val = Protocol.GetFloat(body, "breath_depth", _breathDepthJson.val);
            _breathMorphJson.val = Protocol.GetString(body, "breath_morph", _breathMorphJson.val);
            _idlePosesJson.val = Protocol.GetBool(body, "idle_poses", _idlePosesJson.val);
            _idleAllFilesJson.val = Protocol.GetBool(body, "idle_poses_all_files", _idleAllFilesJson.val);   // version 54
            // version 59: idle_pose_interval_s; a config.json of v51-v58 (idle_pose_min_s / _max_s only) gives their mean
            if (Protocol.Has(body, "idle_pose_interval_s"))
                _idlePoseIntervalJson.val = Protocol.GetFloat(body, "idle_pose_interval_s", _idlePoseIntervalJson.val);
            else if (Protocol.Has(body, "idle_pose_min_s") || Protocol.Has(body, "idle_pose_max_s"))
                _idlePoseIntervalJson.val = IdlePoseScheduler.MigrateInterval(
                    Protocol.GetFloat(body, "idle_pose_min_s", IdlePoseScheduler.OldDefaultMinSeconds),
                    Protocol.GetFloat(body, "idle_pose_max_s", IdlePoseScheduler.OldDefaultMaxSeconds));
            string home = Protocol.GetString(body, "idle_pose_default", _idlePoseDefaultJson.val);
            if (home.Length > 0) SetChooserValue(_idlePoseDefaultJson, home);
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
            _idleMoveJson.val = Protocol.GetBool(body, "idle_movement", _idleMoveJson.val);   // version 60
            _idleMoveLivelyJson.val = Protocol.GetFloat(body, "idle_movement_liveliness", _idleMoveLivelyJson.val);
#endif
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
            RefreshCharacterChoices();   // version 53: the Expression menu shows the new presets at once
        }

        /// <summary>Version 53: help of the Expression part (left info field).</summary>
        public const string ExpressionHelp = "<b>Expression</b>: choose one and press <b>Show expression</b>; it stays until "
            + "<b>Reset expression</b> (or the next expression). The note above says how many of its morphs this character has; "
            + "while an AIBody expression shows, VaM's own Auto Expressions pause so they do not cover it, and come back afterwards. "
            + "Your own expressions: Saves/PluginData/AIBody/expressions.json (morph display names from the Morphs tab), "
            + "reloaded by <b>Reload Config JSON</b> in tab Config (and by the trigger action \"Reload config files\").";

        /// <summary>Version 53: for the Reload Config JSON status line.</summary>
        public string ExpressionsNote
        {
            get { return _expressions != null ? _expressions.PresetCount + " expressions (" + ExpressionsPath + ")" : "expressions not available (no morphs)"; }
        }

        public void ReloadGestures()
        {
            if (_poses == null) return;
            _poses.LoadGestureFile(GesturesPath);
            _poses.ScanPoseFiles();
            _poolDirty = true;
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
            string path = folder + "/" + TestToneFileFor(SpeechVolume);
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
            _router.Handle(msg);   // version 56: a pose command notes the idle poses in ApplyCompanionPose (only when applied)
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
                    // version 59: no "available" field any more (every command runs, a missing pose gets a substitute)
                    poseCommands.Add(entry);
                }
            }
            s["pose_commands"] = poseCommands;
            s["body_control"].AsBool = BodyControl;   // off: the companion offers the AI no body tools
            s["selftest"] = SelfTestJson();   // in-game checks, logged by the companion when they change
        }

        private void OnSpeechStarted(string id, float duration)
        {
            if (IsLocal(id)) return;
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

        /// <summary>Version 36: false while VaM's plugin UI is closed; then no status strings are built per frame.</summary>
        public bool UiVisible = true;

        public void Update(float dt)
        {
            if (_idlePoses != null) _idlePoses.Describe = UiVisible;
            _lastCommandAge += dt;
            _selfTestAge += dt;
            if (_speech != null)
            {
                _speech.Update(dt);
                // Version 48: the full volume distance only from here, only when it changed and nothing plays or waits.
                _speech.UpdateDistance(_distanceJson != null ? _distanceJson.val : SpeechPlayer.DefaultFullVolumeDistance);
            }
            bool speaking = _speech != null && _speech.IsSpeaking;
            if (_poses != null) _poses.Update(dt);   // version 52: the check SettleSeconds after a pose load
            if (DollmasterOwns)
            {
                UpdateSceneState(speaking);   // Dollmaster owns expressions, breathing, idle motion and poses
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
                UpdateIdleMovement(dt);       // version 60: stops IdlePoser (Body control is off while Dollmaster is active)
#endif
                return;
            }
            if (_expressions != null) _expressions.Update(dt);
            if (_breathing != null) _breathing.Update(dt, speaking);
            UpdateSceneState(speaking);
            UpdateIdlePoses(dt, speaking);
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
            UpdateIdleMovement(dt);
#endif
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

        // Version 57 (Don 15:57): a pose that fails is dropped from the idle pool at once (first failure, for the session)
        // and the next pose is picked and loaded right away (next frame, no cooldown). The idle poses are never switched off
        // for the session (up to v55 one exception did that; v56 paused 30 s). Every failure shrinks the pool, so this ends:
        // when no pose is left it logs once and waits (a pose that is added or linked later is used again).
        private bool _idleNextNow;
        private bool _idleEmptyLogged;
        private string _idleLastError;

        /// <summary>Version 54: setting "Idle poses from all pose files" (config.json body.idle_poses_all_files).</summary>
        private bool IdleAllFiles { get { return _idleAllFilesJson != null && _idleAllFilesJson.val; } }

        private void UpdateIdlePoses(float dt, bool speaking)
        {
            if (_idlePoses == null || _poses == null) return;
            try
            {
                bool busy = speaking || (UserSpeaking != null && UserSpeaking()) || (_speech != null && _speech.QueueLength > 0);
                string pose;
                if (_idleNextNow)
                {
                    // the pose before failed: the next one now (still not while someone speaks, Body control off or idle off)
                    if (!_idlePoses.Enabled || !BodyControl) { _idleNextNow = false; return; }
                    if (busy) return;
                    _idleNextNow = false;
                    pose = _idlePoses.PickNow(_poses.Vocabulary, _poses.IdlePoolNames(IdleAllFiles), _poses.PoseNames);
                }
                else pose = _idlePoses.Update(dt, busy, BodyControl, _poses.Vocabulary, _poses.IdlePoolNames(IdleAllFiles), _poses.PoseNames);
                if (pose == null)
                {
                    if (_idlePoses.PoolSize == 0 && _idlePoses.ExcludedCount > 0 && !_idleEmptyLogged)
                    {
                        _idleEmptyLogged = true;
                        Log.Warn("Idle poses: no pose left in the idle pool (all " + _idlePoses.ExcludedCount
                                 + " failed and were left out) - waiting for a working pose (fix the pose files; they stay left out until VaM reloads the plugin)");
                    }
                    return;
                }
                _idleEmptyLogged = false;
                // Version 54: a pose file that is gone or cannot be loaded is dropped from the pool for this session.
                // Version 56/57: an exception of this one load is this pose's error too.
                string error;
                try { error = _poses.PoseFileProblem(pose) ?? _poses.ApplyPose(pose); }
                catch (Exception e) { error = Diag.Describe(e); }
                if (error == null) Log.Debug("Idle pose: " + pose + " (random of a pool of " + _idlePoses.PoolSize + " poses)");
                else
                {
                    _idlePoses.Exclude(pose);
                    _poolDirty = true;
                    _idleNextNow = true;   // version 57: the next pose right away
                    Log.Warn("Idle pose '" + pose + "' (" + IdlePoseFile(pose) + ") failed and is dropped from the idle pool for this session; next pose now: " + error);
                }
            }
            catch (Exception e)
            {
                // Version 56 root cause of "the idle poses stop": up to v55 ANY exception here stopped them for the session.
                // Version 57: no pause and no switch-off; the next frame simply goes on. Logged once per different error.
                string text = Diag.Describe(e);
                if (text != _idleLastError) { _idleLastError = text; Log.Warn("Idle poses: error (they go on): " + text); }
            }
        }

#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
        // Version 60 (Don, call 24.11.2026): idle movement with MacGruber's IdlePoser on the AI character (IdleMovement.cs,
        // IdlePoserLink.cs). It runs only while nobody moves or poses her: grabbing a controller or a pose loaded from
        // outside stops it at once and starts the idle poses' cooldown (both wait the same way); AIBody's own pose loads
        // stop it before VaM applies the pose (BeforePoseLoad) and it starts again from the new pose when that is a
        // standing pose. Speech does not stop it (people shift their weight while they talk).
        private void UpdateIdleMovement(float dt)
        {
            if (_idleMove == null || _poser == null) return;
            try
            {
                bool loading = SuperController.singleton != null && SuperController.singleton.isLoading;   // E43
                _poser.Find(dt, _idleMove.Enabled && BodyControl, loading);   // version 61: nothing while the scene loads
                bool settling = _poses != null && _poses.Guard.Active;
                bool grabbed = _poser.Grabbed();
                bool jumped = _poser.Jumped(dt, loading || settling || _idleMoveFresh);
                _idleMoveFresh = false;
                bool outside = grabbed || jumped;
                if (outside && _idlePoses != null) _idlePoses.NoteUserPose();   // the idle poses wait the same cooldown
                if (jumped) Log.Debug("Idle movement: a controller of '" + (_atom != null ? _atom.uid : "?") + "' jumped (pose from outside): stopped, cooldown started");
                IdleMovementInputs i = new IdleMovementInputs();
                i.Available = _poser.Available;
                i.BodyControl = BodyControl;
                i.Cooldown = _idlePoses != null && _idlePoses.CooldownLeft > 0f;
                i.Settling = settling;
                i.Loading = loading;
                i.Outside = outside;
                List<IdlePart> pose = null;
                _idleMoveStandIn -= dt;
                if (_idleMove.Running || settling || outside || loading || i.Cooldown)
                {
                    _idleMoveStandIn = 0f;        // check again (fresh) right when it may start
                    _idleMoveStanding = false;
                }
                else if (i.Available && _idleMove.Enabled && i.BodyControl && !i.Cooldown && _idleMoveStandIn <= 0f)
                {
                    _idleMoveStandIn = 0.5f;
                    pose = _poser.CaptureBase();
                    _idleMoveStanding = IdleMovementPlan.IsStanding(pose);
                }
                i.Standing = _idleMoveStanding;
                IdleMovementStep step = _idleMove.Update(i);
                if (step == IdleMovementStep.Stop)
                {
                    StopIdleMovement(null);
                }
                else if (step == IdleMovementStep.Start)
                {
                    string error = StartIdleMovement(pose ?? _poser.CaptureBase());
                    if (error != null) { _idleMove.StopNow("could not start: " + error); StopIdleMovement(null); Log.Warn("Idle movement: " + error); }
                }
                else if (step == IdleMovementStep.Rebuild)
                {
                    _idleMoveRebuildIn = 1f;   // after the slider has been still for a second
                }
                if (_idleMoveRebuildIn >= 0f && _idleMove.Running)
                {
                    _idleMoveRebuildIn -= dt;
                    if (_idleMoveRebuildIn < 0f) StartIdleMovement(_poser.BasePose);
                }
            }
            catch (Exception e)
            {
                string text = Diag.Describe(e);
                if (text != _idleMoveLastError) { _idleMoveLastError = text; Log.Warn("Idle movement: error: " + text); }
            }
        }

        private string _idleMoveLastError;

        /// <summary>States from this base pose into IdlePoser, then IdlePoser on. Returns an error or null.</summary>
        private string StartIdleMovement(List<IdlePart> basePose)
        {
            if (basePose == null || _atom == null) return "no pose";
            string error = _poser.Push(IdleMovementPlan.BuildJson(_atom.uid, basePose, _idleMove.Liveliness));
            if (error != null) return error;
            _poser.BasePose = basePose;
            _idleMoveRebuildIn = -1f;
            _idleMoveFresh = true;
            if (_idle != null) _idle.ChestSuspended = true;   // one writer on the chest: IdlePoser
            _poser.SetOn(true);
            Log.Debug("Idle movement: IdlePoser runs on '" + _atom.uid + "' (" + basePose.Count + " controllers, liveliness "
                      + _idleMove.Liveliness.ToString("0.00") + ")");
            return null;
        }

        /// <summary>IdlePoser off now (it writes nothing more; she stays where she is) and the chest back to the idle motion.</summary>
        private void StopIdleMovement(string why)
        {
            if (_poser != null) _poser.SetOn(false);
            if (_idle != null) _idle.ChestSuspended = false;
            if (why != null && _idleMove != null && _idleMove.Running) _idleMove.StopNow(why);
        }
#endif

        /// <summary>The pose's file for the log (the name if it is not a file, e.g. a gestures.json pose).</summary>
        private string IdlePoseFile(string pose)
        {
            try { string path = _poses.PathOf(pose); return string.IsNullOrEmpty(path) ? pose : path; }
            catch (Exception) { return pose; }
        }

        private void UpdateSceneState(bool speaking)
        {
            if (_aiSpeakingJson != null && _aiSpeakingJson.val != speaking) _aiSpeakingJson.val = speaking;
            bool user = UserSpeaking != null && UserSpeaking();
            if (_userSpeakingJson != null && _userSpeakingJson.val != user) _userSpeakingJson.val = user;
        }

        public string StatusText()
        {
            string text = "Last command: " + (_lastCommandAge < 999f ? _lastCommandAge.ToString("0") + "s ago" : "none yet") + "\n";
            if (_speech != null)
            {
                text += "Speaking: " + (_speech.IsSpeaking ? "yes" : "no") + ", queued: " + _speech.QueueLength
                    + (_volumeJson != null && _volumeJson.val < 1f ? " – Speech volume is 0 %!" : "") + "\n";
                text += "Audio: " + (_speech.Status ?? "nothing played yet") + "\n";
                if (_distanceJson != null && _speech.DistancePending(_distanceJson.val))
                    text += "Full volume distance " + _distanceJson.val.ToString("0.0") + " m: applied as soon as the AI is not speaking\n";
                else if (!string.IsNullOrEmpty(_speech.DistanceInfo)) text += _speech.DistanceInfo + "\n";
                if (_speech.LastError != null && _speech.LastError != _speech.Status && _speech.LastErrorAge < 300f)
                    text += "<color=red>" + _speech.LastError + "</color> (" + _speech.LastErrorAge.ToString("0") + " s ago)\n";
            }
            if (DollmasterOwns) text += "Dollmaster is active (tab Dollmaster): it owns the body; AIBody only speaks\n";
            else if (!BodyControl) text += "Body control: off (speech only; no poses, gestures, expressions or idle poses from the AI side)\n";
            if (_testStatus != null) text += _testStatus + "\n";
            if (_expressions != null) text += "Expression: " + _expressions.Current + "\n";
            if (_breathing != null && _morphs != null)
                text += "Breath morph: " + (_breathing.HasMorph ? _breathing.MorphName : "'" + _breathing.MorphName + "' not found") + "\n";
            return text;
        }

        /// <summary>Stops speech and returns every touched morph / bone to its original state.</summary>
        public void Restore()
        {
            if (_speech != null) { _speech.StopAll("stopped"); _speech.RestoreDistance(); }   // Restore = plugin removed / disabled
            if (_expressions != null) _expressions.RestoreNow();
            if (_breathing != null) _breathing.RestoreNow();
            if (_idle != null) _idle.RestoreNow();
#if AIBODY_IDLEPOSER   // version 62: MacGruber IdlePoser idle movement excluded at build time (docs/IDLEPOSER_BUILD_SWITCH.md)
            StopIdleMovement("off (plugin stopped)");   // version 60: IdlePoser writes nothing more
#endif
        }
    }
}
