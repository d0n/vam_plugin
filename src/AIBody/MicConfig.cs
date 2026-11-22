// Microphone settings menu. The microphone itself is captured by the companion app (the plugin
// sandbox cannot load audio libraries and Unity's Microphone class is unverified inside VaM),
// so this class only holds the settings, shows feedback and talks to the companion app:
//   plugin -> companion app: "config" (all mic settings), "ptt" (push-to-talk state)
//   companion app -> plugin: "config_ack", "mic_state", "mic_level"
// Next version: no microphone selection. The companion app always captures the system default
// input (sounddevice default); an old "device" value in a scene or config.json is ignored.
// All settings are JSONStorables, so they are saved with the scene. Changes are sent to the
// companion app (debounced) and applied there live.
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;

namespace AIBody
{
    public class MicConfig
    {
        public const string ModeVad = "Voice activation";
        public const string ModePtt = "Push-to-talk";

        // Voice detector choice (config.json mic.vad_engine: auto / energy / webrtc / silero).
        public const string VadAuto = "Auto";
        public const string VadBuiltIn = "Built-in";
        public const string VadWebRtc = "WebRTC";
        public const string VadSilero = "Silero";

        /// <summary>Start command of the companion app: written to the VaM log once when the app is not running (version 35:
        /// no longer in the menu, Leon 20.11.2026).</summary>
        // Leon, 21.11.2026: users install the companion with "AIBody Companion Setup.exe" and start it from the Start menu;
        // no Python or console command in user-facing plugin text.
        public const string StartHint = "start 'AIBody Companion' from the Windows Start menu (installed with 'AIBody Companion Setup.exe'); it then runs in the background";
        // Version 40: static = once per VaM session, not once per plugin instance or scene load.
        private static bool _startHintLogged;

        private readonly MVRScript _plugin;
        private readonly Action<JSONClass> _send;

        public JSONStorableBool Enabled;
        public JSONStorableStringChooser Mode;
        public JSONStorableFloat Threshold;
        public JSONStorableStringChooser VadEngine;
        public JSONStorableFloat VadStrictness;
        public JSONStorableFloat SilenceMs;
        public JSONStorableFloat MinUtteranceMs;
        public JSONStorableFloat MaxUtteranceMs;
        public JSONStorableFloat EchoTail;
        public JSONStorableFloat Gain;
        public JSONStorableBool PttInterrupts;
        public JSONStorableBool LevelMeter;

        // Not registered: push-to-talk state must not be saved with the scene. Scene triggers
        // and key bindings use the registered actions instead.
        private JSONStorableBool _pttActive;
        private JSONStorableString _pttHelp;
        private JSONStorableString _status;

        private bool _dirty;
        private float _sinceChange;
        private string _micState = "unknown (the companion app is not connected)";
        private string _ackText = "";
        private string _levelText = "";
        private float _levelAge = 999f;
        private float _speechAge = 999f;   // seconds since the last level report that said "speech"
        private string _appHint = "";   // red hint while the link is off or the companion app is not running
        private bool _linkActive = true;
        private bool _appRunning;

        public MicConfig(MVRScript plugin, Action<JSONClass> send)
        {
            _plugin = plugin;
            _send = send;
        }

        /// <summary>Lets the app link add more settings (engines) to every config event.</summary>
        public Action<JSONClass> DecorateConfig;

        public bool PttActive { get { return _pttActive != null && _pttActive.val; } }

        public void CreateStorables()
        {
            Enabled = Reg(new JSONStorableBool("Mic enabled", true, (bool v) => MarkDirty()));
            Mode = new JSONStorableStringChooser("Mic mode", new List<string> { ModeVad, ModePtt }, ModeVad, "Mic mode",
                (string v) => MarkDirty());
            SettingsDefaults.Chooser(_plugin, Mode);
            // RMS level (0..1) above which a frame counts as speech.
            Threshold = Reg(new JSONStorableFloat("VAD threshold", 0.01f, (float v) => MarkDirty(), 0.001f, 0.5f));
            // Voice detector: Auto = WebRTC if the companion app has it installed, else the built-in one.
            VadEngine = new JSONStorableStringChooser("VAD engine", new List<string> { VadAuto, VadBuiltIn, VadWebRtc, VadSilero }, VadAuto,
                "VAD engine", (string v) => MarkDirty());
            SettingsDefaults.Chooser(_plugin, VadEngine);
            // 0..3: higher = ignores more background noise.
            VadStrictness = Reg(new JSONStorableFloat("VAD strictness", 2f, (float v) => MarkDirty(), 0f, 3f));
            SilenceMs = Reg(new JSONStorableFloat("Silence timeout (ms)", 700f, (float v) => MarkDirty(), 200f, 5000f));
            MinUtteranceMs = Reg(new JSONStorableFloat("Min utterance (ms)", 300f, (float v) => MarkDirty(), 100f, 5000f));
            MaxUtteranceMs = Reg(new JSONStorableFloat("Max utterance (ms)", 20000f, (float v) => MarkDirty(), 1000f, 60000f));
            EchoTail = Reg(new JSONStorableFloat("Echo gate tail (s)", 0.4f, (float v) => MarkDirty(), 0f, 3f));
            Gain = Reg(new JSONStorableFloat("Input gain", 1f, (float v) => MarkDirty(), 0.1f, 8f));
            PttInterrupts = Reg(new JSONStorableBool("Push-to-talk interrupts speech", true, (bool v) => MarkDirty()));
            LevelMeter = Reg(new JSONStorableBool("Show level meter", true, (bool v) => MarkDirty()));

            _pttActive = new JSONStorableBool("Push-to-talk active", false, (bool v) => SendPtt(v));
            _status = new JSONStorableString("Mic status", "");
            // VaM's plugin UI has no tooltip / hover API with public evidence, so the explanation
            // stands in the big info field on the left while the tab Client Character is open.
            _pttHelp = new JSONStorableString("Push-to-talk help",
                "While <b>Push-to-talk active</b> is checked the companion app listens to your microphone, like holding the talk button of a "
                + "walkie-talkie, but only when <b>Mic mode</b> is 'Push-to-talk'; you can also use the actions Push-to-talk start, stop and toggle "
                + "from triggers or keys, and <b>Push-to-talk interrupts speech</b> stops the character when you start talking. "
                + "The microphone is always the system default input (change it in your system sound settings), <b>Input gain</b> amplifies it and "
                + "<b>Show level meter</b> shows its level here. <b>VAD engine</b> decides how speech is told from noise: 'Auto' uses Silero if its model "
                + "file is installed (docs/TECHNICAL.md), else WebRTC (part of the installed AIBody Companion), otherwise "
                + "the built-in detector. A higher <b>VAD strictness</b> (0-3) ignores more background noise, <b>VAD threshold</b> is the quietest level "
                + "that can count as speech, <b>Silence timeout (ms)</b> ends an utterance and <b>Min utterance (ms)</b> and <b>Max utterance (ms)</b> "
                + "limit its length. While the character talks, and for <b>Echo gate tail (s)</b> afterwards, the microphone is muted for the AI on purpose "
                + "so it never hears itself (echo protection, always on). <b>Voice barge-in (headphones)</b> (on by default, voice activation, all AI modes) "
                + "still lets you interrupt: when you talk clearly louder than her voice coming back into the microphone for about half a second, she stops "
                + "at once and what you said is answered. With headphones a normal voice is enough; with speakers speak up. Fine tuning: config.json ai.barge_in.");

            _plugin.RegisterAction(new JSONStorableAction("Push-to-talk start", () => _pttActive.val = true));
            _plugin.RegisterAction(new JSONStorableAction("Push-to-talk stop", () => _pttActive.val = false));
            _plugin.RegisterAction(new JSONStorableAction("Push-to-talk toggle", () => _pttActive.val = !_pttActive.val));
        }

        private JSONStorableBool Reg(JSONStorableBool p) { return SettingsDefaults.Bool(_plugin, p); }
        private JSONStorableFloat Reg(JSONStorableFloat p) { return SettingsDefaults.Float(_plugin, p); }

        /// <summary>Microphone and push-to-talk controls of the tab Client Character.</summary>
        public void BuildTab(UiPage page, JSONStorableBool bargeIn)
        {
            page.Header("<b>Microphone</b>");
            page.Toggle(Enabled);
            page.Popup(Mode);
            page.Slider(Gain);
            page.Toggle(LevelMeter);
            page.Header("<b>Push-to-talk</b>");
            page.Toggle(_pttActive);
            page.Toggle(PttInterrupts);
            page.Header("<b>Voice detection</b>");
            page.Popup(VadEngine);
            page.Slider(Threshold);
            page.Slider(VadStrictness);
            page.Slider(SilenceMs);
            page.Slider(MinUtteranceMs);
            page.Slider(MaxUtteranceMs);
            page.Header("<b>Echo and barge-in</b>");
            page.Slider(EchoTail);
            page.Toggle(bargeIn);
        }

        /// <summary>Push-to-talk help and microphone status for the big info field (tab Client Character).</summary>
        public string InfoText()
        {
            if (_pttHelp == null || _status == null || LevelMeter == null) return "";
            RefreshStatus();
            return _pttHelp.val + "\n" + _status.val + "\n";
        }

        public void MarkDirty()
        {
            _dirty = true;
            _sinceChange = 0f;
        }

        /// <summary>Called on every (re)connect: push settings.</summary>
        public void OnConnected()
        {
            SendConfig();
            if (PttActive) SendPtt(true);
        }

        public const float StatusInterval = 0.2f;
        private float _statusAge = StatusInterval;

        /// <summary>Set by the plugin each frame: false while VaM's plugin UI is closed (nothing to show then).</summary>
        public bool UiVisible = true;

        public void Update(float deltaTime, bool connected, bool appRunning, bool linkActive)
        {
            _appRunning = appRunning;
            _linkActive = linkActive;
            _sinceChange += deltaTime;
            _levelAge += deltaTime;
            _speechAge += deltaTime;
            // The companion app is the only thing that listens: say plainly when it is not there.
            // Version 35 (Leon): only a neutral one-line status in the menu; the start command goes to the log once.
            _appHint = !linkActive
                ? "Companion app: link switched off ('Active' in tab Voice)"
                : !appRunning ? "Companion app: not connected" : "";
            if (linkActive && !appRunning && !_startHintLogged)
            {
                _startHintLogged = true;
                Log.Info("Companion app not connected: " + StartHint + ".");
            }
            // Debounce slider drags: send 0.3 s after the last change.
            if (_dirty && connected && _sinceChange > 0.3f) SendConfig();
            // Version 36 (performance): the status text was rebuilt every frame (string garbage at 90 fps);
            // now 5 times a second and only while the plugin UI is open.
            _statusAge += deltaTime;
            if (UiVisible && _statusAge >= StatusInterval)
            {
                _statusAge = 0f;
                RefreshStatus();
            }
        }

        // ------------------------------------------------------------------ outgoing

        public JSONClass BuildConfigEvent()
        {
            JSONClass evt = Protocol.NewEvent(Protocol.EvtConfig);
            evt["mic"] = BuildMicJson();
            if (DecorateConfig != null) DecorateConfig(evt);
            return evt;
        }

        /// <summary>The "mic" object: same keys in the config event and in config.json.</summary>
        public JSONClass BuildMicJson()
        {
            JSONClass mic = new JSONClass();
            mic["enabled"].AsBool = Enabled.val;
            mic["mode"] = Mode.val == ModePtt ? "ptt" : "vad";
            mic["vad_threshold"].AsFloat = Threshold.val;
            mic["vad_engine"] = VadEngine.val == VadBuiltIn ? "energy" : VadEngine.val == VadWebRtc ? "webrtc" : VadEngine.val == VadSilero ? "silero" : "auto";
            mic["vad_strictness"].AsInt = Mathf.RoundToInt(VadStrictness.val);
            mic["end_silence_ms"].AsInt = Mathf.RoundToInt(SilenceMs.val);
            mic["min_utterance_ms"].AsInt = Mathf.RoundToInt(MinUtteranceMs.val);
            mic["max_utterance_ms"].AsInt = Mathf.RoundToInt(MaxUtteranceMs.val);
            mic["echo_tail_s"].AsFloat = EchoTail.val;
            mic["gain"].AsFloat = Gain.val;
            mic["ptt_interrupts"].AsBool = PttInterrupts.val;
            mic["level_meter"].AsBool = LevelMeter.val;
            return mic;
        }

        /// <summary>Seeds the menu from config.json's "mic" object (missing keys keep their value).</summary>
        public void ApplyMicJson(JSONClass mic)
        {
            if (mic == null) return;
            Enabled.val = Protocol.GetBool(mic, "enabled", Enabled.val);
            if (Protocol.Has(mic, "mode")) Mode.val = Protocol.GetString(mic, "mode", "vad") == "ptt" ? ModePtt : ModeVad;
            Threshold.val = Protocol.GetFloat(mic, "vad_threshold", Threshold.val);
            if (Protocol.Has(mic, "vad_engine"))
            {
                string engine = Protocol.GetString(mic, "vad_engine", "auto");
                VadEngine.val = engine == "energy" ? VadBuiltIn : engine == "webrtc" ? VadWebRtc : engine == "silero" ? VadSilero : VadAuto;
            }
            VadStrictness.val = Protocol.GetFloat(mic, "vad_strictness", VadStrictness.val);
            SilenceMs.val = Protocol.GetFloat(mic, "end_silence_ms", SilenceMs.val);
            MinUtteranceMs.val = Protocol.GetFloat(mic, "min_utterance_ms", MinUtteranceMs.val);
            MaxUtteranceMs.val = Protocol.GetFloat(mic, "max_utterance_ms", MaxUtteranceMs.val);
            EchoTail.val = Protocol.GetFloat(mic, "echo_tail_s", EchoTail.val);
            Gain.val = Protocol.GetFloat(mic, "gain", Gain.val);
            PttInterrupts.val = Protocol.GetBool(mic, "ptt_interrupts", PttInterrupts.val);
            LevelMeter.val = Protocol.GetBool(mic, "level_meter", LevelMeter.val);
            MarkDirty();
        }

        private void SendConfig()
        {
            _dirty = false;
            _ackText = "sending settings...";
            _send(BuildConfigEvent());
        }

        private void SendPtt(bool active)
        {
            JSONClass evt = Protocol.NewEvent(Protocol.EvtPtt);
            evt["active"].AsBool = active;
            _send(evt);
        }

        // ------------------------------------------------------------------ incoming

        public void HandleMicState(JSONClass msg)
        {
            string text = Protocol.GetBool(msg, "capturing", false) ? "capturing" : "not capturing";
            text += " | microphone: system default input";
            text += " | mode: " + Protocol.GetString(msg, "mode", "?");
            string vad = Protocol.GetString(msg, "vad", "");
            if (vad.Length > 0) text += "\nVoice detection: " + vad;
            string vadNote = Protocol.GetString(msg, "vad_note", "");
            if (vadNote.Length > 0) text += "\nNote: " + vadNote;
            if (Protocol.GetBool(msg, "ptt_active", false)) text += " | TALKING (PTT)";
            string error = Protocol.GetString(msg, "error", "");
            if (error.Length > 0) text += "\nError: " + error;
            _micState = text;
        }

        public void HandleConfigAck(JSONClass msg)
        {
            JSONArray errors = msg["errors"] as JSONArray;
            if (errors == null || errors.Count == 0) _ackText = "settings applied";
            else
            {
                List<string> list = new List<string>();
                for (int i = 0; i < errors.Count; i++) list.Add(errors[i].Value);
                _ackText = "companion app rejected: " + string.Join("; ", list.ToArray());
            }
            JSONClass state = msg["mic_state"] as JSONClass;
            if (state != null) HandleMicState(state);
        }

        /// <summary>True while the companion reports the user's voice (needs the level meter; a second of grace).</summary>
        public bool UserSpeaking { get { return _speechAge < 1f; } }

        public void HandleMicLevel(JSONClass msg)
        {
            _levelAge = 0f;
            float rms = Protocol.GetFloat(msg, "rms", 0f);
            bool speech = Protocol.GetBool(msg, "speech", false);
            if (speech) _speechAge = 0f;
            bool gateOpen = Protocol.GetBool(msg, "gate_open", true);
            _levelText = LevelBar(rms, Threshold.val) + (speech ? "  SPEECH" : "") + (gateOpen ? "" : "  (muted: body speaking)");
        }

        /// <summary>Text level meter on a -60..0 dBFS scale; '!' marks the VAD threshold.</summary>
        public static string LevelBar(float rms, float threshold)
        {
            const int width = 30;
            int level = DbToCells(rms, width);
            int mark = DbToCells(threshold, width);
            char[] cells = new char[width];
            for (int i = 0; i < width; i++) cells[i] = i < level ? '|' : '.';
            if (mark >= 0 && mark < width) cells[mark] = '!';
            return "[" + new string(cells) + "] " + (rms > 0f ? (20f * Mathf.Log10(rms)).ToString("0") : "-inf") + " dB";
        }

        private static int DbToCells(float rms, int width)
        {
            if (rms <= 0f) return 0;
            float db = 20f * Mathf.Log10(rms);
            return Mathf.Clamp(Mathf.RoundToInt((db + 60f) / 60f * width), 0, width);
        }

        private void RefreshStatus()
        {
            string text = (_appHint.Length > 0 ? _appHint + "\n" : "") + "Mic: " + _micState;
            if (_ackText.Length > 0) text += "\nSettings: " + _ackText;
            if (LevelMeter.val)
            {
                text += "\nLevel: " + (_levelAge < 2f ? _levelText : "(no level data)");
            }
            if (_status.val != text) _status.val = text;
        }

        public void OnDisconnected()
        {
            _micState = "unknown (companion app not connected)";
            _levelText = "";
        }
    }
}
