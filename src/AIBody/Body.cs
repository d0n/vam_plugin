// Body: the AI character's body. A plain component owned by AIBodyPlugin, no MVRScript of its own
// and no I/O: commands arrive in-process from the AppLink, events go out through the send callback.
//
//   - speech on the Person's head audio (VaM lip sync), morphs, expressions, gestures, poses,
//     idle head motion and breathing
//   - per-character settings (volume, idle, breathing, ...) saved with the Person atom
using System;
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
            _breathMorphJson = new JSONStorableString("Breath morph", "Breath1", (string v) => { if (_breathing != null) _breathing.SetMorph(v); });
            _plugin.RegisterString(_breathMorphJson);

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

        /// <summary>Sound test in the tab "Voice Mode".</summary>
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

        /// <summary>Body part of the tab "AI Character" (this Person, i.e. this plugin instance).</summary>
        public void BuildCharacterTab(UiPage page)
        {
            page.Header("<b>Körper</b> (nur diese Person)");
            page.Toggle(_bodyControlJson);
            page.Slider(_volumeJson);
            page.Toggle(_idleJson);
            page.Slider(_idleIntensityJson);
            page.Toggle(_breathingJson);
            page.Slider(_breathRateJson);
            page.Slider(_breathDepthJson);
            if (!page.TextInput(_breathMorphJson))
                _diag.Warn("Feld 'Breath morph' ist nur lesbar (InputField ging nicht).");
            page.Button("Reset expression", () => { if (_expressions != null) _expressions.Reset(0.4f); });
            page.Button("Reload Expressions", ReloadExpressions);
            page.Button("Reload Gestures", ReloadGestures);
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
        }

        public void ReloadGestures()
        {
            if (_poses != null) _poses.LoadGestureFile(GesturesPath);
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
