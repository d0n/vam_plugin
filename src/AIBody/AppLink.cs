// App link: everything that talks to the companion app (the external Python program in
// companion/). A plain component owned by AIBodyPlugin, no MVRScript of its own.
//
//   - transport: JSON files in Saves/PluginData/AIBody/<channel>/ via FileManagerSecure (HTTP only
//     in the optional AIBODY_HTTP build), channel, heartbeat, connection status
//   - microphone menu (MicConfig) and engine menus, sent to the companion app as "config"
//   - incoming body commands are handed in-process to OnBodyCommand (the Body component);
//     everything else (ping, companion_heartbeat, mic feedback) is handled here
using System;
using System.Collections.Generic;
using SimpleJSON;

namespace AIBody
{
    public class AppLink
    {
        public const string DataRoot = "Saves/PluginData/AIBody";

        private const string TransportFile = "File (shared folder)";
#if AIBODY_HTTP
        private const string TransportAuto = "Auto (HTTP, file fallback)";
        private const string TransportHttp = "HTTP only";
#endif
        private const float HeartbeatInterval = 2f;
        private const float AppTimeout = 6f;

        private readonly MVRScript _plugin;
        private readonly string _pluginVersion;

        private JSONStorableBool _activeJson;
        private JSONStorableStringChooser _transportJson;
        private JSONStorableString _channelJson;
        private JSONStorableFloat _filePollJson;
#if AIBODY_HTTP
        private JSONStorableString _hostJson;
        private JSONStorableString _portJson;
#endif
        private JSONStorableStringChooser _sttJson;
        private JSONStorableStringChooser _llmJson;
        private JSONStorableStringChooser _ttsJson;

        private ITransport _transport;
        private MicConfig _mic;

        private int _seenEpoch;
        private float _heartbeatTimer;
        private float _appAge = 999f;
        private string _appSession;
        private string _appVersion = "";

        /// <summary>Set by the plugin once Init is complete; settings callbacks restart only then.</summary>
        public bool Ready;

        /// <summary>Receives every body command (speak, expression, ...), in-process.</summary>
        public Action<JSONClass> OnBodyCommand;

        /// <summary>Adds the body's state to ready / heartbeat / pong.</summary>
        public Action<JSONClass> DecorateStatus;

        public AppLink(MVRScript plugin, string pluginVersion)
        {
            _plugin = plugin;
            _pluginVersion = pluginVersion;
        }

        public bool Active { get { return _activeJson != null && _activeJson.val; } }
        public bool IsRunning { get { return _transport != null; } }

        // ---------------------------------------------------------------- setup

        public void CreateStorables()
        {
            _activeJson = new JSONStorableBool("Active", true, (bool v) => Restart());
            _plugin.RegisterBool(_activeJson);

            List<string> transports = new List<string> { TransportFile };
#if AIBODY_HTTP
            transports.Insert(0, TransportAuto);
            transports.Add(TransportHttp);
#endif
            _transportJson = new JSONStorableStringChooser("Transport", transports, transports[0], "Transport", (string v) => Restart());
            _plugin.RegisterStringChooser(_transportJson);

            // Channel = sub folder below Saves/PluginData/AIBody; must match the companion app's --channel.
            _channelJson = new JSONStorableString("Channel", "default", (string v) => Restart());
            _plugin.RegisterString(_channelJson);
            _filePollJson = new JSONStorableFloat("File poll interval (s)", 0.1f, (float v) => Restart(), 0.02f, 2f);
            _plugin.RegisterFloat(_filePollJson);
#if AIBODY_HTTP
            _hostJson = new JSONStorableString("Companion host", "127.0.0.1", (string v) => Restart());
            _plugin.RegisterString(_hostJson);
            _portJson = new JSONStorableString("Companion port", "8765", (string v) => Restart());
            _plugin.RegisterString(_portJson);
#endif
            // Engine choices are refreshed from the companion app's companion_heartbeat.
            _sttJson = Engine("Speech-to-text", "null");
            _llmJson = Engine("Language model", "echo");
            _ttsJson = Engine("Text-to-speech", "tone");

            _mic = new MicConfig(_plugin, Send);
            _mic.CreateStorables();
            _mic.DecorateConfig = AddEngines;

            _plugin.RegisterAction(new JSONStorableAction("Reconnect", Restart));
        }

        private JSONStorableStringChooser Engine(string name, string defaultValue)
        {
            JSONStorableStringChooser c = new JSONStorableStringChooser(name, new List<string> { defaultValue },
                defaultValue, name, (string v) => { if (_mic != null) _mic.MarkDirty(); });
            _plugin.RegisterStringChooser(c);
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

        /// <summary>Connection controls on the left (below the status box), engines, advanced; mic menu on the right.</summary>
        public void CreateUI()
        {
            UiHelper.Header(_plugin, "<b>Companion app link</b>", false);
            _plugin.CreateToggle(_activeJson);
            _plugin.CreatePopup(_transportJson);
            UiHelper.TextInput(_plugin, _channelJson, false);
#if AIBODY_HTTP
            UiHelper.TextInput(_plugin, _hostJson, false);
            UiHelper.TextInput(_plugin, _portJson, false);
#endif
            _plugin.CreateButton("Reconnect").button.onClick.AddListener(Restart);

            UiHelper.Header(_plugin, "<b>Engines</b> (provided by the companion app)", false);
            _plugin.CreatePopup(_sttJson);
            _plugin.CreatePopup(_llmJson);
            _plugin.CreatePopup(_ttsJson);

            UiHelper.Header(_plugin, "<b>Advanced</b>", false);
            _plugin.CreateSlider(_filePollJson);

            _mic.CreateUI(true);
        }

        // ---------------------------------------------------------------- transport

        public string Channel
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

        public string ChannelDir { get { return DataRoot + "/" + Channel; } }

        public void Restart()
        {
            if (!Ready) return;
            Stop();
            if (!_activeJson.val) return;
            FileTransport file = new FileTransport(ChannelDir, _filePollJson.val, OnPayload);
            _transport = file;
#if AIBODY_HTTP
            if (_transportJson.val != TransportFile)
            {
                int port;
                if (!int.TryParse(_portJson.val, out port)) port = 8765;
                HttpTransport http = new HttpTransport(_plugin, _hostJson.val, port, Channel, _pluginVersion, OnPayload);
                _transport = _transportJson.val == TransportHttp ? (ITransport)http : new AutoTransport(http, file);
            }
#endif
            _seenEpoch = 0;
            _appSession = null;
            _appAge = 999f;
            _transport.Start();
            Log.Info("Started " + _transport.Name + " transport on channel '" + Channel + "'");
        }

        public void Stop()
        {
            if (_transport == null) return;
            _transport.Send(Protocol.NewEvent(Protocol.EvtShutdown));
            _transport.Stop();
            _transport = null;
            if (_mic != null) _mic.OnDisconnected();
        }

        /// <summary>Sends an event to the companion app (dropped while the link is off).</summary>
        public void Send(JSONClass evt)
        {
            if (_transport == null || evt == null) return;
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
            s["plugin_version"] = _pluginVersion;
            s["protocol"].AsInt = Protocol.Version;
            s["channel"] = Channel;
            s["transport"] = _transport != null ? _transport.Name : "none";
            s["audio_dir"] = ChannelDir + "/audio";
            if (DecorateStatus != null) DecorateStatus(s);
            return s;
        }

        // ---------------------------------------------------------------- incoming

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
                    Handle(messages[i]);
                }
                catch (Exception e)
                {
                    Log.Error("Handling message failed", e);
                    Send(Protocol.NewError(Protocol.GetString(messages[i], "id", ""), "command_failed", e.Message));
                }
            }
        }

        private void Handle(JSONClass msg)
        {
            string type = Protocol.GetString(msg, "type", "");
            string id = Protocol.GetString(msg, "id", "");

            if (Protocol.IsBodyCommand(type))
            {
                if (OnBodyCommand != null) OnBodyCommand(msg);
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
            _appAge = 0f;
            _appVersion = Protocol.GetString(msg, "version", "");
            string session = Protocol.GetString(msg, "session", "");
            if (session != _appSession)
            {
                // Companion app (re)started: it lost our settings and cleared its folders.
                _appSession = session;
                Log.Info("Companion app " + _appVersion + " is running (session " + session + ")");
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

        // ---------------------------------------------------------------- frame loop

        public void Update(float dt)
        {
            bool connected = false;
            if (_transport != null)
            {
                _transport.Tick(dt);
                connected = _transport.IsConnected;
                _appAge += dt;

                // New connection, folder re-created, or companion app restarted.
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
        }

        public string StatusText()
        {
            if (_transport == null) return "Link: " + (Active ? "off" : "inactive (Active is off)") + "\n";
            string text = "Link: " + _transport.Name + " - " + _transport.State + "\n";
            if (!string.IsNullOrEmpty(_transport.LastError)) text += "Last error: " + _transport.LastError + "\n";
            text += "Folder: " + ChannelDir + "\n";
            text += "Companion app: " + (_appAge < AppTimeout
                ? "running " + _appVersion + " (seen " + _appAge.ToString("0.0") + "s ago)"
                : "NOT RUNNING (start it with --channel " + Channel + ")") + "\n";
            return text;
        }
    }
}
