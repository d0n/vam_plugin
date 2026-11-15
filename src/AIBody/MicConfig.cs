// Microphone settings menu. The microphone itself is captured by the companion app (the plugin
// sandbox cannot load audio libraries and Unity's Microphone class is unverified inside VaM),
// so this class only holds the settings, shows feedback and talks to the companion app:
//   plugin -> companion app: "config" (all mic settings), "ptt" (push-to-talk state), "list_devices"
//   companion app -> plugin: "config_ack", "devices", "mic_state", "mic_level"
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
        public const string DefaultDevice = "(system default)";

        private readonly MVRScript _plugin;
        private readonly Action<JSONClass> _send;

        public JSONStorableBool Enabled;
        public JSONStorableStringChooser Mode;
        public JSONStorableStringChooser Device;
        public JSONStorableFloat Threshold;
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
        private JSONStorableString _status;

        private bool _dirty;
        private float _sinceChange;
        private string _micState = "unknown (companion app not connected)";
        private string _ackText = "";
        private string _levelText = "";
        private float _levelAge = 999f;

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
            Device = new JSONStorableStringChooser("Mic device", new List<string> { DefaultDevice }, DefaultDevice,
                "Mic device", (string v) => MarkDirty());
            _plugin.RegisterStringChooser(Device);
            // RMS level (0..1) above which a frame counts as speech.
            Threshold = Reg(new JSONStorableFloat("VAD threshold", 0.01f, (float v) => MarkDirty(), 0.001f, 0.2f));
            SilenceMs = Reg(new JSONStorableFloat("Silence timeout (ms)", 700f, (float v) => MarkDirty(), 200f, 5000f));
            MinUtteranceMs = Reg(new JSONStorableFloat("Min utterance (ms)", 300f, (float v) => MarkDirty(), 100f, 5000f));
            MaxUtteranceMs = Reg(new JSONStorableFloat("Max utterance (ms)", 20000f, (float v) => MarkDirty(), 1000f, 60000f));
            EchoTail = Reg(new JSONStorableFloat("Echo gate tail (s)", 0.4f, (float v) => MarkDirty(), 0f, 3f));
            Gain = Reg(new JSONStorableFloat("Input gain", 1f, (float v) => MarkDirty(), 0.1f, 8f));
            PttInterrupts = Reg(new JSONStorableBool("Push-to-talk interrupts speech", true, (bool v) => MarkDirty()));
            LevelMeter = Reg(new JSONStorableBool("Show level meter", true, (bool v) => MarkDirty()));

            _pttActive = new JSONStorableBool("Push-to-talk active", false, (bool v) => SendPtt(v));
            _status = new JSONStorableString("Mic status", "");

            _plugin.RegisterAction(new JSONStorableAction("Push-to-talk start", () => _pttActive.val = true));
            _plugin.RegisterAction(new JSONStorableAction("Push-to-talk stop", () => _pttActive.val = false));
            _plugin.RegisterAction(new JSONStorableAction("Push-to-talk toggle", () => _pttActive.val = !_pttActive.val));
            _plugin.RegisterAction(new JSONStorableAction("Refresh mic devices", RequestDevices));
        }

        private JSONStorableBool Reg(JSONStorableBool p) { _plugin.RegisterBool(p); return p; }
        private JSONStorableFloat Reg(JSONStorableFloat p) { _plugin.RegisterFloat(p); return p; }

        /// <summary>The "Mikrofon &amp; PTT" tab.</summary>
        public void BuildTab(UiPage page)
        {
            page.Toggle(Enabled);
            page.Popup(Mode);
            page.Popup(Device);
            page.Button("Refresh device list", RequestDevices);
            page.Toggle(_pttActive);
            page.Toggle(PttInterrupts);
            page.Text(_status, 160f);
            page.Toggle(LevelMeter);
            page.Slider(Threshold);
            page.Slider(Gain);
            page.Slider(SilenceMs);
            page.Slider(MinUtteranceMs);
            page.Slider(MaxUtteranceMs);
            page.Slider(EchoTail);
        }

        public void MarkDirty()
        {
            _dirty = true;
            _sinceChange = 0f;
        }

        /// <summary>Called on every (re)connect: push settings and ask for devices.</summary>
        public void OnConnected()
        {
            SendConfig();
            RequestDevices();
            if (PttActive) SendPtt(true);
        }

        public void Update(float deltaTime, bool connected)
        {
            _sinceChange += deltaTime;
            _levelAge += deltaTime;
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
            mic["device"] = Device.val == DefaultDevice ? "" : Device.val;
            mic["vad_threshold"].AsFloat = Threshold.val;
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
            if (Protocol.Has(mic, "device"))
            {
                string device = Protocol.GetString(mic, "device", "");
                Device.val = device.Length > 0 ? device : DefaultDevice;
            }
            Threshold.val = Protocol.GetFloat(mic, "vad_threshold", Threshold.val);
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

        public void RequestDevices()
        {
            _send(Protocol.NewEvent(Protocol.EvtListDevices));
        }

        // ------------------------------------------------------------------ incoming

        public void HandleDevices(JSONClass msg)
        {
            List<string> choices = new List<string> { DefaultDevice };
            JSONArray devices = msg["devices"] as JSONArray;
            if (devices != null)
            {
                for (int i = 0; i < devices.Count; i++)
                {
                    JSONClass d = devices[i] as JSONClass;
                    string name = d != null ? d["name"].Value : devices[i].Value;
                    if (!string.IsNullOrEmpty(name) && !choices.Contains(name)) choices.Add(name);
                }
            }
            // Keep a saved device visible even if it is currently unplugged.
            if (!choices.Contains(Device.val)) choices.Add(Device.val);
            // TODO(verify): JSONStorableStringChooser.choices is settable and refreshes the popup.
            Device.choices = choices;
        }

        public void HandleMicState(JSONClass msg)
        {
            string text = Protocol.GetBool(msg, "capturing", false) ? "capturing" : "not capturing";
            string device = Protocol.GetString(msg, "device", "");
            text += " | device: " + (device.Length > 0 ? device : "default");
            text += " | mode: " + Protocol.GetString(msg, "mode", "?");
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

        public void HandleMicLevel(JSONClass msg)
        {
            _levelAge = 0f;
            float rms = Protocol.GetFloat(msg, "rms", 0f);
            bool speech = Protocol.GetBool(msg, "speech", false);
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
            string text = "Mic: " + _micState;
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
