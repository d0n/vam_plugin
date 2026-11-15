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

        private JSONStorableFloat _volumeJson;
        private JSONStorableBool _idleJson;
        private JSONStorableFloat _idleIntensityJson;
        private JSONStorableBool _breathingJson;
        private JSONStorableFloat _breathRateJson;
        private JSONStorableFloat _breathDepthJson;
        private JSONStorableString _breathMorphJson;

        private MorphHelper _morphs;
        private SpeechPlayer _speech;
        private ExpressionController _expressions;
        private BreathingController _breathing;
        private IdleController _idle;
        private PoseController _poses;
        private CommandRouter _router;

        private float _lastCommandAge = 999f;

        public Body(MVRScript plugin, Atom atom, Action<JSONClass> send)
        {
            _plugin = plugin;
            _atom = atom;
            _send = send;
        }

        // ---------------------------------------------------------------- setup

        public void CreateStorables()
        {
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
            _morphs = new MorphHelper(_atom);
            _speech = new SpeechPlayer(_atom);
            _speech.OnStarted = OnSpeechStarted;
            _speech.OnEnded = OnSpeechEnded;
            _speech.OnError = (id, message) => _send(Protocol.NewError(id, "audio_failed", message));
            _speech.Volume = _volumeJson.val;

            _expressions = new ExpressionController(_morphs);
            _breathing = new BreathingController(_morphs, _breathMorphJson.val);
            _idle = new IdleController(_atom);
            _poses = new PoseController(_atom, _idle);
            _router = new CommandRouter(_send, _speech, _expressions, _poses, _idle, _breathing);

            _idle.Enabled = _idleJson.val;
            _idle.Intensity = _idleIntensityJson.val;
            _breathing.Enabled = _breathingJson.val;
            _breathing.Rate = _breathRateJson.val;
            _breathing.Depth = _breathDepthJson.val;
            ReloadConfigFiles();
        }

        /// <summary>Speech controls on the left, body settings on the right (below the mic menu).</summary>
        public void CreateUI()
        {
            UiHelper.Header(_plugin, "<b>Speech output</b>", false);
            _plugin.CreateSlider(_volumeJson);
            _plugin.CreateButton("Stop speaking").button.onClick.AddListener(StopSpeaking);

            UiHelper.Header(_plugin, "<b>Body</b>", true);
            _plugin.CreateToggle(_idleJson, true);
            _plugin.CreateSlider(_idleIntensityJson, true);
            _plugin.CreateToggle(_breathingJson, true);
            _plugin.CreateSlider(_breathRateJson, true);
            _plugin.CreateSlider(_breathDepthJson, true);
            UiHelper.TextInput(_plugin, _breathMorphJson, true);
            _plugin.CreateButton("Reload expressions / gestures", true).button.onClick.AddListener(ReloadConfigFiles);
        }

        public void ReloadConfigFiles()
        {
            if (_expressions != null) _expressions.LoadPresetFile(AppLink.DataRoot + "/expressions.json");
            if (_poses != null) _poses.LoadGestureFile(AppLink.DataRoot + "/gestures.json");
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
            JSONClass evt = Protocol.NewEvent(Protocol.EvtSpeechStarted);
            evt["utterance_id"] = id ?? "";
            evt["duration"].AsFloat = duration;
            _send(evt);
        }

        private void OnSpeechEnded(string id, string reason)
        {
            JSONClass evt = Protocol.NewEvent(Protocol.EvtSpeechEnded);
            evt["utterance_id"] = id ?? "";
            evt["reason"] = reason;
            evt["queue_length"].AsInt = _speech.QueueLength;
            _send(evt);
        }

        // ---------------------------------------------------------------- frame loop

        public void Update(float dt)
        {
            _lastCommandAge += dt;
            _speech.Update(dt);
            bool speaking = _speech.IsSpeaking;
            _expressions.Update(dt);
            _breathing.Update(dt, speaking);
            string finishedGesture = _idle.Update(dt, speaking, _breathing.Cycle, _breathing.CurrentDepth);
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
            text += "Speaking: " + (_speech.IsSpeaking ? "yes" : "no") + ", queued: " + _speech.QueueLength + "\n";
            text += "Expression: " + _expressions.Current + "\n";
            text += "Audio: " + (_speech.Available ? "ok" : "missing HeadAudioSource") + "\n";
            text += "Morphs: " + (_morphs.Available ? "ok" : "unavailable") + "\n";
            text += "Breath morph: " + (_morphs.Find(_breathing.MorphName) != null ? _breathing.MorphName : "not found") + "\n";
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
