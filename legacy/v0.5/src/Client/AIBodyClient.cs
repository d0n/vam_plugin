// AIBody Client plugin - the controlling side: the link between VaM and the companion app
// (the external Python program in companion/), Virt-A-Mate 1.22.
//
// Add it on one atom's Plugins tab (the user's/operator's Person atom, or any other atom such as
// an Empty): Add Plugin ->
//   AddonPackages > d0n.AIBody.<n>:/Custom/Scripts/d0n/AIBody/Client/AIBodyClient.cslist
//   (loose-file install: Custom/Scripts/d0n/AIBody/Client/AIBodyClient.cslist)
// The AI's body is the AIBody Companion plugin on the AI's Person atom.
//
// Responsibilities:
//   - companion app link (file transport in Saves/PluginData/AIBody/<channel>/; HTTP only in
//   - microphone menu (settings, devices, push-to-talk, level meter) and engine selection,
//     sent to the companion app as "config"
//   - routing: body commands from the companion app go to exactly one Companion plugin (the
//     command's "atom", else the "Companion atom" setting, else the only one in the scene);
//     a missing or ambiguous target gives an error, never another atom. Companion events go back
//     to the companion app with "atom".
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;
using UnityEngine.UI;
using AIBodyShared;

namespace AIBodyClient
{
    public class AIBodyClientPlugin : MVRScript
    {
        public const string PluginVersion = "0.5.0";
        public const string DataRoot = "Saves/PluginData/AIBody";

        private const string TransportFile = "File (shared folder)";
        private const float HeartbeatInterval = 2f;
        private const float AppTimeout = 6f;
        private const string AutoCompanion = "(auto: the only one in the scene)";

        private JSONStorableBool _activeJson;
        private JSONStorableStringChooser _transportJson;
        private JSONStorableString _channelJson;
        private JSONStorableFloat _filePollJson;
        private JSONStorableStringChooser _companionAtomJson;
        private JSONStorableStringChooser _sttJson;
        private JSONStorableStringChooser _llmJson;
        private JSONStorableStringChooser _ttsJson;
        private JSONStorableBool _verboseJson;
        private JSONStorableString _statusJson;

        private ITransport _transport;
        private CompanionRegistry _companions;
        private MicConfig _mic;

        private bool _initialized;
        private int _seenEpoch;
        private float _heartbeatTimer;
        private float _uiTimer;
        // The companion app (Python), not the Companion plugin.
        private float _appAge = 999f;
        private string _appSession;
        private string _appVersion = "";

        public override void Init()
        {
            try
            {
                Log.Prefix = "AIBody Client: ";
                _companions = new CompanionRegistry();
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
            _transportJson = new JSONStorableStringChooser("Transport", transports, transports[0], "Transport", (string v) => Restart());
            RegisterStringChooser(_transportJson);

            // Channel = sub folder below Saves/PluginData/AIBody; must match the companion app's --channel.
            _channelJson = new JSONStorableString("Channel", "default", (string v) => Restart());
            RegisterString(_channelJson);
            _filePollJson = new JSONStorableFloat("File poll interval (s)", 0.1f, (float v) => Restart(), 0.02f, 2f);
            RegisterFloat(_filePollJson);

            // Companion for body commands without "atom". Auto = only if exactly one is in the scene.
            _companionAtomJson = new JSONStorableStringChooser("Companion atom", new List<string> { AutoCompanion },
                AutoCompanion, "Companion atom", (string v) => SendCompanions());
            RegisterStringChooser(_companionAtomJson);

            // Engine choices are refreshed from the companion app's companion_heartbeat.
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
            RegisterAction(new JSONStorableAction("Rescan companions", () => _companions.ForceScan()));
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
            CreateButton("Reconnect").button.onClick.AddListener(Restart);
            UIDynamicTextField status = CreateTextField(_statusJson);
            status.height = 300f;

            Header("<b>Characters</b>", false);
            CreatePopup(_companionAtomJson);
            CreateButton("Rescan companions").button.onClick.AddListener(() => _companions.ForceScan());
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
            _seenEpoch = 0;
            _appSession = null;
            _appAge = 999f;
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
            s["role"] = "client";
            s["client"] = containingAtom != null ? containingAtom.uid : "";
            s["plugin_version"] = PluginVersion;
            s["protocol"].AsInt = Protocol.Version;
            s["channel"] = Channel;
            s["transport"] = _transport != null ? _transport.Name : "none";
            s["audio_dir"] = ChannelDir + "/audio";
            AddCompanions(s);
            return s;
        }

        private void SendCompanions()
        {
            if (_companions == null || _transport == null) return;
            JSONClass evt = Protocol.NewEvent(Protocol.EvtCompanions);
            AddCompanions(evt);
            Send(evt);
        }

        private void AddCompanions(JSONClass evt)
        {
            evt["companions"] = _companions.ToJson();
            evt["selected_atom"] = SelectedAtom;
        }

        /// <summary>Companion atom chosen in the UI, "" = auto.</summary>
        private string SelectedAtom
        {
            get { return _companionAtomJson.val == AutoCompanion ? "" : _companionAtomJson.val ?? ""; }
        }

        // ---------------------------------------------------------------- routing

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
                RouteBodyCommand(msg, id);
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

        /// <summary>
        /// Strict routing: the command's "atom" if given, else the "Companion atom" setting, else the
        /// only Companion plugin in the scene. Missing or ambiguous: error back to the companion app;
        /// a command is never redirected to another atom.
        /// </summary>
        private void RouteBodyCommand(JSONClass msg, string id)
        {
            string atom = Protocol.GetString(msg, "atom", "");
            if (atom.Length == 0) atom = SelectedAtom;
            string code, message;
            CompanionLink link = _companions.Resolve(atom, out code, out message);
            if (link == null)
            {
                Log.Debug("Not delivered (" + code + "): " + message);
                JSONClass err = Protocol.NewError(id, code, message);
                if (atom.Length > 0) err["atom"] = atom;
                Send(err);
                return;
            }
            _companions.Deliver(link, msg, containingAtom.uid);
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

        private void StopAllSpeech()
        {
            List<CompanionLink> all = _companions.All;
            for (int i = 0; i < all.Count; i++)
            {
                if (all[i].Storable == null) continue;
                JSONClass stop = new JSONClass();
                stop["v"].AsInt = Protocol.Version;
                stop["type"] = Protocol.CmdStopSpeaking;
                stop["id"] = "client-stop-" + DateTime.UtcNow.Ticks + "-" + i;
                _companions.Deliver(all[i], stop, containingAtom.uid);
            }
        }

        // ---------------------------------------------------------------- frame loop

        private void Update()
        {
            if (!_initialized) return;
            try
            {
                float dt = Time.deltaTime;
                if (_companions.Update(dt))
                {
                    RefreshCompanionChoices();
                    SendCompanions();
                }
                _companions.DrainOutboxes(Send);

                bool connected = false;
                if (_transport != null)
                {
                    _transport.Tick(dt);
                    connected = _transport.IsConnected;
                    _appAge += dt;

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

        private void RefreshCompanionChoices()
        {
            List<string> choices = new List<string> { AutoCompanion };
            List<string> uids = _companions.AtomUids;
            for (int i = 0; i < uids.Count; i++) if (!choices.Contains(uids[i])) choices.Add(uids[i]);
            if (!choices.Contains(_companionAtomJson.val)) choices.Add(_companionAtomJson.val); // keep a saved choice
            // TODO(verify): JSONStorableStringChooser.choices is settable and refreshes the popup.
            _companionAtomJson.choices = choices;
        }

        private void UpdateStatusText()
        {
            string text = "AIBody Client " + PluginVersion + " on '" + containingAtom.uid + "'\n";
            if (_transport == null) text += "Transport: off\n";
            else
            {
                text += "Transport: " + _transport.Name + " - " + _transport.State + "\n";
                if (!string.IsNullOrEmpty(_transport.LastError)) text += "Last error: " + _transport.LastError + "\n";
            }
            text += "Folder: " + ChannelDir + "\n";
            text += "Companion app: " + (_appAge < AppTimeout
                ? "running " + _appVersion + " (seen " + _appAge.ToString("0.0") + "s ago)"
                : "NOT RUNNING (start it with --channel " + Channel + ")") + "\n";
            List<string> uids = _companions.AtomUids;
            text += "Companion plugins (" + uids.Count + "): ";
            if (uids.Count == 0) text += "none - add AIBodyCompanion.cslist to the AI's Person atom";
            text += string.Join(", ", uids.ToArray()) + "\n";
            string code, message;
            CompanionLink target = _companions.Resolve(SelectedAtom, out code, out message);
            text += "Commands go to: " + (target != null ? "'" + target.AtomUid + "'" : "NOBODY (" + message + ")") + "\n";
            _statusJson.val = text;
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
