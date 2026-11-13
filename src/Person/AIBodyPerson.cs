// AIBody Person plugin - the body of the AI on one Person atom (Virt-A-Mate 1.22).
//
// Add on each Person atom: Plugins tab -> Add Plugin ->
//   AddonPackages > d0n.AIBodyPerson.<n>:/Custom/Scripts/d0n/AIBody/AIBodyPerson.cslist
//   (loose-file install: Custom/Scripts/d0n/AIBody/AIBodyPerson.cslist)
// Needs the AIBody Session plugin (Main UI > Session Plugins) for the companion connection.
//
// This plugin does no I/O of its own. The Session plugin finds it by scanning the scene's atoms
// and talks to it through two string params (see Protocol.PersonInboxParam/PersonOutboxParam):
//   - commands (speak, expression, gesture, pose, trigger, idle, breathing, ...) arrive one at a
//     time in "AIBody Inbox"
//   - events (speech_started/ended, errors, person_status, ...) are appended to "AIBody Outbox"
// Per-character settings (volume, idle, breathing, ...) are saved with the Person atom.
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;
using UnityEngine.UI;

namespace AIBody
{
    public class AIBodyPersonPlugin : MVRScript
    {
        public const string PluginVersion = "0.3.0";
        public const string DataRoot = "Saves/PluginData/AIBody";
        private const float StatusInterval = 2f;

        // Bridge to the Session plugin.
        private JSONStorableString _inboxJson;
        private JSONStorableString _outboxJson;
        private JSONStorableString _versionJson;

        // Per-character settings (saved with the Person atom).
        private JSONStorableFloat _volumeJson;
        private JSONStorableBool _idleJson;
        private JSONStorableFloat _idleIntensityJson;
        private JSONStorableBool _breathingJson;
        private JSONStorableFloat _breathRateJson;
        private JSONStorableFloat _breathDepthJson;
        private JSONStorableString _breathMorphJson;
        private JSONStorableBool _verboseJson;
        private JSONStorableString _statusJson;

        private MorphHelper _morphs;
        private SpeechPlayer _speech;
        private ExpressionController _expressions;
        private BreathingController _breathing;
        private IdleController _idle;
        private PoseController _poses;
        private CommandRouter _router;

        private bool _initialized;
        private bool _firstUpdate = true;
        private bool _handlingInbox;
        private float _statusTimer;
        private float _uiTimer;
        private float _lastCommandAge = 999f;
        private float _undrainedAge;

        public override void Init()
        {
            try
            {
                Log.Prefix = "AIBody Person: ";
                if (containingAtom == null || containingAtom.type != "Person")
                {
                    Log.Error("Add this plugin to a Person atom (the AIBody Session plugin goes into Session Plugins).");
                    return;
                }
                CreateStorables();
                CreateControllers();
                CreateUI();
                _initialized = true;
                SendStatus();
            }
            catch (Exception e)
            {
                Log.Error("Init failed", e);
            }
        }

        // ---------------------------------------------------------------- setup

        private void CreateStorables()
        {
            _inboxJson = new JSONStorableString(Protocol.PersonInboxParam, "", OnInbox);
            RegisterString(_inboxJson);
            _outboxJson = new JSONStorableString(Protocol.PersonOutboxParam, "");
            RegisterString(_outboxJson);
            _versionJson = new JSONStorableString(Protocol.PersonVersionParam, PluginVersion);
            RegisterString(_versionJson);

            _volumeJson = new JSONStorableFloat("Speech volume", 1f, (float v) => { if (_speech != null) _speech.Volume = v; }, 0f, 1f);
            RegisterFloat(_volumeJson);
            _idleJson = new JSONStorableBool("Idle head motion", true, (bool v) => { if (_idle != null) _idle.Enabled = v; });
            RegisterBool(_idleJson);
            _idleIntensityJson = new JSONStorableFloat("Idle intensity", 0.5f, (float v) => { if (_idle != null) _idle.Intensity = v; }, 0f, 1f);
            RegisterFloat(_idleIntensityJson);
            _breathingJson = new JSONStorableBool("Breathing", true, (bool v) => { if (_breathing != null) _breathing.Enabled = v; });
            RegisterBool(_breathingJson);
            _breathRateJson = new JSONStorableFloat("Breaths per minute", 14f, (float v) => { if (_breathing != null) _breathing.Rate = v; }, 4f, 40f);
            RegisterFloat(_breathRateJson);
            _breathDepthJson = new JSONStorableFloat("Breath depth", 0.35f, (float v) => { if (_breathing != null) _breathing.Depth = v; }, 0f, 1f);
            RegisterFloat(_breathDepthJson);
            // TODO(verify): choose a chest morph that exists on the character.
            _breathMorphJson = new JSONStorableString("Breath morph", "Breath1", (string v) => { if (_breathing != null) _breathing.SetMorph(v); });
            RegisterString(_breathMorphJson);
            _verboseJson = new JSONStorableBool("Verbose log", false, (bool v) => Log.Verbose = v);
            RegisterBool(_verboseJson);
            _statusJson = new JSONStorableString("Status", "Starting...");

            RegisterAction(new JSONStorableAction("Stop speaking", StopSpeaking));
            RegisterAction(new JSONStorableAction("Reset expression", () => { if (_expressions != null) _expressions.Reset(0.4f); }));
            RegisterAction(new JSONStorableAction("Reload config files", ReloadConfigFiles));
        }

        private void CreateControllers()
        {
            _morphs = new MorphHelper(containingAtom);
            _speech = new SpeechPlayer(this, containingAtom);
            _speech.OnStarted = OnSpeechStarted;
            _speech.OnEnded = OnSpeechEnded;
            _speech.OnError = (id, message) => Send(Protocol.NewError(id, "audio_failed", message));
            _speech.Volume = _volumeJson.val;

            _expressions = new ExpressionController(_morphs);
            _breathing = new BreathingController(_morphs, _breathMorphJson.val);
            _idle = new IdleController(containingAtom);
            _poses = new PoseController(containingAtom, _idle);
            _router = new CommandRouter(Send, _speech, _expressions, _poses, _idle, _breathing);

            _idle.Enabled = _idleJson.val;
            _idle.Intensity = _idleIntensityJson.val;
            _breathing.Enabled = _breathingJson.val;
            _breathing.Rate = _breathRateJson.val;
            _breathing.Depth = _breathDepthJson.val;
            Log.Verbose = _verboseJson.val;
            ReloadConfigFiles();
        }

        private void CreateUI()
        {
            Header("<b>AIBody Person</b> (needs the AIBody Session plugin)", false);
            UIDynamicTextField status = CreateTextField(_statusJson);
            status.height = 220f;
            Header("<b>Speech output</b>", false);
            CreateSlider(_volumeJson);
            CreateButton("Stop speaking").button.onClick.AddListener(StopSpeaking);
            CreateToggle(_verboseJson);

            Header("<b>Body</b>", true);
            CreateToggle(_idleJson, true);
            CreateSlider(_idleIntensityJson, true);
            CreateToggle(_breathingJson, true);
            CreateSlider(_breathRateJson, true);
            CreateSlider(_breathDepthJson, true);
            CreateTextInput(_breathMorphJson, true);
            CreateButton("Reload expressions / gestures", true).button.onClick.AddListener(ReloadConfigFiles);
        }

        private void Header(string text, bool rightSide)
        {
            UIDynamicTextField field = CreateTextField(new JSONStorableString("header " + text, text), rightSide);
            field.height = 40f;
        }

        // TODO(verify): editable text field pattern (InputField bound via storable.inputField).
        private void CreateTextInput(JSONStorableString storable, bool rightSide)
        {
            UIDynamicTextField field = CreateTextField(storable, rightSide);
            field.height = 40f;
            InputField input = field.gameObject.AddComponent<InputField>();
            input.textComponent = field.UItext;
            input.lineType = InputField.LineType.SingleLine;
            storable.inputField = input;
        }

        private void ReloadConfigFiles()
        {
            if (_expressions != null) _expressions.LoadPresetFile(DataRoot + "/expressions.json");
            if (_poses != null) _poses.LoadGestureFile(DataRoot + "/gestures.json");
        }

        private void StopSpeaking()
        {
            if (_speech != null) _speech.StopAll("stopped");
        }

        // ---------------------------------------------------------------- bridge

        // Called synchronously when the Session plugin writes a command into "AIBody Inbox".
        private void OnInbox(string value)
        {
            if (_handlingInbox || string.IsNullOrEmpty(value)) return;
            _handlingInbox = true;
            try
            {
                _lastCommandAge = 0f;
                Log.Debug("<- " + value);
                if (_router != null) _router.HandlePayload(value);
            }
            catch (Exception e)
            {
                Log.Error("Inbox command failed", e);
            }
            finally
            {
                // Reset so the next (possibly identical) message fires the callback again and
                // nothing stale is saved with the scene.
                _inboxJson.val = "";
                _handlingInbox = false;
            }
        }

        /// <summary>Appends an event to the outbox JSON array the Session plugin drains.</summary>
        private void Send(JSONClass evt)
        {
            if (_outboxJson == null || evt == null) return;
            evt["atom"] = containingAtom.uid;
            JSONArray arr = null;
            if (!string.IsNullOrEmpty(_outboxJson.val)) arr = JSON.Parse(_outboxJson.val) as JSONArray;
            if (arr == null) arr = new JSONArray();
            // No Session plugin draining? Keep only the newest events.
            while (arr.Count >= Protocol.MaxOutboxEvents) arr.Remove(0);
            arr.Add(evt);
            _outboxJson.val = arr.ToString();
        }

        private void SendStatus()
        {
            JSONClass s = Protocol.NewEvent(Protocol.EvtPersonStatus);
            s["plugin_version"] = PluginVersion;
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
            Send(s);
        }

        private void OnSpeechStarted(string id, float duration)
        {
            JSONClass evt = Protocol.NewEvent(Protocol.EvtSpeechStarted);
            evt["utterance_id"] = id ?? "";
            evt["duration"].AsFloat = duration;
            Send(evt);
        }

        private void OnSpeechEnded(string id, string reason)
        {
            JSONClass evt = Protocol.NewEvent(Protocol.EvtSpeechEnded);
            evt["utterance_id"] = id ?? "";
            evt["reason"] = reason;
            evt["queue_length"].AsInt = _speech.QueueLength;
            Send(evt);
        }

        // ---------------------------------------------------------------- frame loop

        private void Update()
        {
            if (!_initialized) return;
            try
            {
                if (_firstUpdate)
                {
                    // Drop events restored from a saved scene.
                    _firstUpdate = false;
                    _outboxJson.val = "";
                    SendStatus();
                }
                float dt = Time.deltaTime;
                _lastCommandAge += dt;
                // The Session plugin empties the outbox every frame; if it stays full, it is missing.
                _undrainedAge = string.IsNullOrEmpty(_outboxJson.val) ? 0f : _undrainedAge + dt;
                _speech.Update(dt);
                bool speaking = _speech.IsSpeaking;
                _expressions.Update(dt);
                _breathing.Update(dt, speaking);
                string finishedGesture = _idle.Update(dt, speaking, _breathing.Cycle, _breathing.CurrentDepth);
                if (finishedGesture != null)
                {
                    JSONClass done = Protocol.NewEvent(Protocol.EvtGestureDone);
                    done["name"] = finishedGesture;
                    Send(done);
                }

                _statusTimer += dt;
                if (_statusTimer >= StatusInterval)
                {
                    _statusTimer = 0f;
                    SendStatus();
                }
                _uiTimer += dt;
                if (_uiTimer > 0.5f)
                {
                    _uiTimer = 0f;
                    UpdateStatusText();
                }
            }
            catch (Exception e)
            {
                Log.Error("Update failed; disabling the plugin", e);
                enabled = false;
            }
        }

        private void UpdateStatusText()
        {
            bool sessionSeen = _undrainedAge < 3f;
            string text = "AIBody Person " + PluginVersion + " on '" + containingAtom.uid + "'\n";
            text += "Session plugin: " + (sessionSeen ? "draining events" : "NOT FOUND (add AIBodySession in Session Plugins)") + "\n";
            text += "Last command: " + (_lastCommandAge < 999f ? _lastCommandAge.ToString("0") + "s ago" : "none yet") + "\n";
            text += "Speaking: " + (_speech.IsSpeaking ? "yes" : "no") + ", queued: " + _speech.QueueLength + "\n";
            text += "Expression: " + _expressions.Current + "\n";
            text += "Audio: " + (_speech.Available ? "ok" : "missing HeadAudioSource") + "\n";
            text += "Morphs: " + (_morphs.Available ? "ok" : "unavailable") + "\n";
            text += "Breath morph: " + (_morphs.Find(_breathing.MorphName) != null ? _breathing.MorphName : "not found") + "\n";
            _statusJson.val = text;
        }

        // ---------------------------------------------------------------- teardown

        private void OnDisable()
        {
            if (!_initialized) return;
            try
            {
                if (_speech != null) _speech.StopAll("stopped");
                if (_expressions != null) _expressions.RestoreNow();
                if (_breathing != null) _breathing.RestoreNow();
                if (_idle != null) _idle.RestoreNow();
            }
            catch (Exception e)
            {
                Log.Error("OnDisable cleanup failed", e);
            }
        }

        private void OnDestroy()
        {
            OnDisable();
        }
    }
}
