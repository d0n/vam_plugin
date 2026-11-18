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
        private JSONStorableStringChooser _poseChoiceJson;
        private JSONStorableStringChooser _expressionChoiceJson;
        private JSONStorableStringChooser _gestureChoiceJson;
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
        public string SpeechError { get { return _speech != null ? _speech.LookupError : "SpeechPlayer fehlt"; } }
        public bool MorphsAvailable { get { return _morphs != null && _morphs.Available; } }
        public string MorphsError { get { return _morphs != null ? _morphs.LookupError : "MorphHelper fehlt"; } }

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
                string storage = _poses != null ? _poses.CheckPoseStorage() : "PoseController fehlt";
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
            if (Protocol.Has(t, "error")) return "  Körper-Prüfung: FEHLER " + t["error"].Value + "\n";
            string storage = t["pose_storage"].Value;
            string text = "  Pose-Speicher (PosePresets): " + (storage == "ok" ? "ja" : "NEIN (" + storage + ")") + "\n";
            text += "  Posen: " + t["poses"].AsInt + " (davon Dateien in Custom/Atom/Person/Pose: " + t["pose_files"].AsInt + ")\n";
            text += "  Atem-Morph '" + t["breath_morph"].Value + "': " + (t["breath_morph_found"].AsBool ? "gefunden" : "NICHT gefunden (Tab AI Character > Breath morph)") + "\n";
            int found = t["expression_morphs_found"].AsInt, total = t["expression_morphs_total"].AsInt;
            text += "  Ausdrucks-Morphs: " + (total == 0 ? "-" : found + " von " + total + " gefunden");
            JSONArray missing = t["expression_morphs_missing"] as JSONArray;
            if (missing != null && missing.Count > 0)
            {
                List<string> names = new List<string>();
                for (int i = 0; i < missing.Count && i < 6; i++) names.Add(missing[i].Value);
                text += " – fehlen: " + string.Join(", ", names.ToArray()) + (missing.Count > 6 ? ", …" : "");
            }
            text += "\n";
            if (t["timeline_gestures"].AsInt > 0)
                text += "  Timeline für " + t["timeline_gestures"].AsInt + " Geste(n): " + (t["timeline"].AsBool ? "ja" : "NEIN (Timeline-Plugin fehlt auf dieser Person)") + "\n";
            return text;
        }

        // ---------------------------------------------------------------- setup

        public void CreateStorables()
        {
            // Off = speech only: expression / morph / gesture / pose / trigger commands are ignored.
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

            // Manual pose / expression / gesture menu (tab AI Character). Not registered: only the
            // choice in the menu, nothing new is saved with the scene. Lists refill on opening (E25).
            _poseChoiceJson = new JSONStorableStringChooser("Pose", new List<string>(), "", "Pose", (string v) => { });
            _poseChoiceJson.popupOpenCallback = RefreshCharacterChoices;
            _expressionChoiceJson = new JSONStorableStringChooser("Expression", new List<string>(), "", "Expression", (string v) => { });
            _expressionChoiceJson.popupOpenCallback = RefreshCharacterChoices;
            _gestureChoiceJson = new JSONStorableStringChooser("Gesture", new List<string>(), "", "Gesture", (string v) => { });
            _gestureChoiceJson.popupOpenCallback = RefreshCharacterChoices;
            _plugin.RegisterAction(new JSONStorableAction("Stop speaking", StopSpeaking));
            _plugin.RegisterAction(new JSONStorableAction("Reset expression", () => { if (_expressions != null) _expressions.Reset(0.4f); }));
            _plugin.RegisterAction(new JSONStorableAction("Reload config files", ReloadConfigFiles));
        }

        public void CreateControllers()
        {
            // Each controller on its own: a failing one disables only its feature. Atom lookups
            // (HeadAudioSource, geometry, headControl) are lazy and retried, see the controllers.
            _diag.Run("Morphs (MorphHelper)", () => _morphs = new MorphHelper(_atom));
            _diag.Run("Sprachausgabe (SpeechPlayer)", () =>
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
                _diag.Run("Ausdrücke (ExpressionController)", () => _expressions = new ExpressionController(_morphs));
                _diag.Run("Atmung (BreathingController)", () =>
                {
                    BreathingController breathing = new BreathingController(_morphs, _breathMorphJson != null ? _breathMorphJson.val : "Breath1");
                    if (_breathingJson != null) breathing.Enabled = _breathingJson.val;
                    if (_breathRateJson != null) breathing.Rate = _breathRateJson.val;
                    if (_breathDepthJson != null) breathing.Depth = _breathDepthJson.val;
                    _breathing = breathing;
                });
            }
            _diag.Run("Kopfbewegung (IdleController)", () =>
            {
                IdleController idle = new IdleController(_atom);
                if (_idleJson != null) idle.Enabled = _idleJson.val;
                if (_idleIntensityJson != null) idle.Intensity = _idleIntensityJson.val;
                _idle = idle;
            });
            _diag.Run("Posen/Gesten (PoseController)", () => _poses = new PoseController(_atom, _idle));
            _diag.Run("Befehle (CommandRouter)", () =>
                _router = new CommandRouter(_send, _speech, _expressions, _poses, _idle, _breathing,
                    () => BodyControl));
            _diag.Run("Config-Dateien laden", ReloadConfigFiles);
        }

        /// <summary>Speech controls on the left, body settings on the right (below the mic menu).</summary>
        // ---------------------------------------------------------------- tabs (see AIBodyPlugin)

        private string _testStatus;

        /// <summary>Sound test in the tab "Voice", section "Voice Mode".</summary>
        public void BuildVoiceModeTab(UiPage page)
        {
            page.Button("Test-Ton abspielen", () => { _testStatus = PlayTestTone(); });
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
            page.Header("<b>Posen</b> (per Sprache über die KI, oder hier)");
            // No empty menu (version 16): without poses only "Posen neu laden"; the reason is in the info field.
            if (_poses != null && _poses.PoseNames.Count > 0)
            {
                page.ScrollablePopup(_poseChoiceJson);
                page.Button("Pose anwenden", ApplyChosenPose);
            }
            page.Button("Posen neu laden", () => { ReloadGestures(); RefreshCharacterChoices(); RebuildTab = true; });
            page.Header("<b>Ausdruck und Geste</b>");
            page.Popup(_expressionChoiceJson);
            page.Button("Ausdruck zeigen", ShowChosenExpression);
            page.Button("Reset expression", () => { if (_expressions != null) _expressions.Reset(0.4f); });
            page.Button("Ausdrücke neu laden (expressions.json)", ReloadExpressions);
            page.Popup(_gestureChoiceJson);
            page.Button("Geste abspielen", PlayChosenGesture);
            page.Header("<b>Körper</b> (nur diese Person)");
            page.Toggle(_bodyControlJson);
            page.Slider(_volumeJson);
            page.Toggle(_idleJson);
            page.Slider(_idleIntensityJson);
            page.Toggle(_breathingJson);
            page.Slider(_breathRateJson);
            page.Slider(_breathDepthJson);
            page.Header("Atem-Morph: Name des Brust-Morphs (Feld darunter)");
            if (!page.TextInput(_breathMorphJson))
                _diag.Warn("Feld 'Breath morph' ist nur lesbar (InputField ging nicht).");
        }

        /// <summary>Info for the tab "AI Character" in the big field on the left.</summary>
        public string CharacterInfoText()
        {
            string text = "Posen: " + (_poses != null ? _poses.PoseNames.Count + " im Menü und für die KI (" + _poses.PoseScanNote + ")" : "PoseController fehlt") + "\n";
            text += "Body control aus = nur Sprache, die KI steuert den Körper nicht. Atem-Morph: Name aus dem Morphs-Tab der Figur.\n";
            return text;
        }

        /// <summary>Fills the pose / expression / gesture menus from what this body really has.</summary>
        public void RefreshCharacterChoices()
        {
            if (_poseChoiceJson == null) return;
            List<string> poses = _poses != null ? _poses.PoseNames : new List<string>();
            SetMenu(_poseChoiceJson, poses);
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

        private void ApplyChosenPose()
        {
            if (_poses == null) { CharacterNote = "Pose: PoseController fehlt"; return; }
            string name = _poseChoiceJson.val;
            string error = _poses.ApplyPose(name);
            CharacterNote = error == null ? "Pose angewendet: " + name : "<color=red>Pose '" + name + "': " + error + "</color>";
            Log.Debug(CharacterNote);
        }

        private void ShowChosenExpression()
        {
            if (_expressions == null) { CharacterNote = "Ausdruck: keine Morphs auf dieser Figur"; return; }
            string name = _expressionChoiceJson.val;
            CharacterNote = _expressions.SetExpression(name, 1f, 0.4f, -1f)
                ? "Ausdruck: " + name : "<color=red>Ausdruck '" + name + "' unbekannt</color>";
        }

        private void PlayChosenGesture()
        {
            if (_poses == null) { CharacterNote = "Geste: PoseController fehlt"; return; }
            string name = _gestureChoiceJson.val;
            string error = _poses.PlayGesture(name, 0f, 0f);
            CharacterNote = error == null ? "Geste: " + name : "<color=red>Geste '" + name + "': " + error + "</color>";
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
            root["body"] = body;
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
            Log.Info(_poses.PoseScanNote + "; " + _poses.PoseNames.Count + " Posen im Menü / für die KI");
            _selfTestAge = 999f;
        }

        /// <summary>
        /// Plays the WAV shipped in the package on the head audio: checks the sound path without the
        /// companion app (and without Saves/PluginData). Returns a status line.
        /// </summary>
        public string PlayTestTone()
        {
            if (_speech == null) return "Test-Ton: Sprachausgabe fehlt";
            string folder = null;
            try { folder = PluginFolder != null ? PluginFolder() : null; }
            catch (Exception e) { return "Test-Ton: Plugin-Ordner nicht gefunden (" + Diag.Describe(e) + ")"; }
            if (string.IsNullOrEmpty(folder)) return "Test-Ton: Plugin-Ordner nicht gefunden";
            string path = folder + "/" + TestToneFile;
            string error = _speech.Enqueue(LocalPrefix + "test-" + DateTime.UtcNow.Ticks, path, true);
            return error == null ? "Test-Ton: " + path : "Test-Ton: " + error;
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

        public void Update(float dt)
        {
            _lastCommandAge += dt;
            _selfTestAge += dt;
            if (_speech != null) _speech.Update(dt);
            bool speaking = _speech != null && _speech.IsSpeaking;
            if (_expressions != null) _expressions.Update(dt);
            if (_breathing != null) _breathing.Update(dt, speaking);
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

        public string StatusText()
        {
            string text = "Last command: " + (_lastCommandAge < 999f ? _lastCommandAge.ToString("0") + "s ago" : "none yet") + "\n";
            if (_speech != null)
            {
                text += "Speaking: " + (_speech.IsSpeaking ? "yes" : "no") + ", queued: " + _speech.QueueLength
                    + (_volumeJson != null && _volumeJson.val < 0.01f ? " – Speech volume ist 0!" : "") + "\n";
                text += "Audio: " + (_speech.Status ?? "noch nichts abgespielt") + "\n";
                if (_speech.LastError != null && _speech.LastError != _speech.Status && _speech.LastErrorAge < 300f)
                    text += "<color=red>" + _speech.LastError + "</color> (vor " + _speech.LastErrorAge.ToString("0") + " s)\n";
            }
            if (!BodyControl) text += "Body control: aus (nur Sprache)\n";
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
        }
    }
}
