// AIBody - gives an AI a virtual body in Virt-A-Mate 1.22.
//
// This MVRScript is the thin "body" side: it receives commands from an external companion
// app (speech audio to play, expressions, gestures, poses, triggers) and reports events back
// (ready, speech_started, speech_ended, errors). Microphone capture, voice activity detection,
// speech-to-text, the language model and text-to-speech all live in the companion, because
// the VaM plugin sandbox does not allow native libraries, processes or raw sockets.
//
// Add to a Person atom: Plugins tab -> Add Plugin -> Custom/Scripts/d0n/AIBody/AIBody.cslist
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;
using UnityEngine.UI;

namespace AIBody
{
    public class AIBodyPlugin : MVRScript
    {
        public const string PluginVersion = "0.1.0";
        public const string DataRoot = "Saves/PluginData/AIBody";

        private const string TransportFile = "File (no network needed)";
        private const string TransportHttp = "HTTP (needs network access)";

        // Persisted settings (saved with the scene).
        private JSONStorableBool _activeJson;
        private JSONStorableString _channelJson;
        private JSONStorableStringChooser _transportJson;
        private JSONStorableString _httpUrlJson;
        private JSONStorableFloat _pollIntervalJson;
        private JSONStorableBool _idleJson;
        private JSONStorableFloat _idleIntensityJson;
        private JSONStorableBool _breathingJson;
        private JSONStorableFloat _breathRateJson;
        private JSONStorableFloat _breathDepthJson;
        private JSONStorableString _breathMorphJson;
        private JSONStorableBool _verboseJson;

        // Read-only status for the UI.
        private JSONStorableString _statusJson;

        private ITransport _transport;
        private MorphHelper _morphs;
        private AudioController _audio;
        private ExpressionController _expressions;
        private BreathingController _breathing;
        private IdleController _idle;
        private PoseController _poses;
        private StateReporter _state;
        private CommandRouter _router;

        private bool _initialized;
        private float _heartbeatTimer;
        private float _statusTimer;
        private const float HeartbeatInterval = 2f;

        public override void Init()
        {
            try
            {
                if (containingAtom == null || containingAtom.type != "Person")
                {
                    Log.Error("Please add this plugin to a Person atom.");
                    return;
                }

                CreateStorables();
                CreateControllers();
                CreateUI();
                _initialized = true;
                Restart();
            }
            catch (Exception e)
            {
                Log.Error("Init failed", e);
            }
        }

        // ---------------------------------------------------------------- setup

        private void CreateStorables()
        {
            _activeJson = new JSONStorableBool("Active", true, (bool v) => Restart());
            RegisterBool(_activeJson);

            // Channel = sub folder / HTTP channel name. Defaults to the atom uid so several
            // Person atoms can each have their own AI.
            _channelJson = new JSONStorableString("Channel", containingAtom.uid, (string v) => Restart());
            RegisterString(_channelJson);

            _transportJson = new JSONStorableStringChooser("Transport",
                new List<string> { TransportFile, TransportHttp }, TransportFile, "Transport",
                (string v) => Restart());
            RegisterStringChooser(_transportJson);

            _httpUrlJson = new JSONStorableString("Companion URL", "http://127.0.0.1:8765", (string v) => Restart());
            RegisterString(_httpUrlJson);

            _pollIntervalJson = new JSONStorableFloat("Poll interval (s)", 0.1f, (float v) => Restart(), 0.02f, 2f);
            RegisterFloat(_pollIntervalJson);

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

            // Actions usable from scene triggers / buttons.
            RegisterAction(new JSONStorableAction("Reconnect", Restart));
            RegisterAction(new JSONStorableAction("Stop speaking", () => { if (_state != null) _state.NotifyStopRequested(); if (_audio != null) _audio.Stop(); }));
            RegisterAction(new JSONStorableAction("Reset expression", () => { if (_expressions != null) _expressions.Reset(0.4f); }));
            RegisterAction(new JSONStorableAction("Reload config files", ReloadConfigFiles));
            RegisterAction(new JSONStorableAction("Send ready event", SendReady));
        }

        private void CreateControllers()
        {
            _morphs = new MorphHelper(containingAtom);
            _audio = new AudioController(this, containingAtom);
            _expressions = new ExpressionController(_morphs);
            _breathing = new BreathingController(_morphs, _breathMorphJson.val);
            _idle = new IdleController(containingAtom);
            _poses = new PoseController(containingAtom, _idle);
            _state = new StateReporter(_audio, Send);
            _router = new CommandRouter(Send, _audio, _expressions, _poses, _idle, _breathing, _state, BuildStatus);

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
            CreateToggle(_activeJson);
            CreatePopup(_transportJson);
            CreateTextInput(_channelJson);
            CreateTextInput(_httpUrlJson);
            CreateSlider(_pollIntervalJson);
            CreateButton("Reconnect").button.onClick.AddListener(Restart);
            CreateButton("Reload expressions / gestures").button.onClick.AddListener(ReloadConfigFiles);
            CreateToggle(_verboseJson);

            UIDynamicTextField status = CreateTextField(_statusJson, true);
            status.height = 300f;
            CreateToggle(_idleJson, true);
            CreateSlider(_idleIntensityJson, true);
            CreateToggle(_breathingJson, true);
            CreateSlider(_breathRateJson, true);
            CreateSlider(_breathDepthJson, true);
            CreateTextInput(_breathMorphJson, true);
        }

        // VaM has no one-line text input helper; a text field with an InputField attached
        // and bound through storable.inputField is the common pattern in community plugins.
        // TODO(verify): confirm in VaM 1.22 that editing commits the value (callback fires).
        private void CreateTextInput(JSONStorableString storable, bool rightSide = false)
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

        // ---------------------------------------------------------------- transport

        private string ChannelDir
        {
            get { return DataRoot + "/" + SanitizeChannel(_channelJson.val); }
        }

        private static string SanitizeChannel(string channel)
        {
            if (string.IsNullOrEmpty(channel)) return "default";
            char[] chars = channel.ToCharArray();
            for (int i = 0; i < chars.Length; i++)
            {
                char c = chars[i];
                if (!(char.IsLetterOrDigit(c) || c == '-' || c == '_')) chars[i] = '_';
            }
            return new string(chars);
        }

        private void Restart()
        {
            if (!_initialized) return;
            StopTransport();
            if (!_activeJson.val)
            {
                SetStatus("Inactive");
                return;
            }

            string channel = SanitizeChannel(_channelJson.val);
            if (_transportJson.val == TransportHttp)
            {
                _transport = new HttpTransport(this, _httpUrlJson.val, channel, _pollIntervalJson.val, OnPayload);
            }
            else
            {
                _transport = new FileTransport(ChannelDir, _pollIntervalJson.val, OnPayload);
            }
            _transport.Start();
            Log.Info("Started " + _transport.Name + " transport on channel '" + channel + "'");
            SendReady();
        }

        private void StopTransport()
        {
            if (_transport == null) return;
            JSONClass bye = Protocol.NewEvent("shutdown");
            _transport.Send(bye);
            _transport.Stop();
            _transport = null;
        }

        private void OnPayload(string payload)
        {
            Log.Debug("<- " + payload);
            if (_router != null) _router.HandlePayload(payload);
        }

        private void Send(JSONClass evt)
        {
            if (_transport == null) return;
            Log.Debug("-> " + evt.ToString());
            _transport.Send(evt);
        }

        private void SendReady()
        {
            JSONClass ready = BuildStatus();
            ready["type"] = Protocol.EvtReady;
            Send(ready);
        }

        private JSONClass BuildStatus()
        {
            JSONClass s = Protocol.NewEvent(Protocol.EvtHeartbeat);
            s["plugin_version"] = PluginVersion;
            s["protocol"].AsInt = Protocol.Version;
            s["atom"] = containingAtom.uid;
            s["channel"] = SanitizeChannel(_channelJson.val);
            s["transport"] = _transport != null ? _transport.Name : "none";
            s["speaking"].AsBool = _state != null && _state.IsSpeaking;
            s["expression"] = _expressions != null ? _expressions.Current : "";
            s["audio_dir"] = ChannelDir + "/audio";

            JSONArray expressions = new JSONArray();
            if (_expressions != null) foreach (string n in _expressions.PresetNames) expressions.Add(new JSONData(n));
            s["expressions"] = expressions;
            JSONArray gestures = new JSONArray();
            if (_poses != null) foreach (string n in _poses.GestureNames) gestures.Add(new JSONData(n));
            gestures.Add(new JSONData("nod"));
            gestures.Add(new JSONData("shake"));
            gestures.Add(new JSONData("tilt"));
            s["gestures"] = gestures;
            return s;
        }

        // ---------------------------------------------------------------- frame loop

        private void Update()
        {
            if (!_initialized) return;
            try
            {
                float dt = Time.deltaTime;
                if (_transport != null)
                {
                    _transport.Tick(dt);
                    _heartbeatTimer += dt;
                    if (_heartbeatTimer >= HeartbeatInterval)
                    {
                        _heartbeatTimer = 0f;
                        Send(BuildStatus());
                    }
                }

                _state.Update(dt);
                bool speaking = _state.IsSpeaking;
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
                if (_statusTimer > 0.5f)
                {
                    _statusTimer = 0f;
                    UpdateStatusText();
                }
            }
            catch (Exception e)
            {
                Log.Error("Update failed; deactivating", e);
                _activeJson.val = false;
            }
        }

        private void UpdateStatusText()
        {
            string text = "AIBody " + PluginVersion + "\n";
            if (_transport == null) text += "Transport: off\n";
            else
            {
                text += "Transport: " + _transport.Name + (_transport.IsConnected ? " (ok)" : " (waiting)") + "\n";
                if (!string.IsNullOrEmpty(_transport.LastError)) text += "Last error: " + _transport.LastError + "\n";
            }
            text += "Folder: " + ChannelDir + "\n";
            text += "Speaking: " + (_state.IsSpeaking ? "yes" : "no") + "\n";
            text += "Expression: " + _expressions.Current + "\n";
            text += "Audio: " + (_audio.Available ? "ok" : "missing HeadAudioSource") + "\n";
            text += "Morphs: " + (_morphs.Available ? "ok" : "unavailable") + "\n";
            text += "Breath morph: " + (_morphs.Find(_breathing.MorphName) != null ? _breathing.MorphName : "not found") + "\n";
            SetStatus(text);
        }

        private void SetStatus(string text)
        {
            if (_statusJson != null) _statusJson.val = text;
        }

        // ---------------------------------------------------------------- teardown

        private void OnDisable()
        {
            if (!_initialized) return;
            try
            {
                StopTransport();
                if (_audio != null) _audio.Stop();
                if (_expressions != null) _expressions.RestoreNow();
                if (_breathing != null) _breathing.RestoreNow();
                if (_idle != null) _idle.RestoreNow();
            }
            catch (Exception e)
            {
                Log.Error("OnDisable cleanup failed", e);
            }
        }

        private void OnEnable()
        {
            // Resume the transport when the plugin is toggled back on (Init already ran).
            if (_initialized && _transport == null && _activeJson != null && _activeJson.val) Restart();
        }

        private void OnDestroy()
        {
            StopTransport();
            OnDisable();
        }
    }
}
