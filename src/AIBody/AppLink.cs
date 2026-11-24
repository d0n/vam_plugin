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
using UnityEngine.UI;
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
        // Version 30: the short first-run note at the top of the plugin UI (no token anywhere yet).
        private JSONStorableString _hintTokenJson;      // "First run token"; never registered, so never in the scene
        private InputField _hintInput;
        private UIDynamicButton _hintButton;
        private string _hintTyped = "";                      // what the user typed into the note's field (the field itself only shows the mask)
        private bool _hintDismissed;                         // config.json ui.first_run_hint_dismissed
        private bool _hintShown;                             // the state the last UI build used
        private bool _settingHintDisplay;
        public Action OnHintChanged;                         // the plugin rebuilds the tab when the note appears or goes away
        private JSONStorableBool _networkJson;         // "Network Active" (version 30)
        private NetworkTransport _network;             // null while the toggle is off: no socket code runs then
        private int _networkPort = SocketLink.DefaultPort;
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
        // Version 55 (Don 23.11.2026): mute switch. The companion holds the state (single source of truth); this toggle
        // sends it ("mute" event) and shows what the companion reports (heartbeat "muted"). Not saved: off on every start.
        public const string MuteLabel = "Mute AI (stop talking and listening)";
        private JSONStorableBool _mutedJson;
        private bool _syncingMute;     // the heartbeat sets the toggle: do not send it back
        private bool _mutePending;     // switched while the companion was not connected: sent when it is
        private string _muteBy = "";   // companion heartbeat "mute_by" (menu / voice: <phrase>)
        private JSONStorableStringChooser _voiceJson;       // ai.realtime.voice + ai.xai.voice
        // Version 27: persona (folder in Saves/PluginData/AIBody/personas, listed by the companion app) and memory
        // Version 50 (Don, call 20:35): no "(none)" entry any more; the menu offers the female and the male starter
        // persona (Anna, Marc; companion personas.STARTER_PERSONAS) plus persona folders of your own. Default: Anna.
        public const string PersonaFemale = "Anna";
        public const string PersonaMale = "Marc";
        public const string PersonaDefault = PersonaFemale;
        public static readonly string[] StarterPersonas = { PersonaFemale, PersonaMale };
        private JSONStorableStringChooser _personaJson;     // ai.persona_name
        private JSONStorableStringChooser _languageJson;    // ai.language (22.11.2026, Don): "German (de)" -> "de", "Auto" -> "auto"

        public const string LanguageAuto = "Auto";
        public const string LanguageDefault = "German (de)";
        /// <summary>The menu "Language": Auto plus the 20 languages of xAI text to speech (docs.x.ai, 22.11.2026), shown as
        /// "Name (code)"; the code in brackets is what goes to config.json ai.language. Same list as companion languages.py.</summary>
        public static readonly string[] Languages = {
            LanguageAuto, "German (de)", "English (en)", "French (fr)", "Spanish (Spain) (es-ES)", "Spanish (Mexico) (es-MX)",
            "Italian (it)", "Portuguese (Brazil) (pt-BR)", "Portuguese (Portugal) (pt-PT)", "Russian (ru)", "Turkish (tr)",
            "Chinese (zh)", "Japanese (ja)", "Korean (ko)", "Hindi (hi)", "Bengali (bn)", "Indonesian (id)", "Vietnamese (vi)",
            "Arabic (Egypt) (ar-EG)", "Arabic (Saudi Arabia) (ar-SA)", "Arabic (UAE) (ar-AE)" };

        /// <summary>"German (de)" -> "de"; "Auto" (or anything without brackets) -> "auto".</summary>
        public static string LanguageCode(string label)
        {
            if (string.IsNullOrEmpty(label)) return "auto";
            int open = label.LastIndexOf('(');
            int close = label.LastIndexOf(')');
            if (open < 0 || close <= open + 1) return "auto";
            return label.Substring(open + 1, close - open - 1);
        }

        /// <summary>"de" -> "German (de)"; "auto" -> "Auto"; an unknown code -> "<code> (<code>)" so it is kept.</summary>
        public static string LanguageLabel(string code)
        {
            if (string.IsNullOrEmpty(code) || code == "auto") return LanguageAuto;
            for (int i = 0; i < Languages.Length; i++)
                if (string.Equals(LanguageCode(Languages[i]), code, StringComparison.OrdinalIgnoreCase)) return Languages[i];
            return code + " (" + code + ")";
        }
        private JSONStorableBool _memoryJson;               // ai.memory.enabled
        private string _personaInUse = "";                  // companion heartbeat "persona"
        private string _personaNote = "";                   // companion heartbeat "persona_note"
        private JSONClass _memoryInfo;                      // companion heartbeat "memory"

        // API keys: only the PATH of a key file (the key itself would be saved readably in the scene
        // and in config.json). TODO(user decision): a direct key field was asked about; not built.
        // Since version 15 the path fields are not in the menu (they showed as empty, unlabeled
        // boxes); the paths come from config.json ai.xai.key_file / ai.elevenlabs.key_file and are
        // still saved with the scene and sent to the companion (docs/BACKLOG.md).
        // "XAI API Token": a plain free-text field (tab Voice, section Companion connection), no format check.
        // Version 21: saved with the scene only. Version 24: the real token lives in _xaiToken and is
        // saved in config.json (ai.xai.api_key, plain text, at Don's explicit request); the storable
        // _xaiTokenJson is only what the field SHOWS: the masked token ("xai-****...****abcd") once it is saved,
        // and the mask never overwrites the token (see OnTokenEdited). Version 31: the storable is NOT registered
        // with VaM, so no scene ever holds the token, not even the raw text typed or pasted into the field.
        // The token is sent to the companion app in the config event (files in the channel folders)
        // and is never logged.
        private JSONStorableString _xaiTokenJson;
        private string _xaiToken = "";                       // the real token (trimmed)
        private bool _tokenReady;                            // config.json was read; before that nothing is written or cleared
        private bool _settingTokenDisplay;                   // we set the field's text ourselves
        private InputField _tokenInput;                      // the token field's InputField of the tab Voice (rebuilt on every tab switch)
        private bool _maskPending;                           // the field was edited: show the mask as soon as it is NOT focused
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

        /// <summary>True while the user is talking (companion level reports; used by the "User speaking" scene hook and the idle poses).</summary>
        public bool UserSpeaking { get { return _mic != null && _mic.UserSpeaking; } }

        public AppLink(MVRScript plugin, string pluginVersion, Diag diag)
        {
            _plugin = plugin;
            _pluginVersion = pluginVersion;
            _diag = diag ?? new Diag();
        }

        public bool Active { get { return _activeJson != null && _activeJson.val; } }
        /// <summary>Category header of the first-run note on the right (20.11.2026: only headers and controls on the right;
        /// what to paste where is explained in the left field of the tab Voice).</summary>
        public const string HintText = "<b>First start: XAI API Token</b>";
        public const string HintClose = "Close";
        public const string HintOk = "OK";

        /// <summary>
        /// True while the note shows: config.json was read, the user has not closed it before, and no token is known from
        /// the field, config.json (ai.xai.api_key), a key file path or - once the app reported - XAI_API_KEY.
        /// </summary>
        public bool FirstRunHintVisible
        {
            get
            {
                if (_hintDismissed || !_tokenReady || _xaiToken.Length > 0) return false;
                if (_xaiKeyFileJson != null && _xaiKeyFileJson.val.Length > 0) return false;
                return _keyInfo == null || !KeyConfigured("xai");
            }
        }

        /// <summary>Adds the note (one line, one field, one button) at the top of a tab; nothing when it is not due.</summary>
        public void BuildFirstRunHint(UiPage page)
        {
            _hintInput = null;
            _hintButton = null;
            _hintShown = FirstRunHintVisible;
            if (!_hintShown) return;
            _settingHintDisplay = true;
            try { _hintTokenJson.val = _hintTyped.Length > 0 ? MaskToken(_hintTyped) : ""; }
            finally { _settingHintDisplay = false; }
            page.Header(HintText);
            _hintInput = page.TextInputField(_hintTokenJson);
            _hintButton = page.ButtonRef(_hintTyped.Length > 0 ? HintOk : HintClose, OnHintButton);
        }

        private void OnHintEdited(string v)
        {
            if (_settingHintDisplay) return;
            string typed = (v ?? "").Trim();
            if (IsMaskedToken(typed)) return;                // the mask itself is never taken as input
            _hintTyped = typed;
            if (_hintButton != null) _hintButton.buttonText.text = typed.Length > 0 ? HintOk : HintClose;
        }

        /// <summary>"OK" saves what was typed exactly like the token field in the tab Voice does; "Close" just closes. Both close for good.</summary>
        private void OnHintButton()
        {
            string typed = _hintTyped;
            _hintTyped = "";
            _hintDismissed = true;
            if (typed.Length > 0 && _xaiTokenJson != null) _xaiTokenJson.val = typed;   // runs OnTokenEdited: token, config.json, mask
            MarkConfigDirty();                               // writes ui.first_run_hint_dismissed
            _hintShown = false;
            if (OnHintChanged != null) OnHintChanged();
        }

        /// <summary>Every frame: masks the note's field when it loses focus; rebuilds the tab when the note must appear or go.</summary>
        private void TickHint()
        {
            bool focused = _hintInput != null && _hintInput.isFocused;
            if (!focused && _hintTyped.Length > 0 && _hintShown && _hintTokenJson.val != MaskToken(_hintTyped))
            {
                _settingHintDisplay = true;
                try { _hintTokenJson.val = MaskToken(_hintTyped); }
                finally { _settingHintDisplay = false; }
            }
            if (!focused && FirstRunHintVisible != _hintShown && OnHintChanged != null)
            {
                _hintShown = FirstRunHintVisible;
                OnHintChanged();
            }
        }

        public bool NetworkActive { get { return _networkJson != null && _networkJson.val; } }
        public bool IsRunning { get { return _transport != null; } }

        /// <summary>True while companion_heartbeats arrive (last one less than 6 s ago).</summary>
        public bool AppSeen { get { return _appAlive; } }

        /// <summary>True if the app was connected before and its heartbeat stopped.</summary>
        public bool AppLost { get { return !_appAlive && _lastSession != null; } }

        /// <summary>Called when the companion app restarted (new session id): its old speech is void.</summary>
        public Action OnAppRestarted;
        /// <summary>Adds extra objects to the config event (character setup answers).</summary>
        public Action<JSONClass> AppendConfig;

        /// <summary>Outbox files kept while the companion app is away (it clears them on start).</summary>
        private const int MaxOutboxWhileAway = 20;

        // ---------------------------------------------------------------- setup

        public void CreateStorables()
        {
            _activeJson = new JSONStorableBool("Active", true, (bool v) => Restart());
            SettingsDefaults.Bool(_plugin, _activeJson);

            // Version 30: loopback socket to the companion app, files as the fallback. Default on; off = no network code at all.
            _hintTokenJson = new JSONStorableString("First run token", "", OnHintEdited);
            _networkJson = new JSONStorableBool("Network Active", true, (bool v) => Restart());
            SettingsDefaults.Bool(_plugin, _networkJson);
            _filePollJson = new JSONStorableFloat("File poll interval (s)", 0.1f, (float v) => Restart(), 0.02f, 2f);
            SettingsDefaults.Float(_plugin, _filePollJson);
            // Engine choices are refreshed from the companion app's companion_heartbeat.
            // Version 50 (Don, call 20:35): the menus always list every engine of the companion app (EngineChoices, the
            // same lists as companion config.ENGINES_AVAILABLE), also before the app connected; default xai, the real
            // engines (without an xAI key the companion app falls back to the offline test engines null / echo / tone).
            _sttJson = Engine("Speech-to-text", SttChoices, EngineDefault);
            _llmJson = Engine("Language model", LlmChoices, EngineDefault);
            _ttsJson = Engine("Text-to-speech", TtsChoices, EngineDefault);
            // qa = simple questions and answers (STT -> LLM -> TTS with xAI, speech only; the default);
            // auto = realtime voice if the companion has an xAI key, else the chain
            _aiModeJson = new JSONStorableStringChooser("AI mode", new List<string> { ModeQa, "auto", "realtime", "chain" },
                ModeQa, "AI mode", (string v) => { SyncRealtimeToggle(); MarkConfigDirty(); });
            SettingsDefaults.Chooser(_plugin, _aiModeJson);
            // Not registered: only a view of "AI mode" (on = auto, off = qa), so nothing new is saved.
            _realtimeJson = new JSONStorableBool("Use realtime voice", false, SetRealtime);   // not registered (not saved)
            _proactiveJson = new JSONStorableBool("Proactive talking", true, (bool v) => MarkConfigDirty());   // config.json key ai.proactive.enabled; was "Proactive" up to version 22
            SettingsDefaults.Bool(_plugin, _proactiveJson);
            _proactiveIdleJson = new JSONStorableFloat("Speech delay timer (s)", 90f, (float v) => MarkConfigDirty(), 0f, 3600f);   // 0 = proactive speech off; config.json key ai.proactive.idle_seconds; was "Proactive idle (s)" up to version 22
            SettingsDefaults.Float(_plugin, _proactiveIdleJson);
            _bargeInJson = new JSONStorableBool("Voice barge-in (headphones)", true, (bool v) => MarkConfigDirty());   // on by default since 22.11.2026 (Don); config.json ai.barge_in.enabled
            SettingsDefaults.Bool(_plugin, _bargeInJson);
            _mutedJson = new JSONStorableBool(MuteLabel, false, OnMuteToggled);
            _mutedJson.isStorable = false;     // never saved in the scene: unmuted on every start (version 55)
            _mutedJson.isRestorable = false;
            _plugin.RegisterBool(_mutedJson);  // a VaM trigger can mute / unmute too
            // xAI voices: the 28 built-in voices of docs.x.ai (text-to-speech page, 21.11.2026); the companion app
            // replaces the list with the answer of GET /v1/tts/voices (heartbeat "voices"). A custom id is kept.
            _voiceJson = new JSONStorableStringChooser("Voice", new List<string>(XaiVoices), "eve", "Voice",
                (string v) => MarkConfigDirty());
            SettingsDefaults.Chooser(_plugin, _voiceJson);
            // The persona list: Anna (female) and Marc (male) always, plus the folders the companion app reports (version 50).
            _personaJson = new JSONStorableStringChooser("Persona", new List<string>(StarterPersonas), PersonaDefault, "Persona",
                (string v) => MarkConfigDirty());
            // Version 35: the menu is refilled from the last list the companion app reported each time it opens, so it
            // always shows at least Anna and Marc and the app's personas (E25).
            _personaJson.popupOpenCallback = RefreshPersonaChoices;
            SettingsDefaults.Chooser(_plugin, _personaJson);
            _languageJson = new JSONStorableStringChooser("Language", new List<string>(Languages), LanguageDefault, "Language",
                (string v) => MarkConfigDirty());
            SettingsDefaults.Chooser(_plugin, _languageJson);
            _memoryJson = new JSONStorableBool("Memory", true, (bool v) => MarkConfigDirty());   // on by default since version 50 (Don 20:35)
            SettingsDefaults.Bool(_plugin, _memoryJson);
            // No format check on purpose (Don, 18.11.2026): whatever is typed or pasted is sent as is.
            // Not registered (version 31): same as the first-run note's field; the token lives in config.json only.
            _xaiTokenJson = new JSONStorableString(XaiTokenLabel, "", OnTokenEdited);
            _xaiKeyFileJson = new JSONStorableString("xAI key file", "", (string v) => CheckKeyFile(_xaiKeyFileJson, v));
            // Not reset by 'Reset to Default' (plain RegisterString): the key file paths point to the user's keys.
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
        /// <summary>Running prose for the left field of the tab Voice (moved there from below the token field on 20.11.2026).</summary>
        public const string XaiTokenHint = "Paste your xAI API key into <b>XAI API Token</b>; once it is saved, the field shows it masked when you leave it "
            + "(like xai-****...****abcd), to change it you select everything in the field and paste the new key, and to remove it you empty the field.";
        /// <summary>
        /// Security notice at the top of the big info field on the left (tab Voice); the same text (without the bold markup)
        /// is in config.json (ai.xai.api_key_warning, next to ai.xai.api_key). Not shown under the token field.
        /// </summary>
        public const string XaiTokenWarning = "SECURITY NOTICE: the <b>XAI API Token</b> is stored as plain text in config.json (ai.xai.api_key), "
            + "so anyone who can read that file can read your token and you should not share or publish it; since version 31 no scene holds the token any more, "
            + "but a scene saved with AIBody version 21 to 23 still contains the full token, so do not publish such a scene.";
        /// <summary>The same notice for config.json (plain text: the file is read in an editor, not as Unity rich text).</summary>
        public const string XaiTokenWarningPlain = "SECURITY NOTICE: the XAI API Token is stored as plain text in config.json (ai.xai.api_key), "
            + "so anyone who can read that file can read your token and you should not share or publish it; since version 31 no scene holds the token any more, "
            + "but a scene saved with AIBody version 21 to 23 still contains the full token, so do not publish such a scene.";
        /// <summary>One short hint in the big info field on the left (version 30): the toggle depends on VaM's own setting.</summary>
        public const string NetworkNotice = "NETWORK: <b>Network Active</b> (tab Config) needs VaM's global setting Allow Plugins Network Access "
            + "(VaM preferences, Security), and without it the plugin uses the file exchange.";

        /// <summary>The real token (as typed or read from config.json, without surrounding blanks / line breaks; nothing else is checked).</summary>
        private string XaiToken { get { return _xaiToken; } }

        /// <summary>
        /// Shown while the field is not focused: the first 4 and the last 4 characters with a fixed run of stars in
        /// between, "xai-****...****abcd". The number of stars never depends on the token's length. Short tokens
        /// (under 12 characters) show just "****".
        /// </summary>
        public static string MaskToken(string token)
        {
            string t = (token ?? "").Trim();
            if (t.Length == 0) return "";
            if (t.Length < 12) return "****";
            return t.Substring(0, 4) + "****...****" + t.Substring(t.Length - 4);
        }

        /// <summary>True for text the field shows as a mask. A real key never contains four asterisks in a row.</summary>
        public static bool IsMaskedToken(string value)
        {
            return value != null && value.Contains("****");
        }

        /// <summary>The field's text changed: a typed / pasted key becomes the token; the mask itself is ignored.</summary>
        private void OnTokenEdited(string v)
        {
            if (_settingTokenDisplay) return;
            string typed = (v ?? "").Trim();
            if (IsMaskedToken(typed))
            {
                _maskPending = true;                         // text with the mask in it: ignored; the correct mask comes back when focus is lost
                return;
            }
            if (!_tokenReady)
            {
                // Typed before config.json was read: keep it, it is written once the file was read.
                if (typed.Length > 0) _xaiToken = typed;
                return;
            }
            _xaiToken = typed;                               // written to config.json by the plugin's settings writer
            _maskPending = typed.Length > 0;                 // masked when the user leaves the field, never while typing
            UpdateKeyStatus();
            MarkConfigDirty();
        }

        /// <summary>True while the user has the cursor in the token field (InputField.isFocused).</summary>
        private bool TokenFieldFocused()
        {
            return _tokenInput != null && _tokenInput.isFocused;
        }

        private void ShowTokenMask()
        {
            if (TokenFieldFocused())
            {
                _maskPending = true;                         // never rewrite the text under the user's cursor
                return;
            }
            string shown = MaskToken(_xaiToken);
            _maskPending = false;
            if (_xaiTokenJson == null || _xaiTokenJson.val == shown) return;
            _settingTokenDisplay = true;
            try { _xaiTokenJson.val = shown; }
            finally { _settingTokenDisplay = false; }
        }

        /// <summary>
        /// Version 50 (Don, call 20:35): 'Reset to Default' clears the XAI API Token too, like emptying the field: the
        /// field is emptied, config.json ai.xai.api_key is written as "" and the config event carries keys.xai = "", so the
        /// companion app forgets the token (EngineSet.set_ui_key). The token is never logged or shown.
        /// </summary>
        // ---------------------------------------------------------------- mute (version 55)

        /// <summary>The menu toggle changed (by the user or a trigger): tell the companion, which holds the state.</summary>
        private void OnMuteToggled(bool muted)
        {
            if (_syncingMute) return;
            _muteBy = "menu";
            if (!_appAlive)
            {
                _mutePending = true;   // sent as soon as the companion is connected
                return;
            }
            SendMute(muted);
        }

        private void SendMute(bool muted)
        {
            _mutePending = false;
            JSONClass evt = Protocol.NewEvent(Protocol.EvtMute);
            evt["muted"].AsBool = muted;
            Send(evt);
            Log.Info(muted ? "Mute AI: on (menu) - the AI stops talking and ignores what it hears"
                           : "Mute AI: off (menu) - the AI listens and answers again");
        }

        /// <summary>The companion's state (heartbeat "muted"): a voice command flips the toggle here.</summary>
        private void ApplyMuteState(JSONClass msg)
        {
            if (_mutePending)
            {
                SendMute(_mutedJson.val);   // the user's latest choice wins over the companion's older state
                return;
            }
            if (!Protocol.Has(msg, "muted")) return;
            bool muted = Protocol.GetBool(msg, "muted", false);
            _muteBy = Protocol.GetString(msg, "mute_by", _muteBy);
            if (muted == _mutedJson.val) return;
            _syncingMute = true;
            try { _mutedJson.val = muted; }
            finally { _syncingMute = false; }
            Log.Info("Mute AI: " + (muted ? "on" : "off") + " (companion: " + _muteBy + ")");
        }

        /// <summary>Reset to Default (version 55): unmuted.</summary>
        public void ResetMute()
        {
            if (_mutedJson != null) _mutedJson.val = false;
        }

        public bool Muted { get { return _mutedJson != null && _mutedJson.val; } }

        /// <summary>Left info field of the tab Config: what the toggle does, with its exact label in bold.</summary>
        public string MuteInfoText()
        {
            string state = !_appAlive ? (Muted ? "on (sent when the companion app connects)" : "off (companion app not connected)")
                : Muted ? "<color=orange>on</color>" + (_muteBy.Length > 0 ? " (" + _muteBy + ")" : "") : "off";
            return "<b>" + MuteLabel + "</b>: " + state + ". On = the AI stops talking at once, its queued speech is dropped, "
                + "and it ignores everything it hears (no answer, no pose or gesture from speech) until you switch it off. "
                + "By voice: \"shut up\", \"halt's Maul\", \"halt die Klappe\" or \"sei still\" switch it on; "
                + "\"sprich mit mir\", \"speak again\" or \"go ahead talking\" switch it off (also inside a longer sentence). "
                + "Not saved: off after a restart and after Reset to Default.\n";
        }

        public void ClearToken()
        {
            _xaiToken = "";
            _hintTyped = "";
            _maskPending = false;
            ShowTokenMask();
            UpdateKeyStatus();
            MarkConfigDirty();
        }

        /// <summary>
        /// On start (and "Reload Config JSON") the token comes from config.json ai.xai.api_key and fills the field.
        /// If the file has none, a token typed before the file was read is kept and written to the file.
        /// </summary>
        public void AdoptToken(JSONClass root)
        {
            JSONClass ai = root != null ? root["ai"] as JSONClass : null;
            JSONClass xai = ai != null ? ai["xai"] as JSONClass : null;
            string fromFile = xai != null ? Protocol.GetString(xai, "api_key", "").Trim() : "";
            if (fromFile.Length > 0) _xaiToken = fromFile;
            _tokenReady = true;
            ShowTokenMask();
            UpdateKeyStatus();
            MarkConfigDirty();
        }

        /// <summary>
        /// Called every frame (InputField.isFocused is polled, there is no audited end-edit event): while the field has
        /// focus nothing is touched, so a full token can be typed or pasted; once focus is lost the mask is shown.
        /// </summary>
        private void TickTokenMask()
        {
            if (TokenFieldFocused())
            {
                _maskPending = true;                         // the user is in the field; mask it afterwards
                return;
            }
            if (_maskPending) ShowTokenMask();
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
                _keyWarning = "That looks like an API key, so it was NOT saved here (keys must not end up in the scene). "
                    + "Enter the PATH of a text file that contains the key instead, e.g. C:/Users/<you>/keys/xai.txt. "
                    + "Or paste the key into the field '" + XaiTokenLabel + "'.";
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

        public const string EngineDefault = "xai";
        /// <summary>Version 50: the engine lists of companion config.ENGINES_AVAILABLE (real engines first).</summary>
        public static readonly string[] SttChoices = { "xai", "null" };
        public static readonly string[] LlmChoices = { "xai", "ollama", "echo" };
        public static readonly string[] TtsChoices = { "xai", "elevenlabs", "tone" };

        private JSONStorableStringChooser Engine(string name, string[] choices, string defaultValue)
        {
            JSONStorableStringChooser c = new JSONStorableStringChooser(name, new List<string>(choices),
                defaultValue, name, (string v) => MarkConfigDirty());
            SettingsDefaults.Chooser(_plugin, c);
            return c;
        }

        private void AddEngines(JSONClass configEvent)
        {
            JSONClass engines = new JSONClass();
            engines["stt"] = _sttJson.val;
            engines["llm"] = _llmJson.val;
            engines["tts"] = _ttsJson.val;
            configEvent["engines"] = engines;
            configEvent["ai"] = BuildAiJson(false);
            // Version 21: the token travels in the config event only ("keys"), always present so that
            // clearing the field also clears it in the companion app. Not part of BuildAiJson (config.json).
            JSONClass keys = new JSONClass();
            keys["xai"] = XaiToken;
            configEvent["keys"] = keys;
            JSONClass advanced = new JSONClass();
            advanced["verbose_log"].AsBool = Log.Verbose;   // Config > Verbose log: companion turn trace too
            configEvent["advanced"] = advanced;
            if (AppendConfig != null) AppendConfig(configEvent);
        }

        /// <summary>The ai keys the plugin UI controls: mode, proactive on/off + idle, voice barge-in.</summary>
        private JSONClass BuildAiJson(bool forFile)
        {
            JSONClass ai = new JSONClass();
            ai["mode"] = _aiModeJson.val;
            ai["language"] = LanguageCode(_languageJson.val);
            JSONClass proactive = new JSONClass();
            proactive["enabled"].AsBool = _proactiveJson.val;
            proactive["idle_seconds"].AsFloat = (float)Math.Round(_proactiveIdleJson.val);
            ai["proactive"] = proactive;
            JSONClass barge = new JSONClass();
            barge["enabled"].AsBool = _bargeInJson.val;   // 22.11.2026: chain and realtime, echo protection always on
            ai["barge_in"] = barge;
            JSONClass realtime = new JSONClass();
            realtime["voice"] = _voiceJson.val;
            ai["realtime"] = realtime;
            ai["persona_name"] = PersonaName;
            JSONClass memory = new JSONClass();
            memory["enabled"].AsBool = _memoryJson.val;
            ai["memory"] = memory;
            JSONClass xai = new JSONClass();
            xai["voice"] = _voiceJson.val;
            // Key file paths only when set, so an empty field never wipes a path entered in config.json.
            if (_xaiKeyFileJson.val.Length > 0) xai["key_file"] = _xaiKeyFileJson.val;
            // The token goes into config.json only (never into the config event) and only once config.json was read,
            // so an early write cannot wipe a saved token. The warning text stays next to it.
            if (forFile && _tokenReady)
            {
                xai["api_key"] = _xaiToken;
                xai["api_key_warning"] = XaiTokenWarningPlain;
            }
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
            target["persona_name"] = ui["persona_name"].Value;
            if (Protocol.Has(ui, "language")) target["language"] = ui["language"].Value;
            MergeSection(target, ui, "memory", "enabled");
            MergeSection(target, ui, "proactive", "enabled");
            MergeSection(target, ui, "proactive", "idle_seconds");
            MergeSection(target, ui, "barge_in", "enabled");
            MergeSection(target, ui, "realtime", "voice");
            MergeSection(target, ui, "xai", "voice");
            MergeSection(target, ui, "xai", "key_file");
            MergeSection(target, ui, "xai", "api_key");
            MergeSection(target, ui, "xai", "api_key_warning");
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

        /// <summary>Tab "Voice", section "Companion connection": link on/off, API Reconnect, the token field (label above it).</summary>
        public void BuildConnectionSection(UiPage page)
        {
            page.Toggle(_activeJson);
            page.Button("API Reconnect", ApiReconnect);
            page.Header(XaiTokenLabel);   // the label of the field below (an input field shows only its value)
            _tokenInput = page.TextInputField(_xaiTokenJson);   // a new InputField on every tab switch
            if (_tokenInput == null)
                Log.Error("Field '" + XaiTokenLabel + "' is read-only (InputField failed).");
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
        private bool _testTonePending;    // pressed while the app was not connected: sent as soon as it connects (at most one)
        private static bool _testToneWaitLogged;   // version 40: the "not connected yet" log line once per VaM session
        private bool _testToneWaiting;    // sent: waiting for the app's speak "Test tone"
        private float _testToneAge;
        public const float TestToneWait = 60f;      // a press waits this long for the app to connect
        public const float TestToneAnswer = 10f;    // and this long for its answer

        /// <summary>
        /// "Test tone via companion": asks the companion app for a test WAV in its audio folder (tests the path app -> file ->
        /// head audio). Version 35: before, a press while the app was not connected did nothing visible (one line at the end
        /// of the info field). Now the request waits up to TestToneWait s for the app, the result stands at the top of the
        /// Voice info field, and the arrival of the app's answer (or its absence) is reported.
        /// </summary>
        public void RequestTestTone()
        {
            if (!_appAlive)
            {
                // Version 40 (Don, 21.11.2026: six presses gave six log lines): at most ONE request waits; more presses
                // only say so in the left info field, and the VaM log gets this line once per VaM session.
                if (_testTonePending)
                {
                    _testToneStatus = "Test tone via companion: already waiting for the companion app (not connected); one request is kept and sent as soon as the app connects.";
                    return;
                }
                _testToneAge = 0f;
                _testTonePending = true;
                _testToneWaiting = false;
                _testToneStatus = "Test tone via companion: waiting for the companion app (not connected). It is sent as soon as the app connects (up to " + TestToneWait.ToString("0") + " s).";
                if (!_testToneWaitLogged)
                {
                    _testToneWaitLogged = true;
                    Log.Info("Test tone via companion: the companion app is not connected yet; one request waits for it.");
                }
                else Log.Debug("Test tone via companion: waiting for the companion app.");
                return;
            }
            _testToneAge = 0f;
            SendTestTone();
        }

        private void SendTestTone()
        {
            _testTonePending = false;
            _testToneWaiting = true;
            _testToneAge = 0f;
            Send(Protocol.NewEvent(Protocol.EvtTestTone));
            _testToneStatus = "Test tone via companion: requested, waiting for the app's answer ...";
        }

        /// <summary>Called for every body command from the app: the test tone arrives as a speak with the text "Test tone".</summary>
        private void NoteTestToneSpeak(JSONClass msg)
        {
            if (!_testToneWaiting || Protocol.GetString(msg, "type", "") != Protocol.CmdSpeak || Protocol.GetString(msg, "text", "") != "Test tone") return;
            _testToneWaiting = false;
            _testToneStatus = "Test tone via companion: arrived (" + Protocol.GetString(msg, "audio", "") + "), playing on the character. Nothing heard? See 'Audio' in tab AI Character and the red notes here.";
        }

        private void TickTestTone(float dt)
        {
            if (!_testTonePending && !_testToneWaiting) return;
            _testToneAge += dt;
            if (_testTonePending)
            {
                if (_appAlive) SendTestTone();
                else if (_testToneAge > TestToneWait)
                {
                    _testTonePending = false;
                    _testToneStatus = "Test tone via companion: not sent, the companion app did not connect within " + TestToneWait.ToString("0") + " s.";
                }
            }
            else if (_testToneAge > TestToneAnswer)
            {
                _testToneWaiting = false;
                _testToneStatus = "Test tone via companion: no answer from the app within " + TestToneAnswer.ToString("0") + " s (see companion.log).";
            }
        }

        /// <summary>The test tone result for the top of the Voice info field ("" = nothing pressed yet).</summary>
        public string TestToneStatus { get { return _testToneStatus ?? ""; } }

        /// <summary>
        /// Tab "Voice", section "Voice > AI Character": how the AI character listens, thinks and speaks
        /// (AI mode, voice, engines, proactive). No text fields: help and status go to the big info
        /// field on the left (VoiceInfoText).
        /// </summary>
        public void BuildAiSection(UiPage page)
        {
            SyncRealtimeToggle();
            page.Toggle(_realtimeJson);
            page.Popup(_aiModeJson);
            page.Popup(_llmJson);
            page.Popup(_personaJson);
            page.ScrollablePopup(_languageJson);   // 21 entries: the plain popup cannot scroll (version 42)
            page.Toggle(_memoryJson);
            page.Button("Forget memory", ForgetMemory);
            page.Toggle(_proactiveJson);
            page.Slider(_proactiveIdleJson);
        }

        /// <summary>Tab "Voice", section "Voice and sound": the voice, speech-to-text, text-to-speech, the companion sound test.</summary>
        public void BuildVoiceSection(UiPage page)
        {
            page.ScrollablePopup(_voiceJson);   // version 42: 28+ voices; the plain popup cannot scroll, so Don saw only part of the list
            page.Popup(_sttJson);
            page.Popup(_ttsJson);
            page.Button("Test tone via companion", RequestTestTone);
        }

        /// <summary>Button "Forget memory": the companion app deletes the notes about the user and starts a fresh conversation.</summary>
        public void ForgetMemory()
        {
            if (_appAlive) Send(Protocol.NewEvent(Protocol.EvtMemoryForget));
        }

        /// <summary>Persona and memory lines for the Voice tab's info field.</summary>
        private string PersonaInfoText()
        {
            string text = "<b>Language</b> is " + (_languageJson.val == LanguageAuto
                ? "Auto: the persona's language, else every sentence is detected on its own (short sentences can come out in an English accent). "
                : _languageJson.val + ": every sentence is spoken in it, speech recognition expects it, and the AI is told to always answer in it (also in realtime mode); it wins over a persona's language. ");
            text += "The <b>Persona</b> menu " + (_personaListSeen
                ? "offers the female persona " + PersonaFemale + " and the male persona " + PersonaMale + (_personaNames.Count > 0 ? " and lists " + _personaNames.Count + " persona folder(s) from the companion app" : "")
                : "offers the female persona " + PersonaFemale + " and the male persona " + PersonaMale + "; persona folders of your own appear once the companion app "
                  + "has connected (start it from the Windows Start menu, 'AIBody Companion'; it writes Anna and Marc on its first start)") + "; the list comes from the app, and personas are folders in "
                + "Saves/PluginData/AIBody/personas/<name>/ with a persona.json (docs/PERSONAS.md). ";   // version 40 / 50
            if (_appAlive && _personaInUse != PersonaName) text += "The persona '" + PersonaName + "' is not in use: " + (_personaNote.Length > 0 ? _personaNote : "the companion app has not confirmed it yet") + "\n";
            else text += "The persona " + PersonaName + " is in use, and its prompt and voice replace ai.persona and <b>Voice</b> (its language counts only when <b>Language</b> is Auto).\n";
            if (!_memoryJson.val) text += "<b>Memory</b> is off (on by default); switched on, the AI keeps short notes about what you tell it (personas/<name>/memory.json, local; the summary request goes to xAI) and uses them next time.\n";
            else
            {
                string facts = _memoryInfo != null && Protocol.Has(_memoryInfo, "facts") ? _memoryInfo["facts"].Value : "?";
                text += "<b>Memory</b> is on with " + facts + " notes about you; they are updated after the conversation (10 minutes of silence, a persona change or when the app stops), and <b>Forget memory</b> deletes them.\n";
                if (_memoryInfo != null && Protocol.Has(_memoryInfo, "note")) text += "Memory problem: " + _memoryInfo["note"].Value + "\n";
            }
            return text;
        }

        /// <summary>Info for the tab "Voice" in the big field on the left: mode help, key and engine status.</summary>
        public string VoiceInfoText()
        {
            UpdateKeyStatus();
            UpdateEngineInfo();
            string text = XaiTokenWarning + "\n\n" + NetworkNotice + "\n\n" + _modeHelpJson.val + "\n\n" + SpeechVolumeHelp + "\n\n" + XaiTokenHint + "\n" + _keyStatusJson.val + "\n" + PersonaInfoText();
            if (_engineStatus != null) text += _engineInfoJson.val;   // before the first heartbeat the connection section says "not seen yet"
            return text;
        }

        /// <summary>Folder line for the tab "Config": the one fixed folder the plugin and the companion app share.</summary>
        public string NetworkInfoText()
        {
            return "<b>Network Active</b> lets the plugin talk to the companion app over a local socket (127.0.0.1 port " + _networkPort
                + ", set connection.network_port in config.json); " + NetworkStatus + ", and when it is off or unavailable the file exchange is used.";
        }

        public string ChannelInfoText()
        {
            return "The plugin and the companion app exchange messages in the folder " + ChannelDir + " (one character, one fixed folder).";
        }

        /// <summary>
        /// Shown label of the storable "File poll interval (s)" (version 19). The stored name stays
        /// unchanged so saved scenes keep their value; config.json key: advanced.file_poll_interval_s.
        /// </summary>
        public const string FilePollLabel = "Companion inbox poll interval (s)";

        /// <summary>Config tab hint: what the poll interval polls (the companion app's messages, not config.json).</summary>
        public string FilePollInfoText()
        {
            return "<b>" + FilePollLabel + "</b> sets how often the plugin checks the companion app's inbox folder ("
                + ChannelDir + "/inbox/) for messages such as speech, poses and expressions; it does not reload config.json, "
                + "which is what <b>Reload Config JSON</b> does.";
        }

        public const string ModeQa = "qa";

        /// <summary>Version 44 (Don 21:01): Speech volume above 1.</summary>
        public const string SpeechVolumeHelp = "<b>Speech volume (%)</b> 100 is the full volume of the character's head audio (0 to 1000, "
            + "default 100). Above 100 the companion app makes its speech and <b>Test tone via companion</b> louder by that factor (200 = "
            + "twice, 1000 = ten times; no limiter: very high values distort), and <b>Play test tone</b> plays a 2x copy from 150 and a "
            + "3x copy from 250 (also above 300). A sound file cannot go above full scale, so above about 150 the voice mostly gets harsher, not louder. "
            + "<b>Full volume distance (m)</b>: up to this distance from the character's head the voice is at full volume, farther away "
            + "VaM turns it down (default 3 m). A change is applied when the AI is not speaking.";

        private readonly JSONStorableString _modeHelpJson = new JSONStorableString("AI mode help",
            "With <b>AI mode</b> 'qa' your speech is turned into text, Grok answers and the character speaks (talking only); "
            + "'auto' and 'realtime' let you talk to Grok Voice directly and fall back to 'chain' if that does not work, and 'chain' uses the engines "
            + "picked in <b>Language model</b>, <b>Speech-to-text</b> and <b>Text-to-speech</b>. <b>Use realtime voice</b> switches between 'auto' and 'qa'. "
            + "With <b>Proactive talking</b> on, the AI may start talking by itself after a quiet moment, and <b>Speech delay timer (s)</b> is how long it "
            + "must be quiet first (0 = never), not how long the AI takes to answer. There is no separate Question and Answer button: "
            + "with <b>Proactive talking</b> off the character only speaks when you ask it something, and <b>Body control</b> stays as you set it.");

        /// <summary>
        /// Voice > AI > "Use realtime voice": on = AI mode auto (Grok Voice, falls back to
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
                text += "No xAI key yet: paste your xAI API key (from console.x.ai) into <b>" + XaiTokenLabel + "</b> (tab Voice); "
                    + "it is saved in config.json (ai.xai.api_key), so you only do this once, and the XAI_API_KEY environment variable "
                    + "or a key file set in config.json (ai.xai.key_file) work as well.\n";
            if (_keyInfo != null && !KeyConfigured("elevenlabs"))
                text += "ElevenLabs is optional and only needed for ElevenLabs voices: set the ELEVENLABS_API_KEY environment variable or a key file in config.json (ai.elevenlabs.key_file), since there is no field for it here.";
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
            bool toggle = Protocol.GetBool(_proactiveInfo, "enabled", false);
            float idle = Protocol.GetFloat(_proactiveInfo, "idle_seconds", 0f);
            bool on = toggle && idle >= 1f;   // timer 0 s = off, like the toggle (the app never nudges then)
            string line = "Proactive talking: " + (on ? "on - after " + idle.ToString("0") + " s of silence the AI may speak on its own (speech delay timer, not the answer delay)"
                : toggle ? "off (speech delay timer " + idle.ToString("0") + " s)" : "off");
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

        /// <summary>Tab "Client Character": the user's microphone, voice activation and push-to-talk, voice barge-in.</summary>
        public void BuildClientCharacterTab(UiPage page)
        {
            if (_mic != null) _mic.BuildTab(page, _bargeInJson);
            else page.Toggle(_bargeInJson);
        }

        /// <summary>Info for the tab "Client Character": push-to-talk help, microphone status.</summary>
        public string ClientInfoText()
        {
            return _mic != null ? _mic.InfoText() : "";
        }

        /// <summary>Tab "Config" (former Config + Advanced): the shared config.json and the file link.</summary>
        public void BuildConfigTab(UiPage page, UnityEngine.Events.UnityAction reload)
        {
            page.Toggle(_mutedJson);   // version 55: explanation in the left info field (MuteInfoText)
            page.Header("<b>Config file</b>");
            page.Button("Reload Config JSON", reload);
            page.Header("<b>Connection</b>");
            page.Toggle(_networkJson);
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
            JSONClass uiState = root != null ? root["ui"] as JSONClass : null;
            if (uiState != null && Protocol.GetBool(uiState, "first_run_hint_dismissed", false)) _hintDismissed = true;
            JSONClass connection = root != null ? root["connection"] as JSONClass : null;
            int port = connection != null ? (int)Protocol.GetFloat(connection, "network_port", SocketLink.DefaultPort) : SocketLink.DefaultPort;
            _networkPort = (port > 0 && port < 65536) ? port : SocketLink.DefaultPort;
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
            JSONClass ui = new JSONClass();
            ui["first_run_hint_dismissed"].AsBool = _hintDismissed;
            root["ui"] = ui;
            connection["active"].AsBool = Active;
            connection["network_active"].AsBool = NetworkActive;
            connection["network_port"].AsInt = _networkPort;
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
            root["ai"] = BuildAiJson(true);
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
                if (Protocol.Has(connection, "active")) _activeJson.val = Protocol.GetBool(connection, "active", true);
                if (Protocol.Has(connection, "network_active")) _networkJson.val = Protocol.GetBool(connection, "network_active", true);
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
                if (Protocol.Has(ai, "persona_name")) SetPersona(ai["persona_name"].Value);
                if (Protocol.Has(ai, "language")) SetLanguage(ai["language"].Value);
                JSONClass memory = ai["memory"] as JSONClass;
                if (memory != null) _memoryJson.val = Protocol.GetBool(memory, "enabled", _memoryJson.val);
                JSONClass proactive = ai["proactive"] as JSONClass;
                if (proactive != null)
                {
                    _proactiveJson.val = Protocol.GetBool(proactive, "enabled", _proactiveJson.val);
                    _proactiveIdleJson.val = Protocol.GetFloat(proactive, "idle_seconds", _proactiveIdleJson.val);
                }
                JSONClass realtime = ai["realtime"] as JSONClass;
                if (realtime != null) SetVoice(Protocol.GetString(realtime, "voice", _voiceJson.val));
                JSONClass barge = ai["barge_in"] as JSONClass;   // the old realtime.send_while_speaking is ignored (legacy)
                if (barge != null) _bargeInJson.val = Protocol.GetBool(barge, "enabled", _bargeInJson.val);
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

        /// <summary>The persona's folder name for config.json and the companion app ("" = none).</summary>
        private string PersonaName { get { return string.IsNullOrEmpty(_personaJson.val) ? PersonaDefault : _personaJson.val; } }

        /// <summary>config.json ai.language into the menu; an unknown code is added as a choice so it is not lost.</summary>
        private void SetLanguage(string code)
        {
            string label = LanguageLabel(code);
            if (!_languageJson.choices.Contains(label))
            {
                List<string> choices = new List<string>(_languageJson.choices);
                choices.Add(label);
                try { _languageJson.choices = choices; }   // choices refresh: E9, E24, E25
                catch (Exception e) { _diag.Fail("Extend language list", e); }
            }
            _languageJson.val = label;
        }

        private void SetPersona(string name)
        {
            // Version 40: an empty ai.persona_name was "(none)"; version 50 (no "(none)" any more): Anna.
            if (string.IsNullOrEmpty(name) || name == "(none)") name = PersonaDefault;   // version 50: no "(none)" any more
            if (!_personaJson.choices.Contains(name))
            {
                List<string> choices = new List<string>(_personaJson.choices);
                choices.Add(name);
                try { _personaJson.choices = choices; }   // choices refresh: E9, E24, E25
                catch (Exception e) { _diag.Fail("Extend persona list", e); }
            }
            _personaJson.val = name;
        }

        /// <summary>Persona folder names from the last companion heartbeat (version 35: kept for the menu refill).</summary>
        private readonly List<string> _personaNames = new List<string>();
        private bool _personaListSeen;

        /// <summary>The persona list from the companion app: Anna and Marc first, then the folders; the chosen one is kept.
        /// Version 35: a missing list (older app) keeps the last one; version 50: no "(none)" entry.</summary>
        private void SetPersonaChoices(JSONArray names)
        {
            if (names == null || _personaJson == null) return;
            _personaListSeen = true;
            _personaNames.Clear();
            for (int i = 0; i < names.Count; i++)
            {
                string n = names[i].Value;
                if (n.Length > 0 && n != "(none)" && !_personaNames.Contains(n)) _personaNames.Add(n);
            }
            RefreshPersonaChoices();
        }

        /// <summary>Sets the Persona menu from _personaNames: always Anna and Marc first (version 50, no "(none)"), the chosen one is kept.</summary>
        private void RefreshPersonaChoices()
        {
            if (_personaJson == null) return;
            // Version 40: never a blank menu entry; version 50: an empty or "(none)" value (old scene or config) is Anna.
            if (string.IsNullOrEmpty(_personaJson.val) || _personaJson.val == "(none)") _personaJson.val = PersonaDefault;
            List<string> choices = new List<string>(StarterPersonas);   // version 50: female + male starter, no "(none)"
            for (int i = 0; i < _personaNames.Count; i++) if (!choices.Contains(_personaNames[i])) choices.Add(_personaNames[i]);
            if (!choices.Contains(_personaJson.val)) choices.Add(_personaJson.val);
            bool same = choices.Count == _personaJson.choices.Count;
            for (int i = 0; same && i < choices.Count; i++) same = choices[i] == _personaJson.choices[i];
            if (same) return;
            try { _personaJson.choices = choices; }   // choices refresh: E24, E25
            catch (Exception e)
            {
                if (_choicesWarned) return;
                _choicesWarned = true;
                _diag.Fail("Update persona choices", e);
            }
        }

        /// <summary>The built-in xAI voices of docs.x.ai (21.11.2026), the page's order; no invented names.</summary>
        public static readonly string[] XaiVoices = {
            "carina", "zagan", "helix", "orion", "luna", "iris", "altair", "zenith", "perseus", "helios", "lux",
            "kepler", "rigel", "cosmo", "celeste", "ursa", "sirius", "lumen", "castor", "naksh", "atlas", "aurora",
            "liora", "ara", "eve", "leo", "rex", "sal" };

        /// <summary>The voice list from the companion heartbeat (after version 40): GET /v1/tts/voices or its
        /// static list. The chosen voice stays in the menu. An older app sends none: the static list stays.</summary>
        private void SetVoiceChoices(JSONArray names)
        {
            if (names == null || names.Count == 0 || _voiceJson == null) return;
            List<string> choices = new List<string>();
            for (int i = 0; i < names.Count; i++)
            {
                string n = names[i].Value;
                if (n.Length > 0 && !choices.Contains(n)) choices.Add(n);
            }
            if (!string.IsNullOrEmpty(_voiceJson.val) && !choices.Contains(_voiceJson.val)) choices.Add(_voiceJson.val);
            bool same = choices.Count == _voiceJson.choices.Count;
            for (int i = 0; same && i < choices.Count; i++) same = choices[i] == _voiceJson.choices[i];
            if (same) return;
            try { _voiceJson.choices = choices; }   // choices refresh: E9, E24, E25
            catch (Exception e) { _diag.Fail("Update voice list", e); }
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

        /// <summary>
        /// The one fixed sub folder below Saves/PluginData/AIBody (one character, one companion app). A channel value
        /// left behind by version 28 (scene or config.json) is ignored.
        /// </summary>
        public const string Channel = "default";

        public string ChannelDir { get { return DataRoot + "/" + Channel; } }

        public void Restart()
        {
            if (!Ready) return;
            Stop();
            if (_activeJson == null || !_activeJson.val || _filePollJson == null) return;
            LoadSettingsFile();   // also reads connection.network_port
            FileTransport file = new FileTransport(ChannelDir, _filePollJson.val, OnPayload);
            if (NetworkActive)
            {
                _network = new NetworkTransport(file, new SocketLink(_networkPort, OnPayload));
                _transport = _network;
            }
            else
            {
                _network = null;   // off: no network code is touched
                _transport = file;
            }
            _seenEpoch = 0;
            _appSession = null;
            _appAlive = false;
            _appAge = 999f;
            _transport.Start();
            Log.Info("Started " + (_network != null ? "network+file" : "file") + " transport (" + ChannelDir + ")");
        }

        public void Stop()
        {
            if (_transport == null) return;
            _transport.Send(Protocol.NewEvent(Protocol.EvtShutdown));
            _transport.Stop();
            _transport = null;
            _network = null;
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
                NoteTestToneSpeak(msg);
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
            ApplyMuteState(msg);   // version 55
            SetPersonaChoices(msg["personas"] as JSONArray);
            SetVoiceChoices(msg["voices"] as JSONArray);
            _personaInUse = msg["persona"].Value;
            _personaNote = msg["persona_note"].Value;
            JSONClass memoryInfo = msg["memory"] as JSONClass;
            if (memoryInfo != null) _memoryInfo = memoryInfo;
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

        /// <summary>
        /// Version 51 (Don 20:58: "after Reset to Default the dropdowns are empty, must never happen"): every menu of the
        /// link gets its built-in list again (kept: entries the companion app reported, the current value), so no menu
        /// is ever empty or reduced to one entry after a reset or before the companion app reported anything.
        /// </summary>
        public void RefreshAllChoices()
        {
            EnsureChoices(_sttJson, SttChoices);
            EnsureChoices(_llmJson, LlmChoices);
            EnsureChoices(_ttsJson, TtsChoices);
            EnsureChoices(_aiModeJson, new[] { ModeQa, "auto", "realtime", "chain" });
            EnsureChoices(_voiceJson, XaiVoices);
            EnsureChoices(_languageJson, Languages);
            RefreshPersonaChoices();
            if (_mic != null) _mic.RefreshChoices();
        }

        /// <summary>Built-in entries first, then the other entries the menu had, then its value; unchanged lists are not touched.</summary>
        public static void EnsureChoices(JSONStorableStringChooser chooser, string[] builtIn)
        {
            if (chooser == null || builtIn == null) return;
            List<string> choices = new List<string>(builtIn);
            List<string> old = chooser.choices;
            if (old != null) for (int i = 0; i < old.Count; i++) if (!string.IsNullOrEmpty(old[i]) && !choices.Contains(old[i])) choices.Add(old[i]);
            if (!string.IsNullOrEmpty(chooser.val) && !choices.Contains(chooser.val)) choices.Add(chooser.val);
            bool same = old != null && choices.Count == old.Count;
            for (int i = 0; same && i < choices.Count; i++) same = choices[i] == old[i];
            if (same) return;
            chooser.choices = choices;   // choices refresh: E9, E24, E25
        }

        private string[] BuiltInChoices(JSONStorableStringChooser chooser)
        {
            if (chooser == _sttJson) return SttChoices;
            if (chooser == _llmJson) return LlmChoices;
            return TtsChoices;
        }

        private void SetChoices(JSONStorableStringChooser chooser, JSONArray names)
        {
            if (names == null || chooser == null) return;
            // Version 50: the built-in list first (never empty or reduced to the test engine), then what the app reports.
            List<string> choices = new List<string>(BuiltInChoices(chooser));
            for (int i = 0; i < names.Count; i++)
            {
                string n = names[i].Value;
                if (n.Length > 0 && !choices.Contains(n)) choices.Add(n);
            }
            if (!string.IsNullOrEmpty(chooser.val) && !choices.Contains(chooser.val)) choices.Add(chooser.val);
            bool same = choices.Count == chooser.choices.Count;
            for (int i = 0; same && i < choices.Count; i++) same = choices[i] == chooser.choices[i];
            if (same) return;
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
            TickTokenMask();
            TickHint();
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
            TickTestTone(dt);
            if (_mic != null)
            {
                _mic.UiVisible = UiVisible;
                _mic.Update(dt, connected, _appAlive, _activeJson != null && _activeJson.val);
            }
        }

        /// <summary>
        /// Turn status lines from the companion that describe a problem (shown red).
        /// </summary>
        public static bool IsProblemTurn(string turn)
        {
            if (string.IsNullOrEmpty(turn)) return false;
            string[] prefixes = { "Nothing", "No ", "Realtime" };
            for (int i = 0; i < prefixes.Length; i++) if (turn.StartsWith(prefixes[i])) return true;
            return turn.Contains("error") || turn.Contains("Error");
        }

        /// <summary>"Network: off" / "connecting ..." / "connected" / "unavailable, using files" (one short line).</summary>
        public string NetworkStatus
        {
            get
            {
                if (!NetworkActive) return "Network: off";
                return _network != null ? _network.NetworkStatus : "Network: starting";
            }
        }

        /// <summary>Version 36: false while VaM's plugin UI is closed (status texts are not built then).</summary>
        public bool UiVisible = true;

        public string StatusText()
        {
            if (_transport == null) return "Link: " + (Active ? "off" : "inactive (Active is off)") + "\n";
            string text = "Link: " + _transport.Name + " - " + _transport.State + "\n" + NetworkStatus + "\n";
            if (!string.IsNullOrEmpty(_transport.LastError)) text += "Last error: " + _transport.LastError + "\n";
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
            else if (_lastSession != null) text += "Companion app: connection lost (no heartbeat). It reconnects by itself once the app runs again; if it should be running, look at its console window.\n";
            else text += "Companion app: not connected\n";   // version 35: no start instructions in the menu (README, log)
            return text;
        }
    }
}
