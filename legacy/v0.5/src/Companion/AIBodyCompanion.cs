// AIBody Companion plugin - the AI side: the body the AI drives (Virt-A-Mate 1.22).
//
// Add it on the AI character's Person atom: Plugins tab -> Add Plugin ->
//   AddonPackages > d0n.AIBody.<n>:/Custom/Scripts/d0n/AIBody/Companion/AIBodyCompanion.cslist
//   (loose-file install: Custom/Scripts/d0n/AIBody/Companion/AIBodyCompanion.cslist)
// Needs the AIBody Client plugin in the scene (it holds the link to the companion app).
// Not to be confused with the companion app (the external Python program in companion/).
//
// This plugin does no I/O of its own. The Client plugin finds it by scanning the scene's atoms
// and talks to it through string params (see Protocol.CompanionInboxParam):
//   - commands (speak, expression, gesture, pose, trigger, idle, breathing, ...) arrive one at a
//     time in "AIBody Companion Inbox". Only commands marked as coming from a Client plugin
//     ("via":"aibody_client") are accepted, and only from one Client atom at a time.
//   - events (speech_started/ended, errors, companion_status, ...) are appended to
//     "AIBody Companion Outbox"
// Per-character settings (volume, idle, breathing, ...) are saved with the Person atom.
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;
using UnityEngine.UI;
using AIBodyShared;

namespace AIBodyCompanion
{
    public class AIBodyCompanionPlugin : MVRScript
    {
        public const string PluginVersion = "0.5.0";
        public const string DataRoot = "Saves/PluginData/AIBody";
        private const float StatusInterval = 2f;

        // Bridge to the Client plugin.
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
        private const float ClientLockSeconds = 10f;
        private string _clientUid;   // atom of the Client plugin that currently drives this body
        private float _clientAge = 999f;

        public override void Init()
        {
            try
            {
                Log.Prefix = "AIBody Companion: ";
                if (containingAtom == null || containingAtom.type != "Person")
                {
                    Log.Error("Add this plugin to the AI character's Person atom (the AIBody Client plugin can go on any atom).");
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
            _inboxJson = new JSONStorableString(Protocol.CompanionInboxParam, "", OnInbox);
            RegisterString(_inboxJson);
            _outboxJson = new JSONStorableString(Protocol.CompanionOutboxParam, "");
            RegisterString(_outboxJson);
            _versionJson = new JSONStorableString(Protocol.CompanionVersionParam, PluginVersion);
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
            Header("<b>AIBody Companion</b> (the AI's body; needs the AIBody Client plugin)", false);
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

        // Called synchronously when the Client plugin writes a command into the Inbox.
        private void OnInbox(string value)
        {
            if (_handlingInbox || string.IsNullOrEmpty(value)) return;
            _handlingInbox = true;
            try
            {
                _lastCommandAge = 0f;
                Log.Debug("<- " + value);
                if (_router != null) HandleInbox(value);
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

        private void HandleInbox(string value)
        {
            List<JSONClass> messages;
            try
            {
                messages = Protocol.ParseMessages(value);
            }
            catch (Exception e)
            {
                Send(Protocol.NewError(null, "bad_json", e.Message));
                return;
            }
            for (int i = 0; i < messages.Count; i++)
            {
                if (!AcceptSender(messages[i])) continue;
                _router.Handle(messages[i]);
            }
        }

        /// <summary>
        /// Commands are accepted only from an AIBody Client plugin ("via":"aibody_client" plus its atom
        /// uid in "client"), and only from one Client at a time: another Client is refused until the
        /// current one has been silent for ClientLockSeconds. This keeps triggers, other plugins or a
        /// second Client from driving the body by accident (not a security boundary: any plugin can
        /// write these params).
        /// </summary>
        private bool AcceptSender(JSONClass msg)
        {
            string id = Protocol.GetString(msg, "id", "");
            string via = Protocol.GetString(msg, "via", "");
            string client = Protocol.GetString(msg, "client", "");
            if (via != Protocol.ViaClient || client.Length == 0)
            {
                Log.Error("Refused a command that did not come from an AIBody Client plugin");
                Send(Protocol.NewError(id, Protocol.ErrNotFromClient, "Commands must come from the AIBody Client plugin"));
                return false;
            }
            if (_clientUid != null && client != _clientUid && _clientAge < ClientLockSeconds)
            {
                Log.Error("Refused a command from Client on '" + client + "' (Client on '" + _clientUid + "' is active)");
                Send(Protocol.NewError(id, Protocol.ErrClientConflict, "Another AIBody Client ('" + _clientUid
                    + "') is driving this Companion; remove one Client plugin"));
                return false;
            }
            _clientUid = client;
            _clientAge = 0f;
            return true;
        }

        /// <summary>Appends an event to the outbox JSON array the Client plugin drains.</summary>
        private void Send(JSONClass evt)
        {
            if (_outboxJson == null || evt == null) return;
            evt["atom"] = containingAtom.uid;
            JSONArray arr = null;
            if (!string.IsNullOrEmpty(_outboxJson.val)) arr = JSON.Parse(_outboxJson.val) as JSONArray;
            if (arr == null) arr = new JSONArray();
            // No Client plugin draining? Keep only the newest events.
            while (arr.Count >= Protocol.MaxOutboxEvents) arr.Remove(0);
            arr.Add(evt);
            _outboxJson.val = arr.ToString();
        }

        private void SendStatus()
        {
            JSONClass s = Protocol.NewEvent(Protocol.EvtCompanionStatus);
            s["plugin_version"] = PluginVersion;
            s["client"] = _clientUid ?? "";
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
                _clientAge += dt;
                // The Client plugin empties the outbox every frame; if it stays full, it is missing.
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
            bool clientSeen = _undrainedAge < 3f;
            string text = "AIBody Companion " + PluginVersion + " on '" + containingAtom.uid + "'\n";
            text += "Client plugin: " + (clientSeen ? "draining events" : "NOT FOUND (add AIBodyClient.cslist to an atom)")
                + (_clientUid != null ? ", driven by '" + _clientUid + "'" : "") + "\n";
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
