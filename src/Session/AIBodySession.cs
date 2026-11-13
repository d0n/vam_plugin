// AIBody Session plugin - the AI's connection to the companion app (Virt-A-Mate 1.22).
//
// Load it once via Main UI > Session Plugins > Add Plugin ->
//   AddonPackages > d0n.AIBodySession.<n>:/Custom/Scripts/d0n/AIBody/AIBodySession.cslist
//   (loose-file install: Custom/Scripts/d0n/AIBody/AIBodySession.cslist)
// ("Set Current As User Defaults" there makes it load with every VaM start). Session plugins
// survive scene changes and are not attached to a Person, so nothing here uses containingAtom.
//
// Responsibilities:
//   - companion connection (file transport in the shared folder; HTTP only in the optional
//     AIBODY_HTTP build), channel, connection status
//   - microphone menu (settings, devices, push-to-talk, level meter) and engine selection,
//     sent to the companion as "config"
//   - routing: body commands from the companion go to the AIBody Person plugin on the target atom
//     ("atom" field, else the default character), Person events go back to the companion.
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;
using UnityEngine.UI;

namespace AIBody
{
    public class AIBodySessionPlugin : MVRScript
    {
        public const string PluginVersion = "0.3.0";
        public const string DataRoot = "Saves/PluginData/AIBody";

        private const string TransportFile = "File (shared folder)";
#if AIBODY_HTTP
        private const string TransportAuto = "Auto (HTTP, file fallback)";
        private const string TransportHttp = "HTTP only";
#endif
        private const string FirstFound = "(first Person found)";
        private const float HeartbeatInterval = 2f;
        private const float CompanionTimeout = 6f;

        private JSONStorableBool _activeJson;
        private JSONStorableStringChooser _transportJson;
        private JSONStorableString _channelJson;
        private JSONStorableFloat _filePollJson;
#if AIBODY_HTTP
        private JSONStorableString _hostJson;
        private JSONStorableString _portJson;
#endif
        private JSONStorableStringChooser _defaultPersonJson;
        private JSONStorableStringChooser _sttJson;
        private JSONStorableStringChooser _llmJson;
        private JSONStorableStringChooser _ttsJson;
        private JSONStorableBool _verboseJson;
        private JSONStorableString _statusJson;

        private ITransport _transport;
        private PersonRegistry _persons;
        private MicConfig _mic;

        private bool _initialized;
        private int _seenEpoch;
        private float _heartbeatTimer;
        private float _uiTimer;
        private float _companionAge = 999f;
        private string _companionSession;
        private string _companionVersion = "";

        public override void Init()
        {
            try
            {
                Log.Prefix = "AIBody Session: ";
                _persons = new PersonRegistry();
                CreateStorables();
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

            List<string> transports = new List<string> { TransportFile };
#if AIBODY_HTTP
            transports.Insert(0, TransportAuto);
            transports.Add(TransportHttp);
#endif
            _transportJson = new JSONStorableStringChooser("Transport", transports, transports[0], "Transport", (string v) => Restart());
            RegisterStringChooser(_transportJson);

            // Channel = sub folder below Saves/PluginData/AIBody; must match the companion's --channel.
            _channelJson = new JSONStorableString("Channel", "default", (string v) => Restart());
            RegisterString(_channelJson);
            _filePollJson = new JSONStorableFloat("File poll interval (s)", 0.1f, (float v) => Restart(), 0.02f, 2f);
            RegisterFloat(_filePollJson);
#if AIBODY_HTTP
            _hostJson = new JSONStorableString("Companion host", "127.0.0.1", (string v) => Restart());
            RegisterString(_hostJson);
            _portJson = new JSONStorableString("Companion port", "8765", (string v) => Restart());
            RegisterString(_portJson);
#endif

            _defaultPersonJson = new JSONStorableStringChooser("Default character", new List<string> { FirstFound },
                FirstFound, "Default character", (string v) => { });
            RegisterStringChooser(_defaultPersonJson);

            // Engine choices are refreshed from the companion's companion_heartbeat.
            _sttJson = Engine("Speech-to-text", "null");
            _llmJson = Engine("Language model", "echo");
            _ttsJson = Engine("Text-to-speech", "tone");

            _verboseJson = new JSONStorableBool("Verbose log", false, (bool v) => Log.Verbose = v);
            RegisterBool(_verboseJson);
            _statusJson = new JSONStorableString("Status", "Starting...");

            _mic = new MicConfig(this, Send);
            _mic.CreateStorables();
            _mic.DecorateConfig = AddEngines;

            RegisterAction(new JSONStorableAction("Reconnect", Restart));
            RegisterAction(new JSONStorableAction("Rescan characters", () => _persons.ForceScan()));
            RegisterAction(new JSONStorableAction("Stop all speech", StopAllSpeech));
        }

        private JSONStorableStringChooser Engine(string name, string defaultValue)
        {
            JSONStorableStringChooser c = new JSONStorableStringChooser(name, new List<string> { defaultValue },
                defaultValue, name, (string v) => { if (_mic != null) _mic.MarkDirty(); });
            RegisterStringChooser(c);
            return c;
        }

        private void AddEngines(JSONClass configEvent)
        {
            JSONClass engines = new JSONClass();
            engines["stt"] = _sttJson.val;
            engines["llm"] = _llmJson.val;
            engines["tts"] = _ttsJson.val;
            configEvent["engines"] = engines;
        }

        private void CreateUI()
        {
            Header("<b>Connection</b>", false);
            CreateToggle(_activeJson);
            CreatePopup(_transportJson);
            CreateTextInput(_channelJson, false);
#if AIBODY_HTTP
            CreateTextInput(_hostJson, false);
            CreateTextInput(_portJson, false);
#endif
            CreateButton("Reconnect").button.onClick.AddListener(Restart);
            UIDynamicTextField status = CreateTextField(_statusJson);
            status.height = 300f;

            Header("<b>Characters</b>", false);
            CreatePopup(_defaultPersonJson);
            CreateButton("Rescan characters").button.onClick.AddListener(() => _persons.ForceScan());
            CreateButton("Stop all speech").button.onClick.AddListener(StopAllSpeech);

            Header("<b>Engines</b> (provided by the companion)", false);
            CreatePopup(_sttJson);
            CreatePopup(_llmJson);
            CreatePopup(_ttsJson);

            Header("<b>Advanced</b>", false);
            CreateSlider(_filePollJson);
            CreateToggle(_verboseJson);

            _mic.CreateUI(true);
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

        // ---------------------------------------------------------------- transport

        private string Channel
        {
            get
            {
                string channel = _channelJson.val;
                if (string.IsNullOrEmpty(channel)) return "default";
                char[] chars = channel.ToCharArray();
                for (int i = 0; i < chars.Length; i++)
                {
                    char c = chars[i];
                    if (!(char.IsLetterOrDigit(c) || c == '-' || c == '_')) chars[i] = '_';
                }
                return new string(chars);
            }
        }

        private string ChannelDir { get { return DataRoot + "/" + Channel; } }

        private void Restart()
        {
            if (!_initialized) return;
            StopTransport();
            if (!_activeJson.val)
            {
                _statusJson.val = "Inactive";
                return;
            }
            FileTransport file = new FileTransport(ChannelDir, _filePollJson.val, OnPayload);
            _transport = file;
#if AIBODY_HTTP
            if (_transportJson.val != TransportFile)
            {
                int port;
                if (!int.TryParse(_portJson.val, out port)) port = 8765;
                HttpTransport http = new HttpTransport(this, _hostJson.val, port, Channel, PluginVersion, OnPayload);
                _transport = _transportJson.val == TransportHttp ? (ITransport)http : new AutoTransport(http, file);
            }
#endif
            _seenEpoch = 0;
            _companionSession = null;
            _companionAge = 999f;
            _transport.Start();
            Log.Info("Started " + _transport.Name + " transport on channel '" + Channel + "'");
        }

        private void StopTransport()
        {
            if (_transport == null) return;
            _transport.Send(Protocol.NewEvent(Protocol.EvtShutdown));
            _transport.Stop();
            _transport = null;
            if (_mic != null) _mic.OnDisconnected();
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
            s["role"] = "session";
            s["plugin_version"] = PluginVersion;
            s["protocol"].AsInt = Protocol.Version;
            s["channel"] = Channel;
            s["transport"] = _transport != null ? _transport.Name : "none";
            s["audio_dir"] = ChannelDir + "/audio";
            s["default_atom"] = DefaultAtom ?? "";
            s["persons"] = _persons.ToJson();
            return s;
        }

        private void SendPersons()
        {
            JSONClass evt = Protocol.NewEvent(Protocol.EvtPersons);
            evt["persons"] = _persons.ToJson();
            evt["default_atom"] = DefaultAtom ?? "";
            Send(evt);
        }

        // ---------------------------------------------------------------- routing

        /// <summary>Atom that gets body commands without an explicit "atom" field.</summary>
        private string DefaultAtom
        {
            get
            {
                if (_defaultPersonJson.val != FirstFound && _persons.Get(_defaultPersonJson.val) != null) return _defaultPersonJson.val;
                List<string> uids = _persons.AtomUids;
                return uids.Count > 0 ? uids[0] : null;
            }
        }

        private void OnPayload(string payload)
        {
            Log.Debug("<- " + payload);
            List<JSONClass> messages;
            try
            {
                messages = Protocol.ParseMessages(payload);
            }
            catch (Exception e)
            {
                Send(Protocol.NewError(null, "bad_json", e.Message));
                return;
            }
            for (int i = 0; i < messages.Count; i++)
            {
                try
                {
                    Route(messages[i]);
                }
                catch (Exception e)
                {
                    Log.Error("Handling message failed", e);
                    Send(Protocol.NewError(Protocol.GetString(messages[i], "id", ""), "command_failed", e.Message));
                }
            }
        }

        private void Route(JSONClass msg)
        {
            string type = Protocol.GetString(msg, "type", "");
            string id = Protocol.GetString(msg, "id", "");

            if (Protocol.IsBodyCommand(type))
            {
                string target = Protocol.GetString(msg, "atom", "");
                if (target.Length == 0) target = DefaultAtom;
                if (target == null || !_persons.Deliver(target, msg))
                {
                    JSONClass err = Protocol.NewError(id, "no_person",
                        "No AIBody Person plugin " + (string.IsNullOrEmpty(target) ? "in the scene" : "on atom '" + target + "'"));
                    if (target != null) err["atom"] = target;
                    Send(err);
                }
                return;
            }

            switch (type)
            {
                case Protocol.CmdPing:
                {
                    JSONClass pong = BuildStatus();
                    pong["type"] = Protocol.EvtPong;
                    pong["reply_to"] = id;
                    Send(pong);
                    break;
                }
                case Protocol.CmdCompanionHeartbeat:
                    HandleCompanionHeartbeat(msg);
                    break;
                case Protocol.CmdConfigAck:
                    _mic.HandleConfigAck(msg);
                    break;
                case Protocol.CmdDevices:
                    _mic.HandleDevices(msg);
                    break;
                case Protocol.CmdMicState:
                    _mic.HandleMicState(msg);
                    break;
                case Protocol.CmdMicLevel:
                    _mic.HandleMicLevel(msg);
                    break;
                default:
                    Send(Protocol.NewError(id, "command_failed", "Unknown message type '" + type + "'"));
                    break;
            }
        }

        private void HandleCompanionHeartbeat(JSONClass msg)
        {
            _companionAge = 0f;
            _companionVersion = Protocol.GetString(msg, "version", "");
            string session = Protocol.GetString(msg, "session", "");
            if (session != _companionSession)
            {
                // Companion (re)started: it lost our settings and cleared its folders.
                _companionSession = session;
                Log.Info("Companion " + _companionVersion + " is running (session " + session + ")");
                _seenEpoch = -1; // forces ready + config in Update
            }
            JSONClass available = msg["engines_available"] as JSONClass;
            if (available != null)
            {
                SetChoices(_sttJson, available["stt"] as JSONArray);
                SetChoices(_llmJson, available["llm"] as JSONArray);
                SetChoices(_ttsJson, available["tts"] as JSONArray);
            }
        }

        private static void SetChoices(JSONStorableStringChooser chooser, JSONArray names)
        {
            if (names == null) return;
            List<string> choices = new List<string>();
            for (int i = 0; i < names.Count; i++) choices.Add(names[i].Value);
            if (!choices.Contains(chooser.val)) choices.Add(chooser.val);
            // TODO(verify): JSONStorableStringChooser.choices is settable and refreshes the popup.
            chooser.choices = choices;
        }

        private void StopAllSpeech()
        {
            List<string> uids = _persons.AtomUids;
            for (int i = 0; i < uids.Count; i++)
            {
                JSONClass stop = new JSONClass();
                stop["v"].AsInt = Protocol.Version;
                stop["type"] = Protocol.CmdStopSpeaking;
                stop["id"] = "session-stop-" + DateTime.UtcNow.Ticks;
                _persons.Deliver(uids[i], stop);
            }
        }

        // ---------------------------------------------------------------- frame loop

        private void Update()
        {
            if (!_initialized) return;
            try
            {
                float dt = Time.deltaTime;
                if (_persons.Update(dt))
                {
                    RefreshPersonChoices();
                    SendPersons();
                }
                _persons.DrainOutboxes(Send);

                bool connected = false;
                if (_transport != null)
                {
                    _transport.Tick(dt);
                    connected = _transport.IsConnected;
                    _companionAge += dt;

                    // New connection, folder re-created, or companion restarted.
                    if (connected && _transport.ConnectionEpoch != _seenEpoch)
                    {
                        _seenEpoch = _transport.ConnectionEpoch;
                        SendReady();
                        _mic.OnConnected();
                        _heartbeatTimer = 0f;
                    }
                    _heartbeatTimer += dt;
                    if (connected && _heartbeatTimer >= HeartbeatInterval)
                    {
                        _heartbeatTimer = 0f;
                        Send(BuildStatus());
                    }
                }
                _mic.Update(dt, connected);

                _uiTimer += dt;
                if (_uiTimer > 0.5f)
                {
                    _uiTimer = 0f;
                    UpdateStatusText();
                }
            }
            catch (Exception e)
            {
                Log.Error("Update failed; deactivating", e);
                _activeJson.val = false;
            }
        }

        private void RefreshPersonChoices()
        {
            List<string> choices = new List<string> { FirstFound };
            choices.AddRange(_persons.AtomUids);
            if (!choices.Contains(_defaultPersonJson.val)) choices.Add(_defaultPersonJson.val);
            _defaultPersonJson.choices = choices;
        }

        private void UpdateStatusText()
        {
            string text = "AIBody Session " + PluginVersion + "\n";
            if (_transport == null) text += "Transport: off\n";
            else
            {
                text += "Transport: " + _transport.Name + " - " + _transport.State + "\n";
                if (!string.IsNullOrEmpty(_transport.LastError)) text += "Last error: " + _transport.LastError + "\n";
            }
            text += "Folder: " + ChannelDir + "\n";
            text += "Companion: " + (_companionAge < CompanionTimeout
                ? "running " + _companionVersion + " (seen " + _companionAge.ToString("0.0") + "s ago)"
                : "NOT RUNNING (start it with --channel " + Channel + ")") + "\n";
            List<string> uids = _persons.AtomUids;
            string target = DefaultAtom;
            text += "Characters (" + uids.Count + "): ";
            if (uids.Count == 0) text += "none - add AIBodyPerson.cslist to a Person atom";
            for (int i = 0; i < uids.Count; i++)
            {
                text += (i > 0 ? ", " : "") + uids[i] + (uids[i] == target ? " (default)" : "");
            }
            _statusJson.val = text + "\n";
        }

        // ---------------------------------------------------------------- teardown

        private void OnDisable()
        {
            if (!_initialized) return;
            StopTransport();
        }

        private void OnEnable()
        {
            if (_initialized && _transport == null && _activeJson != null && _activeJson.val) Restart();
        }

        private void OnDestroy()
        {
            OnDisable();
        }
    }
}
