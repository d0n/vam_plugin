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
        public const string PluginVersion = "0.2.0";
        public const string DataRoot = "Saves/PluginData/AIBody";

        private const string TransportAuto = "Auto (HTTP, file fallback)";
        private const string TransportHttp = "HTTP only";
        private const string TransportFile = "File only (no network)";

        // Persisted settings (saved with the scene).
        private JSONStorableBool _activeJson;
        private JSONStorableStringChooser _transportJson;
        private JSONStorableString _hostJson;
        private JSONStorableString _portJson;
        private JSONStorableString _channelJson;
        private JSONStorableFloat _filePollJson;
        private JSONStorableFloat _volumeJson;
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
        private SpeechPlayer _speech;
        private ExpressionController _expressions;
        private BreathingController _breathing;
        private IdleController _idle;
        private PoseController _poses;
        private MicConfig _mic;
        private CommandRouter _router;

        private bool _initialized;
        private int _seenEpoch;
        private bool _wasConnected;
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

            _transportJson = new JSONStorableStringChooser("Transport",
                new List<string> { TransportAuto, TransportHttp, TransportFile }, TransportAuto, "Transport",
                (string v) => Restart());
            RegisterStringChooser(_transportJson);

            _hostJson = new JSONStorableString("Companion host", "127.0.0.1", (string v) => Restart());
            RegisterString(_hostJson);
            _portJson = new JSONStorableString("Companion port", "8765", (string v) => Restart());
            RegisterString(_portJson);

            // Channel = sub folder / HTTP channel name. Defaults to the atom uid so several
            // Person atoms can each have their own AI.
            _channelJson = new JSONStorableString("Channel", containingAtom.uid, (string v) => Restart());
            RegisterString(_channelJson);

            _filePollJson = new JSONStorableFloat("File poll interval (s)", 0.1f, (float v) => Restart(), 0.02f, 2f);
            RegisterFloat(_filePollJson);

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

            _mic = new MicConfig(this, Send);
            _mic.CreateStorables();

            // Actions usable from scene triggers / buttons.
            RegisterAction(new JSONStorableAction("Reconnect", Restart));
            RegisterAction(new JSONStorableAction("Stop speaking", StopSpeaking));
            RegisterAction(new JSONStorableAction("Reset expression", () => { if (_expressions != null) _expressions.Reset(0.4f); }));
            RegisterAction(new JSONStorableAction("Reload config files", ReloadConfigFiles));
            RegisterAction(new JSONStorableAction("Send ready event", SendReady));
        }

        private void CreateControllers()
        {
            _morphs = new MorphHelper(containingAtom);
            _speech = new SpeechPlayer(this, containingAtom);
            _speech.HttpBaseUrl = () => _transport != null ? _transport.HttpBaseUrl : null;
            _speech.OnStarted = OnSpeechStarted;
            _speech.OnEnded = OnSpeechEnded;
            _speech.OnError = (id, message) => Send(Protocol.NewError(id, "audio_failed", message));
            _speech.Volume = _volumeJson.val;

            _expressions = new ExpressionController(_morphs);
            _breathing = new BreathingController(_morphs, _breathMorphJson.val);
            _idle = new IdleController(containingAtom);
            _poses = new PoseController(containingAtom, _idle);
            _router = new CommandRouter(Send, _speech, _expressions, _poses, _idle, _breathing, _mic, BuildStatus);

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
            // Left column: connection, speech output, body.
            Header("<b>Connection</b>", false);
            CreateToggle(_activeJson);
            CreatePopup(_transportJson);
            CreateTextInput(_hostJson);
            CreateTextInput(_portJson);
            CreateTextInput(_channelJson);
            CreateButton("Reconnect").button.onClick.AddListener(Restart);
            UIDynamicTextField status = CreateTextField(_statusJson);
            status.height = 260f;

            Header("<b>Speech output</b>", false);
            CreateSlider(_volumeJson);
            CreateButton("Stop speaking").button.onClick.AddListener(StopSpeaking);

            Header("<b>Body</b>", false);
            CreateToggle(_idleJson);
            CreateSlider(_idleIntensityJson);
            CreateToggle(_breathingJson);
            CreateSlider(_breathRateJson);
            CreateSlider(_breathDepthJson);
            CreateTextInput(_breathMorphJson);
            CreateButton("Reload expressions / gestures").button.onClick.AddListener(ReloadConfigFiles);

            Header("<b>Advanced</b>", false);
            CreateSlider(_filePollJson);
            CreateToggle(_verboseJson);

            // Right column: microphone settings.
            _mic.CreateUI(true);
        }

        private void Header(string text, bool rightSide)
        {
            UIDynamicTextField field = CreateTextField(new JSONStorableString("header " + text, text), rightSide);
            field.height = 40f;
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

        private void StopSpeaking()
        {
            if (_speech != null) _speech.StopAll("stopped");
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

        private int Port
        {
            get
            {
                int port;
                if (int.TryParse(_portJson.val, out port) && port > 0 && port < 65536) return port;
                Log.Error("Invalid companion port '" + _portJson.val + "', using 8765");
                return 8765;
            }
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
            string mode = _transportJson.val;
            if (mode == TransportFile)
            {
                _transport = new FileTransport(ChannelDir, _filePollJson.val, OnPayload);
            }
            else
            {
                HttpTransport http = new HttpTransport(this, _hostJson.val, Port, channel, PluginVersion, OnPayload);
                if (mode == TransportHttp) _transport = http;
                else _transport = new AutoTransport(http, new FileTransport(ChannelDir, _filePollJson.val, OnPayload));
            }
            _seenEpoch = 0;
            _wasConnected = false;
            _transport.Start();
            Log.Info("Started " + _transport.Name + " transport on channel '" + channel + "'");
        }

        private void StopTransport()
        {
            if (_transport == null) return;
            _transport.Send(Protocol.NewEvent(Protocol.EvtShutdown));
            _transport.Stop();
            _transport = null;
            if (_mic != null) _mic.OnDisconnected();
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

        private JSONClass BuildStatus()
        {
            JSONClass s = Protocol.NewEvent(Protocol.EvtHeartbeat);
            s["plugin_version"] = PluginVersion;
            s["protocol"].AsInt = Protocol.Version;
            s["atom"] = containingAtom.uid;
            s["channel"] = SanitizeChannel(_channelJson.val);
            s["transport"] = _transport != null ? _transport.Name : "none";
            AutoTransport auto = _transport as AutoTransport;
            s["link"] = auto != null ? auto.ActiveLink : (_transport != null ? _transport.Name : "none");
            s["speaking"].AsBool = _speech != null && _speech.IsSpeaking;
            s["speech_queue"].AsInt = _speech != null ? _speech.QueueLength : 0;
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
                bool connected = false;
                if (_transport != null)
                {
                    _transport.Tick(dt);
                    connected = _transport.IsConnected;

                    // (Re)connected, companion restarted, or switched between HTTP and file.
                    if (connected && _transport.ConnectionEpoch != _seenEpoch)
                    {
                        _seenEpoch = _transport.ConnectionEpoch;
                        SendReady();
                        _mic.OnConnected();
                        _heartbeatTimer = 0f;
                    }
                    if (!connected && _wasConnected) _mic.OnDisconnected();
                    _wasConnected = connected;

                    _heartbeatTimer += dt;
                    if (connected && _heartbeatTimer >= HeartbeatInterval)
                    {
                        _heartbeatTimer = 0f;
                        Send(BuildStatus());
                    }
                }

                _speech.Update(dt);
                _mic.Update(dt, connected);
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
                text += "Transport: " + _transport.Name + (_transport.IsConnected ? " (connected)" : " (waiting)") + "\n";
                text += "State: " + _transport.State + "\n";
                if (!string.IsNullOrEmpty(_transport.LastError)) text += "Last error: " + _transport.LastError + "\n";
            }
            text += "Folder: " + ChannelDir + "\n";
            text += "Speaking: " + (_speech.IsSpeaking ? "yes" : "no") + ", queued: " + _speech.QueueLength + "\n";
            text += "Expression: " + _expressions.Current + "\n";
            text += "Audio: " + (_speech.Available ? "ok" : "missing HeadAudioSource") + "\n";
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

        private void OnEnable()
        {
            // Resume the transport when the plugin is toggled back on (Init already ran).
            if (_initialized && _transport == null && _activeJson != null && _activeJson.val) Restart();
        }

        private void OnDestroy()
        {
            OnDisable();
        }
    }
}
