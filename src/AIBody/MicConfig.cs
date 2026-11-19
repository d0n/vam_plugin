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

        /// <summary>Start command of the companion app, shown when it is not running.</summary>
        public const string StartHint = "python -m aibody_companion --vam-root \"D:\\VaM\"";

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
            _plugin.RegisterStringChooser(Mode);
            // RMS level (0..1) above which a frame counts as speech.
            Threshold = Reg(new JSONStorableFloat("VAD threshold", 0.01f, (float v) => MarkDirty(), 0.001f, 0.5f));
            // Voice detector: Auto = WebRTC if the companion app has it installed, else the built-in one.
            VadEngine = new JSONStorableStringChooser("VAD engine", new List<string> { VadAuto, VadBuiltIn, VadWebRtc, VadSilero }, VadAuto,
                "VAD engine", (string v) => MarkDirty());
            _plugin.RegisterStringChooser(VadEngine);
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
                "Push-to-talk active: while this is checked the companion app listens to your microphone, like holding the "
                + "talk button of a walkie-talkie. It only works when Mic mode is 'Push-to-talk'. "
                + "The microphone is always the system default input (change it in your system sound settings). "
                + "VAD engine: how speech is told from noise. 'Auto' uses Silero if its model file is installed (docs/TECHNIK.md), else WebRTC if the companion app has it (python -m pip install webrtcvad-wheels), "
                + "otherwise the built-in detector. VAD strictness 0-3: higher ignores more background noise. "
                + "VAD threshold is the quietest level that can count as speech. While the character talks (and a moment after) the microphone is muted on purpose, so the AI never hears itself. "
                + "You can also use the actions 'Push-to-talk start / stop / toggle' from triggers or keys.");

            _plugin.RegisterAction(new JSONStorableAction("Push-to-talk start", () => _pttActive.val = true));
            _plugin.RegisterAction(new JSONStorableAction("Push-to-talk stop", () => _pttActive.val = false));
            _plugin.RegisterAction(new JSONStorableAction("Push-to-talk toggle", () => _pttActive.val = !_pttActive.val));
        }

        private JSONStorableBool Reg(JSONStorableBool p) { _plugin.RegisterBool(p); return p; }
        private JSONStorableFloat Reg(JSONStorableFloat p) { _plugin.RegisterFloat(p); return p; }

        /// <summary>Microphone and push-to-talk controls of the tab Client Character.</summary>
        public void BuildTab(UiPage page)
        {
            page.Toggle(Enabled);
            page.Popup(Mode);
            page.Toggle(_pttActive);
            page.Toggle(PttInterrupts);
            page.Toggle(LevelMeter);
            page.Popup(VadEngine);
            page.Slider(Threshold);
            page.Slider(VadStrictness);
            page.Slider(Gain);
            page.Slider(SilenceMs);
            page.Slider(MinUtteranceMs);
            page.Slider(MaxUtteranceMs);
            page.Slider(EchoTail);
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

        public void Update(float deltaTime, bool connected, bool appRunning, bool linkActive)
        {
            _appRunning = appRunning;
            _linkActive = linkActive;
            _sinceChange += deltaTime;
            _levelAge += deltaTime;
            _speechAge += deltaTime;
            // The companion app is the only thing that listens: say plainly when it is not there.
            _appHint = !linkActive
                ? "<color=red>The link to the companion app is switched off. Turn on 'Active' in tab Voice.</color>"
                : !appRunning
                    ? "<color=red>Companion app not running, so nothing is heard or spoken. Start it in a console, in the 'companion' folder: " + StartHint + "</color>"
                    : "";
            // Debounce slider drags: send 0.3 s after the last change.
            if (_dirty && connected && _sinceChange > 0.3f) SendConfig();
            RefreshStatus();
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
