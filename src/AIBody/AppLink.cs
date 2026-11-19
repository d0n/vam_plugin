// App link: everything that talks to the companion app (the external Python program in
// companion/). A plain component owned by AIBodyPlugin, no MVRScript of its own.
//
//   - transport: JSON files in Saves/PluginData/AIBody/<channel>/ via FileManagerSecure (the only
//     link; there is no network code), channel, heartbeat, connection status
//   - microphone menu (MicConfig) and engine menus, sent to the companion app as "config"
//   - incoming body commands are handed in-process to OnBodyCommand (the Body component);
//     everything else (ping, companion_heartbeat, mic feedback) is handled here
using System;
using System.Collections.Generic;
using SimpleJSON;
using MVR.FileManagementSecure;

namespace AIBody
{
    public class AppLink
    {
        public const string DataRoot = "Saves/PluginData/AIBody";

        private const float HeartbeatInterval = 2f;
        private const float AppTimeout = 6f;

        private readonly MVRScript _plugin;
        private readonly string _pluginVersion;
        private readonly Diag _diag;

        private JSONStorableBool _activeJson;
        private JSONStorableString _channelJson;
        private JSONStorableFloat _filePollJson;
        private JSONStorableStringChooser _sttJson;
        private JSONStorableStringChooser _llmJson;
        private JSONStorableStringChooser _ttsJson;

        private ITransport _transport;
        private MicConfig _mic;

        private int _seenEpoch;
        private bool _appAlive;
        private string _lastSession;   // survives plugin-side restarts; a new value = app restarted
        private float _heartbeatTimer;
        private float _appAge = 999f;
        private string _appSession;
        private string _appVersion = "";
        private JSONClass _engineStatus;   // kind -> engine -> "ready ..." / "not configured: ..."
        private JSONClass _engineActive;   // kind -> engine that really runs (fallback if not configured)
        private readonly JSONStorableString _engineInfoJson = new JSONStorableString("Engine status", "Engines: waiting for the companion app ...");
        private JSONClass _modeInfo;       // companion heartbeat "mode": requested / active / status
        private JSONClass _proactiveInfo;  // companion heartbeat "proactive": enabled / idle_seconds / status
        private JSONClass _audioOut;       // companion heartbeat "audio_out": folder / auto / note
        private string _turn = "";         // companion heartbeat "turn": last question / answer step
        private JSONClass _latency;        // companion heartbeat "latency": last_s, avg_s, n, parts

        // ai controls (sent in the config event, merged into config.json "ai"; the rest of "ai" is file-only)
        private JSONStorableStringChooser _aiModeJson;
        private JSONStorableBool _realtimeJson;
        private bool _syncingRealtime;
        private JSONStorableBool _proactiveJson;
        private JSONStorableFloat _proactiveIdleJson;
        private JSONStorableBool _bargeInJson;
        private JSONStorableStringChooser _voiceJson;       // ai.realtime.voice + ai.xai.voice

        // API keys: only the PATH of a key file (the key itself would be saved readably in the scene
        // and in config.json). TODO(user decision): a direct key field was asked about; not built.
        // Since version 15 the path fields are not in the menu (they showed as empty, unlabeled
        // boxes); the paths come from config.json ai.xai.key_file / ai.elevenlabs.key_file and are
        // still saved with the scene and sent to the companion (docs/BACKLOG.md).
        // Version 21: "XAI API Token", a plain free-text field (Voice tab, Voice Mode). Saved with the scene
        // (hence the hint "(beware: scenes save it)"), sent to the companion app only in the config event
        // (files in the channel folders), never written to config.json, never logged.
        private JSONStorableString _xaiTokenJson;
        private JSONStorableString _xaiKeyFileJson;
        private JSONStorableString _elevenKeyFileJson;
        private JSONClass _keyInfo;                          // companion heartbeat "keys"
        private readonly JSONStorableString _keyStatusJson = new JSONStorableString("API key status", "API keys: waiting for the companion app ...");
        private string _keyWarning;

        /// <summary>Set by the plugin once Init is complete; settings callbacks restart only then.</summary>
        public bool Ready;

        /// <summary>Receives every body command (speak, expression, ...), in-process.</summary>
        public Action<JSONClass> OnBodyCommand;

        /// <summary>Adds the body's state to ready / heartbeat / pong.</summary>
        public Action<JSONClass> DecorateStatus;

        public AppLink(MVRScript plugin, string pluginVersion, Diag diag)
        {
            _plugin = plugin;
            _pluginVersion = pluginVersion;
            _diag = diag ?? new Diag();
        }

        public bool Active { get { return _activeJson != null && _activeJson.val; } }
        public bool IsRunning { get { return _transport != null; } }

        /// <summary>True while companion_heartbeats arrive (last one less than 6 s ago).</summary>
        public bool AppSeen { get { return _appAlive; } }

        /// <summary>True if the app was connected before and its heartbeat stopped.</summary>
        public bool AppLost { get { return !_appAlive && _lastSession != null; } }

        /// <summary>Called when the companion app restarted (new session id): its old speech is void.</summary>
        public Action OnAppRestarted;

        /// <summary>Outbox files kept while the companion app is away (it clears them on start).</summary>
        private const int MaxOutboxWhileAway = 20;

        // ---------------------------------------------------------------- setup

        public void CreateStorables()
        {
            _activeJson = new JSONStorableBool("Active", true, (bool v) => Restart());
            _plugin.RegisterBool(_activeJson);

            // Channel = sub folder below Saves/PluginData/AIBody; must match the companion app's --channel.
            _channelJson = new JSONStorableString("Channel", "default", (string v) => Restart());
            _plugin.RegisterString(_channelJson);
            _filePollJson = new JSONStorableFloat("File poll interval (s)", 0.1f, (float v) => Restart(), 0.02f, 2f);
            _plugin.RegisterFloat(_filePollJson);
            // Engine choices are refreshed from the companion app's companion_heartbeat.
            _sttJson = Engine("Speech-to-text", "null");
            _llmJson = Engine("Language model", "echo");
            _ttsJson = Engine("Text-to-speech", "tone");
            // qa = simple questions and answers (STT -> LLM -> TTS with xAI, speech only; the default);
            // auto = realtime voice if the companion has an xAI key, else the chain
            _aiModeJson = new JSONStorableStringChooser("AI mode", new List<string> { ModeQa, "auto", "realtime", "chain" },
                ModeQa, "AI mode", (string v) => { SyncRealtimeToggle(); MarkConfigDirty(); });
            _plugin.RegisterStringChooser(_aiModeJson);
            // Not registered: only a view of "AI mode" (on = auto, off = qa), so nothing new is saved.
            _realtimeJson = new JSONStorableBool("Use realtime voice", false, SetRealtime);   // not registered (not saved)
            _proactiveJson = new JSONStorableBool("Proactive", true, (bool v) => MarkConfigDirty());
            _plugin.RegisterBool(_proactiveJson);
            _proactiveIdleJson = new JSONStorableFloat("Proactive idle (s)", 90f, (float v) => MarkConfigDirty(), 15f, 3600f);
            _plugin.RegisterFloat(_proactiveIdleJson);
            _bargeInJson = new JSONStorableBool("Voice barge-in (headphones)", false, (bool v) => MarkConfigDirty());
            _plugin.RegisterBool(_bargeInJson);
            // xAI voices (docs.x.ai: same roster for speech-to-speech and TTS); a custom id from config.json is kept.
            _voiceJson = new JSONStorableStringChooser("Voice", new List<string> { "eve", "ara", "rex", "sal", "leo" },
                "eve", "Voice", (string v) => MarkConfigDirty());
            _plugin.RegisterStringChooser(_voiceJson);
            // No format check on purpose (Leon, 18.11.2026): whatever is typed or pasted is sent as is.
            _xaiTokenJson = new JSONStorableString(XaiTokenLabel, "", (string v) => { UpdateKeyStatus(); MarkConfigDirty(); });
            _plugin.RegisterString(_xaiTokenJson);
            _xaiKeyFileJson = new JSONStorableString("xAI key file", "", (string v) => CheckKeyFile(_xaiKeyFileJson, v));
            _plugin.RegisterString(_xaiKeyFileJson);
            _elevenKeyFileJson = new JSONStorableString("ElevenLabs key file", "", (string v) => CheckKeyFile(_elevenKeyFileJson, v));
            _plugin.RegisterString(_elevenKeyFileJson);

            MicConfig mic = new MicConfig(_plugin, Send);
            mic.DecorateConfig = AddEngines;
            _diag.Run("Microphone settings (storables)", mic.CreateStorables);
            _mic = mic;

            _plugin.RegisterAction(new JSONStorableAction("Reconnect", Restart));
        }

        public const string XaiTokenLabel = "XAI API Token";
        public const string XaiTokenHint = "(beware: scenes save it)";

        /// <summary>The token as typed, without surrounding blanks / line breaks (nothing else is checked).</summary>
        private string XaiToken
        {
            get { return _xaiTokenJson != null && _xaiTokenJson.val != null ? _xaiTokenJson.val.Trim() : ""; }
        }

        /// <summary>Same rule as the companion's looks_like_secret: a pasted key is refused and cleared.</summary>
        public static bool LooksLikeKey(string value)
        {
            string v = (value ?? "").Trim();
            if (v.Length == 0) return false;
            if (v.StartsWith("xai-") || v.StartsWith("sk_") || v.StartsWith("sk-")) return true;
            return v.Length >= 24 && v.IndexOfAny(new char[] { '/', '\\', '.', '~', ' ' }) < 0;
        }

        private void CheckKeyFile(JSONStorableString field, string value)
        {
            if (LooksLikeKey(value))
            {
                field.val = "";   // never keep a key in the scene
                _keyWarning = "That looked like an API key and was NOT saved. Enter the PATH of a text file "
                    + "that contains the key (e.g. C:/Users/<you>/keys/xai.txt).";
                Log.Error(_keyWarning);
                UpdateKeyStatus();
                return;
            }
            _keyWarning = null;
            UpdateKeyStatus();
            MarkConfigDirty();
        }

        public void MarkConfigDirty()
        {
            if (_mic != null) _mic.MarkDirty();
        }

        private JSONStorableStringChooser Engine(string name, string defaultValue)
        {
            JSONStorableStringChooser c = new JSONStorableStringChooser(name, new List<string> { defaultValue },
                defaultValue, name, (string v) => MarkConfigDirty());
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
            configEvent["ai"] = BuildAiJson();
            // Version 21: the token travels in the config event only ("keys"), always present so that
            // clearing the field also clears it in the companion app. Not part of BuildAiJson (config.json).
            JSONClass keys = new JSONClass();
            keys["xai"] = XaiToken;
            configEvent["keys"] = keys;
            JSONClass advanced = new JSONClass();
            advanced["verbose_log"].AsBool = Log.Verbose;   // Config > Verbose log: companion turn trace too
            configEvent["advanced"] = advanced;
        }

        /// <summary>The ai keys the plugin UI controls: mode, proactive on/off + idle, voice barge-in.</summary>
        private JSONClass BuildAiJson()
        {
            JSONClass ai = new JSONClass();
            ai["mode"] = _aiModeJson.val;
            JSONClass proactive = new JSONClass();
            proactive["enabled"].AsBool = _proactiveJson.val;
            proactive["idle_seconds"].AsFloat = (float)Math.Round(_proactiveIdleJson.val);
            ai["proactive"] = proactive;
            JSONClass realtime = new JSONClass();
            realtime["send_while_speaking"].AsBool = _bargeInJson.val;
            realtime["voice"] = _voiceJson.val;
            ai["realtime"] = realtime;
            JSONClass xai = new JSONClass();
            xai["voice"] = _voiceJson.val;
            // Key file paths only when set, so an empty field never wipes a path entered in config.json.
            if (_xaiKeyFileJson.val.Length > 0) xai["key_file"] = _xaiKeyFileJson.val;
            ai["xai"] = xai;
            if (_elevenKeyFileJson.val.Length > 0)
            {
                JSONClass eleven = new JSONClass();
                eleven["key_file"] = _elevenKeyFileJson.val;
                ai["elevenlabs"] = eleven;
            }
            return ai;
        }

        /// <summary>
        /// On every start the key file paths come from config.json (also for saved scenes). Since
        /// version 15 there is no menu field, so a path in the file wins over one saved with the scene.
        /// </summary>
        public void AdoptKeyFiles(JSONClass root)
        {
            JSONClass ai = root != null ? root["ai"] as JSONClass : null;
            if (ai == null) return;
            AdoptKeyFile(_xaiKeyFileJson, ai["xai"] as JSONClass);
            AdoptKeyFile(_elevenKeyFileJson, ai["elevenlabs"] as JSONClass);
        }

        private static void AdoptKeyFile(JSONStorableString field, JSONClass section)
        {
            if (field == null || section == null) return;
            string path = Protocol.GetString(section, "key_file", "");
            if (path.Length > 0 && path != field.val && !LooksLikeKey(path)) field.val = path;
        }

        /// <summary>
        /// Copies the UI's ai keys (from BuildAiJson) into the "ai" section read from config.json,
        /// keeping everything else there (persona, engine settings, key FILE paths, realtime/proactive details).
        /// </summary>
        public static void MergeAi(JSONClass target, JSONClass ui)
        {
            if (target == null || ui == null) return;
            target["mode"] = ui["mode"].Value;
            MergeSection(target, ui, "proactive", "enabled");
            MergeSection(target, ui, "proactive", "idle_seconds");
            MergeSection(target, ui, "realtime", "send_while_speaking");
            MergeSection(target, ui, "realtime", "voice");
            MergeSection(target, ui, "xai", "voice");
            MergeSection(target, ui, "xai", "key_file");
            MergeSection(target, ui, "elevenlabs", "key_file");
        }

        private static void MergeSection(JSONClass target, JSONClass ui, string section, string key)
        {
            JSONClass from = ui[section] as JSONClass;
            if (from == null || !Protocol.Has(from, key)) return;
            JSONClass to = target[section] as JSONClass;
            if (to == null)
            {
                to = new JSONClass();
                target[section] = to;
            }
            to[key] = from[key].Value;
        }

        // ---------------------------------------------------------------- tabs (see AIBodyPlugin)

        /// <summary>"Latency to first sound: 2.4 s (avg 2.6 s, 5 turns) – STT 0.80 · …": end of speech -> first sound.</summary>
        private string LatencyLine()
        {
            string text = "Latency to first sound: " + Protocol.GetFloat(_latency, "last_s", 0f).ToString("0.0") + " s (avg "
                + Protocol.GetFloat(_latency, "avg_s", 0f).ToString("0.0") + " s, " + _latency["n"].Value + " turns)";
            JSONClass parts = _latency["parts"] as JSONClass;
            if (parts == null) return text;
            List<string> items = new List<string>();
            foreach (KeyValuePair<string, JSONNode> kv in parts)
                items.Add(kv.Key + " " + kv.Value.AsFloat.ToString("0.00"));
            return text + "\n  " + string.Join(" · ", items.ToArray());
        }

        /// <summary>Tab "Voice", section "Voice Mode": link on/off, realtime, API Reconnect, sound test.</summary>
        public void BuildVoiceModeTab(UiPage page)
        {
            page.Toggle(_activeJson);
            SyncRealtimeToggle();
            page.Toggle(_realtimeJson);
            page.Button("API Reconnect", ApiReconnect);
            // Version 21: plain free-text field (no format check) with the hint directly below.
            page.Header("<b>" + XaiTokenLabel + "</b>");
            if (!page.TextInput(_xaiTokenJson))
                Log.Error("Field '" + XaiTokenLabel + "' is read-only (InputField failed).");
            page.Header(XaiTokenHint);
            page.Button("Test tone via companion", RequestTestTone);
        }

        /// <summary>
        /// "API Reconnect": asks the companion app to re-read its keys and reopen the realtime
        /// connection, then restarts the plugin's own link to the app.
        /// </summary>
        public void ApiReconnect()
        {
            if (_appAlive) Send(Protocol.NewEvent(Protocol.EvtReconnect));
            Restart();
        }

        private string _testToneStatus;

        /// <summary>Asks the companion app for a test WAV in the channel's audio folder (tests that path).</summary>
        public void RequestTestTone()
        {
            if (!_appAlive)
            {
                _testToneStatus = "Test tone via companion: app not connected";
                return;
            }
            Send(Protocol.NewEvent(Protocol.EvtTestTone));
            _testToneStatus = "Test tone via companion requested (arrives as a normal speak command)";
        }

        /// <summary>
        /// Tab "Voice", section "Voice > AI Character": how the AI character listens, thinks and speaks
        /// (AI mode, voice, engines, proactive). No text fields: help and status go to the big info
        /// field on the left (VoiceInfoText).
        /// </summary>
        public void BuildAiVoiceSection(UiPage page)
        {
            page.Popup(_aiModeJson);
            page.Popup(_voiceJson);
            page.Popup(_sttJson);
            page.Popup(_llmJson);
            page.Popup(_ttsJson);
            page.Toggle(_proactiveJson);
            page.Slider(_proactiveIdleJson);
        }

        /// <summary>Info for the tab "Voice" in the big field on the left: mode help, key and engine status.</summary>
        public string VoiceInfoText()
        {
            UpdateKeyStatus();
            UpdateEngineInfo();
            string text = _modeHelpJson.val + "\n" + _keyStatusJson.val + "\n";
            if (_engineStatus != null) text += _engineInfoJson.val;   // before the first heartbeat the connection section says "not seen yet"
            return text;
        }

        /// <summary>Channel line for the tab "Config" (set in config.json connection.channel, not in the menu).</summary>
        public string ChannelInfoText()
        {
            return "Channel: " + Channel + " (" + ChannelDir + "; change via config.json connection.channel or --channel)";
        }

        /// <summary>
        /// Shown label of the storable "File poll interval (s)" (version 19). The stored name stays
        /// unchanged so saved scenes keep their value; config.json key: advanced.file_poll_interval_s.
        /// </summary>
        public const string FilePollLabel = "Companion inbox poll interval (s)";

        /// <summary>Config tab hint: what the poll interval polls (the companion app's messages, not config.json).</summary>
        public string FilePollInfoText()
        {
            return "Companion inbox poll interval: how often the plugin checks the companion app's inbox folder ("
                + ChannelDir + "/inbox/) for messages (speech, poses, expressions). Does not reload config.json; "
                + "use Reload Config JSON for that.";
        }

        public const string ModeQa = "qa";

        private readonly JSONStorableString _modeHelpJson = new JSONStorableString("AI mode help",
            "AI mode: qa = speech recognition -> Grok -> voice (speech only). auto / realtime = Grok Voice directly "
            + "(falls back to the chain). chain = the engines under Voice > AI Character.");

        /// <summary>Button "Question and Answer": AI mode qa (body control is switched off by the plugin).</summary>
        /// <summary>
        /// Voice Mode > "Use realtime voice": on = AI mode auto (Grok Voice, falls back to
        /// the chain), off = qa (the default). Shows on while AI mode is auto or realtime.
        /// </summary>
        private void SetRealtime(bool on)
        {
            if (_syncingRealtime) return;
            bool isOn = _aiModeJson.val == "auto" || _aiModeJson.val == "realtime";
            if (on != isOn) _aiModeJson.val = on ? "auto" : ModeQa;   // its callback marks the config dirty
        }

        private void SyncRealtimeToggle()
        {
            if (_realtimeJson == null || _aiModeJson == null) return;
            bool isOn = _aiModeJson.val == "auto" || _aiModeJson.val == "realtime";
            if (_realtimeJson.val == isOn) return;
            _syncingRealtime = true;
            try { _realtimeJson.val = isOn; }
            finally { _syncingRealtime = false; }
        }

        public void SetSimpleQa()
        {
            _aiModeJson.val = ModeQa;
            MarkConfigDirty();
        }

        /// <summary>Key status per provider from the companion heartbeat: configured / missing / rejected.</summary>
        private void UpdateKeyStatus()
        {
            string text = "";
            if (_keyWarning != null) text += "<color=red>" + _keyWarning + "</color>\n";
            if (_keyInfo == null) text += "API keys: waiting for the companion app ...\n";
            else
            {
                text += KeyLine("xAI", "xai") + KeyLine("ElevenLabs", "elevenlabs");
            }
            // Version 21: the token field is the main way; the environment variable and key file are optional.
            if (_keyInfo == null || !KeyConfigured("xai"))
                text += "Enter the token in the field '" + XaiTokenLabel + "' (tab Voice). XAI_API_KEY or a key file (config.json ai.xai.key_file) also work; the field wins.\n";
            if (_keyInfo != null && !KeyConfigured("elevenlabs"))
                text += "ElevenLabs: ELEVENLABS_API_KEY or a key file (config.json ai.elevenlabs.key_file); no menu field.";
            _keyStatusJson.val = text;
        }

        private bool KeyConfigured(string provider)
        {
            JSONClass k = _keyInfo != null ? _keyInfo[provider] as JSONClass : null;
            return k != null && k["state"].Value == "configured";
        }

        private string KeyLine(string label, string provider)
        {
            JSONClass k = _keyInfo[provider] as JSONClass;
            if (k == null) return label + ": ?\n";
            string state = k["state"].Value;
            string shown = state == "configured" ? "configured" : state == "rejected" ? "<color=red>rejected</color>" : "missing";
            string detail = k["detail"].Value;
            string line = label + " key: " + shown + (detail.Length > 0 ? " – " + detail : "") + "\n";
            // e.g. "needed: an API key from console.x.ai ... a Grok subscription / grok.com token does not work"
            string hint = k["hint"].Value;
            if (state != "configured" && hint.Length > 0) line += "  " + (state == "rejected" ? "<color=red>" + hint + "</color>" : hint) + "\n";
            return line;
        }

        /// <summary>Engine status from the companion heartbeat: what is selected, what really runs, and why.</summary>
        private void UpdateEngineInfo()
        {
            if (_engineStatus == null)
            {
                _engineInfoJson.val = "Engines: waiting for the companion app ...";
                return;
            }
            string text = "<b>Engine status</b> (from the companion app)\n";
            text += ModeLine() + ProactiveLine();
            text += EngineLine("Speech-to-text", "stt", _sttJson);
            text += EngineLine("Language model", "llm", _llmJson);
            text += EngineLine("Text-to-speech", "tts", _ttsJson);
            _engineInfoJson.val = text;
        }

        /// <summary>"Mode: realtime – Realtime connected ..." from the heartbeat (empty for an older app).</summary>
        private string ModeLine()
        {
            if (_modeInfo == null) return "";
            string requested = _modeInfo["requested"].Value, active = _modeInfo["active"].Value;
            string line = "Mode: " + active;
            if (requested == ModeQa) line = "Mode: Question and Answer";
            else if (!string.IsNullOrEmpty(requested) && requested != active) line += " (selected: " + requested + ")";
            string status = _modeInfo["status"].Value;
            if (!string.IsNullOrEmpty(status)) line += " – " + status;
            return line + "\n";
        }

        private string ProactiveLine()
        {
            if (_proactiveInfo == null) return "";
            bool on = Protocol.GetBool(_proactiveInfo, "enabled", false);
            string line = "Proactive: " + (on ? "on, after " + Protocol.GetFloat(_proactiveInfo, "idle_seconds", 0f).ToString("0") + " s of silence" : "off");
            string status = _proactiveInfo["status"].Value;
            if (!string.IsNullOrEmpty(status)) line += " – " + status;
            return line + "\n";
        }

        private string EngineLine(string label, string kind, JSONStorableStringChooser chooser)
        {
            string selected = chooser != null ? chooser.val : "";
            string active = _engineActive != null ? _engineActive[kind].Value : "";
            JSONClass states = _engineStatus[kind] as JSONClass;
            string state = states != null ? states[selected].Value : "";
            string line = label + ": " + selected;
            if (!string.IsNullOrEmpty(state)) line += " – " + state;
            if (!string.IsNullOrEmpty(active) && active != selected) line += "\n    running instead: " + active + " (fallback)";
            return line + "\n";
        }

        /// <summary>Tab "Client Character": the user's microphone and push-to-talk, voice barge-in.</summary>
        public void BuildClientCharacterTab(UiPage page)
        {
            page.Header("<b>Client Character: microphone and push-to-talk</b>");
            if (_mic != null) _mic.BuildTab(page);
            page.Toggle(_bargeInJson);
        }

        /// <summary>Info for the tab "Client Character": push-to-talk help, microphone status.</summary>
        public string ClientInfoText()
        {
            return _mic != null ? _mic.InfoText() : "";
        }

        /// <summary>Tab "Config" (former Config + Advanced): the shared config.json and the file link.</summary>
        public void BuildConfigTab(UiPage page, UnityEngine.Events.UnityAction reload)
        {
            page.Button("Reload Config JSON", reload);
            page.Slider(_filePollJson, FilePollLabel);
        }

        // ---------------------------------------------------------------- shared settings file

        /// <summary>
        /// Saves/PluginData/AIBody/config.json: ONE global file shared with the companion app, in the
        /// customary per-plugin folder (Timeline: Saves/PluginData/Timeline/settings.json,
        /// Keybindings: Saves/PluginData/Keybindings; docs/API_AUDIT.md E10, E19).
        /// </summary>
        public string SettingsPath { get { return DataRoot + "/" + SettingsFileName; } }
        public const string SettingsFileName = "config.json";

        public string ExpressionsPath = DataRoot + "/expressions.json";
        public string GesturesPath = DataRoot + "/gestures.json";

        /// <summary>connection.paths.audio: the companion's speech WAV folder ("" = default); kept, not used here.</summary>
        public string AudioFolder = "";

        /// <summary>Called when the paths from config.json changed (the Body reloads its files).</summary>
        public Action OnPathsChanged;

        private string _pathsText = "";

        /// <summary>
        /// Reads config.json (if there is one), applies the file-only part
        /// (connection.paths) and returns the parsed file for seeding a new scene, else null.
        /// </summary>
        /// <summary>Parses config.json; null if it is missing or not a JSON object. Throws on read errors.</summary>
        public JSONClass ReadSettingsRoot()
        {
            if (!FileManagerSecure.FileExists(SettingsPath)) return null;
            return JSON.Parse(FileManagerSecure.ReadAllText(SettingsPath)) as JSONClass;
        }

        public JSONClass LoadSettingsFile()
        {
            JSONClass root = null;
            string note = "no config.json yet (the plugin and the companion app create it)";
            try
            {
                if (FileManagerSecure.FileExists(SettingsPath))
                {
                    root = ReadSettingsRoot();
                    note = root != null ? "loaded" : "not valid JSON, using defaults";
                }
            }
            catch (Exception e)
            {
                root = null;
                note = "read failed: " + Diag.Describe(e);
            }
            string expressions = DataRoot + "/expressions.json";
            string gestures = DataRoot + "/gestures.json";
            JSONClass connection = root != null ? root["connection"] as JSONClass : null;
            JSONClass paths = connection != null ? connection["paths"] as JSONClass : null;
            if (paths != null)
            {
                expressions = CheckPath(Protocol.GetString(paths, "expressions", expressions), expressions);
                gestures = CheckPath(Protocol.GetString(paths, "gestures", gestures), gestures);
            }
            string audio = "";
            if (paths != null)
            {
                string a = Protocol.GetString(paths, "audio", "");
                if (!string.IsNullOrEmpty(a)) audio = CheckPath(a, "");
            }
            AudioFolder = audio;
            bool changed = expressions != ExpressionsPath || gestures != GesturesPath;
            ExpressionsPath = expressions;
            GesturesPath = gestures;
            // No path display in the menu (it only shows what can be set); the paths go to the log once.
            string pathsText = "Settings file: " + SettingsPath + " (" + note + ")\nExpressions: " + ExpressionsPath
                + "\nGestures: " + GesturesPath + "\nAudio (written by the companion app): "
                + (AudioFolder.Length > 0 ? AudioFolder : "Custom/Sounds/AIBody/" + Channel + " (automatic; if VaM cannot load from there: "
                   + ChannelDir + "/audio)");
            if (pathsText != _pathsText)
            {
                _pathsText = pathsText;
                Log.Info(pathsText.Replace("\n", " | "));
            }
            if (changed && OnPathsChanged != null) OnPathsChanged();
            return root;
        }

        /// <summary>Paths must stay relative to the VaM folder, below Saves/ or Custom/.</summary>
        private static string CheckPath(string path, string fallback)
        {
            if (string.IsNullOrEmpty(path)) return fallback;
            string p = path.Replace('\\', '/');
            bool ok = (p.StartsWith("Saves/") || p.StartsWith("Custom/")) && !p.Contains("..") && !p.Contains(":");
            if (ok) return p;
            Log.Error("config.json: ignoring path '" + path + "' (must be relative, below Saves/ or Custom/)");
            return fallback;
        }

        /// <summary>Adds connection, engines, mic and advanced (companion inbox poll interval, verbose log) to config.json.</summary>
        public void WriteSettings(JSONClass root)
        {
            JSONClass connection = new JSONClass();
            connection["channel"] = Channel;
            connection["active"].AsBool = Active;
            JSONClass paths = new JSONClass();
            paths["expressions"] = ExpressionsPath;
            paths["gestures"] = GesturesPath;
            if (AudioFolder.Length > 0) paths["audio"] = AudioFolder;
            connection["paths"] = paths;
            root["connection"] = connection;
            JSONClass engines = new JSONClass();
            engines["stt"] = _sttJson.val;
            engines["llm"] = _llmJson.val;
            engines["tts"] = _ttsJson.val;
            root["engines"] = engines;
            root["ai"] = BuildAiJson();
            if (_mic != null) root["mic"] = _mic.BuildMicJson();
            JSONClass advanced = new JSONClass();
            advanced["file_poll_interval_s"].AsFloat = _filePollJson.val;
            root["advanced"] = advanced;
        }

        /// <summary>Seeds the UI from config.json (only for a scene without saved AIBody settings).</summary>
        public void ApplySettings(JSONClass root)
        {
            JSONClass connection = root["connection"] as JSONClass;
            if (connection != null)
            {
                if (Protocol.Has(connection, "channel")) _channelJson.val = Protocol.GetString(connection, "channel", _channelJson.val);
                if (Protocol.Has(connection, "active")) _activeJson.val = Protocol.GetBool(connection, "active", true);
            }
            JSONClass engines = root["engines"] as JSONClass;
            if (engines != null)
            {
                _sttJson.val = Protocol.GetString(engines, "stt", _sttJson.val);
                _llmJson.val = Protocol.GetString(engines, "llm", _llmJson.val);
                _ttsJson.val = Protocol.GetString(engines, "tts", _ttsJson.val);
            }
            JSONClass ai = root["ai"] as JSONClass;
            if (ai != null)
            {
                string mode = Protocol.GetString(ai, "mode", _aiModeJson.val);
                if (mode == ModeQa || mode == "auto" || mode == "realtime" || mode == "chain") _aiModeJson.val = mode;
                JSONClass proactive = ai["proactive"] as JSONClass;
                if (proactive != null)
                {
                    _proactiveJson.val = Protocol.GetBool(proactive, "enabled", _proactiveJson.val);
                    _proactiveIdleJson.val = Protocol.GetFloat(proactive, "idle_seconds", _proactiveIdleJson.val);
                }
                JSONClass realtime = ai["realtime"] as JSONClass;
                if (realtime != null)
                {
                    _bargeInJson.val = Protocol.GetBool(realtime, "send_while_speaking", _bargeInJson.val);
                    SetVoice(Protocol.GetString(realtime, "voice", _voiceJson.val));
                }
                JSONClass xai = ai["xai"] as JSONClass;
                if (xai != null && Protocol.Has(xai, "key_file") && !LooksLikeKey(xai["key_file"].Value))
                    _xaiKeyFileJson.val = xai["key_file"].Value;
                JSONClass eleven = ai["elevenlabs"] as JSONClass;
                if (eleven != null && Protocol.Has(eleven, "key_file") && !LooksLikeKey(eleven["key_file"].Value))
                    _elevenKeyFileJson.val = eleven["key_file"].Value;
            }
            if (_mic != null) _mic.ApplyMicJson(root["mic"] as JSONClass);
            JSONClass advanced = root["advanced"] as JSONClass;
            if (advanced != null) _filePollJson.val = Protocol.GetFloat(advanced, "file_poll_interval_s", _filePollJson.val);
        }

        private void SetVoice(string voice)
        {
            if (string.IsNullOrEmpty(voice)) return;
            if (!_voiceJson.choices.Contains(voice))
            {
                List<string> choices = new List<string>(_voiceJson.choices);
                choices.Add(voice);
                try { _voiceJson.choices = choices; }   // choices refresh: E9, E24, E25
                catch (Exception e) { _diag.Fail("Extend voice list", e); }
            }
            _voiceJson.val = voice;
        }

        /// <summary>
        /// Self test: creates the channel folder and writes, checks and deletes a small file there.
        /// Returns null if that worked, else the error.
        /// </summary>
        public string TestWritable()
        {
            string path = ChannelDir + "/selftest.txt";
            try
            {
                FileManagerSecure.CreateDirectory(ChannelDir);
                FileManagerSecure.WriteAllText(path, "AIBody self test");
                if (!FileManagerSecure.FileExists(path)) return "Test file not found: " + path;
                FileManagerSecure.DeleteFile(path);
                return null;
            }
            catch (Exception e)
            {
                return Diag.Describe(e);
            }
        }

        // ---------------------------------------------------------------- transport

        public string Channel
        {
            get
            {
                string channel = _channelJson != null ? _channelJson.val : "default";
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
            if (_activeJson == null || !_activeJson.val || _filePollJson == null) return;
            FileTransport file = new FileTransport(ChannelDir, _filePollJson.val, OnPayload);
            _transport = file;
            _seenEpoch = 0;
            _appSession = null;
            _appAlive = false;
            _appAge = 999f;
            _transport.Start();
            Log.Info("Started " + _transport.Name + " transport on channel '" + Channel + "'");
            LoadSettingsFile();
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
            Log.Debug("-> " + LogText(evt));
            _transport.Send(evt);
        }

        /// <summary>Event text for the log; the "keys" object (the token) is never shown, only whether it is set.</summary>
        private string LogText(JSONClass evt)
        {
            if (!Protocol.Has(evt, "keys")) return evt.ToString();
            return evt["type"].Value + " event (keys masked: XAI API Token "
                + (XaiToken.Length > 0 ? "set, " + XaiToken.Length + " characters" : "empty") + ")";
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
                    if (_mic != null) _mic.HandleConfigAck(msg);
                    break;
                case Protocol.CmdDevices:
                    if (_mic != null) _mic.HandleDevices(msg);
                    break;
                case Protocol.CmdMicState:
                    if (_mic != null) _mic.HandleMicState(msg);
                    break;
                case Protocol.CmdMicLevel:
                    if (_mic != null) _mic.HandleMicLevel(msg);
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
                // Companion app (re)started, or this link restarted: send ready + config again.
                bool appRestarted = _lastSession != null && session != _lastSession;
                _appSession = session;
                _lastSession = session;
                Log.Info("Companion app " + _appVersion + " connected (session " + session + ")");
                _seenEpoch = -1; // forces ready + config in Update
                if (appRestarted && OnAppRestarted != null) OnAppRestarted();
            }
            JSONClass available = msg["engines_available"] as JSONClass;
            if (available != null)
            {
                SetChoices(_sttJson, available["stt"] as JSONArray);
                SetChoices(_llmJson, available["llm"] as JSONArray);
                SetChoices(_ttsJson, available["tts"] as JSONArray);
            }
            JSONClass status = msg["engines_status"] as JSONClass;
            if (status != null) _engineStatus = status;
            JSONClass active = msg["engines_active"] as JSONClass;
            if (active != null) _engineActive = active;
            JSONClass mode = msg["mode"] as JSONClass;
            if (mode != null) _modeInfo = mode;
            JSONClass proactive = msg["proactive"] as JSONClass;
            if (proactive != null) _proactiveInfo = proactive;
            JSONClass keys = msg["keys"] as JSONClass;
            if (keys != null) _keyInfo = keys;
            JSONClass audioOut = msg["audio_out"] as JSONClass;
            if (audioOut != null) _audioOut = audioOut;
            if (Protocol.Has(msg, "turn")) _turn = msg["turn"].Value;
            JSONClass latency = msg["latency"] as JSONClass;
            if (latency != null) _latency = latency;
            UpdateEngineInfo();
            UpdateKeyStatus();
        }

        private bool _choicesWarned;

        private void SetChoices(JSONStorableStringChooser chooser, JSONArray names)
        {
            if (names == null || chooser == null) return;
            List<string> choices = new List<string>();
            for (int i = 0; i < names.Count; i++) choices.Add(names[i].Value);
            if (!choices.Contains(chooser.val)) choices.Add(chooser.val);
            try
            {
                // choices = ... refreshes a shown popup (E24, E25).
                chooser.choices = choices;
            }
            catch (Exception e)
            {
                if (_choicesWarned) return;
                _choicesWarned = true;
                _diag.Fail("Update engine choices", e);
            }
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
                    if (_mic != null) _mic.OnConnected();
                    _heartbeatTimer = 0f;
                }
                bool alive = _appSession != null && _appAge < AppTimeout;
                if (_appAlive && !alive)
                {
                    // Logged once per loss, not every frame.
                    Log.Info("Companion app disconnected (no heartbeat for " + AppTimeout.ToString("0") + " s); "
                        + "reconnects by itself as soon as it runs again.");
                    if (_mic != null) _mic.OnDisconnected();
                    _appSession = null;
                }
                _appAlive = alive;

                _heartbeatTimer += dt;
                if (connected && _heartbeatTimer >= HeartbeatInterval)
                {
                    _heartbeatTimer = 0f;
                    Send(BuildStatus());
                    // Nobody reads the outbox while the app is away: keep only the newest files.
                    if (!alive) _transport.PruneOutbox(MaxOutboxWhileAway);
                }
            }
            if (_mic != null) _mic.Update(dt, connected, _appAlive, _activeJson != null && _activeJson.val);
        }

        /// <summary>
        /// Turn status lines from the companion that describe a problem (shown red). English since
        /// version 18; the German prefixes of older companion versions are still recognised.
        /// </summary>
        public static bool IsProblemTurn(string turn)
        {
            if (string.IsNullOrEmpty(turn)) return false;
            string[] prefixes = { "Nothing", "No ", "Realtime", "Nichts", "Keine" };
            for (int i = 0; i < prefixes.Length; i++) if (turn.StartsWith(prefixes[i])) return true;
            return turn.Contains("error") || turn.Contains("Error") || turn.Contains("Fehler");
        }

        public string StatusText()
        {
            if (_transport == null) return "Link: " + (Active ? "off" : "inactive (Active is off)") + "\n";
            string text = "Link: " + _transport.Name + " - " + _transport.State + "\n";
            if (!string.IsNullOrEmpty(_transport.LastError)) text += "Last error: " + _transport.LastError + "\n";
            if (_testToneStatus != null) text += _testToneStatus + "\n";
            if (_appAlive)
            {
                // Version 17: modes and engines only once, in the engine status above (no second summary).
                text += "Companion app: connected, " + _appVersion + " (last heartbeat " + _appAge.ToString("0.0") + " s ago)\n";
                if (_audioOut != null)
                {
                    text += "Audio folder: " + _audioOut["folder"].Value + "\n";
                    string note = _audioOut["note"].Value;
                    if (!string.IsNullOrEmpty(note)) text += "<color=red>" + note + "</color>\n";
                }
                if (!string.IsNullOrEmpty(_turn))
                {
                    bool bad = IsProblemTurn(_turn);
                    text += "Last turn: " + (bad ? "<color=red>" + _turn + "</color>" : _turn) + "\n";
                }
                if (_latency != null) text += LatencyLine() + "\n";
            }
            else if (_lastSession != null) text += "Companion app: DISCONNECTED – reconnects automatically as soon as the app runs again\n";
            else text += "Companion app: not seen yet – start it: python -m aibody_companion --vam-root \"D:\\VaM\" --channel " + Channel + "\n";
            return text;
        }
    }
}
