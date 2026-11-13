// Session plugin: microphone settings menu. The microphone itself is captured by the companion (the plugin
// sandbox cannot load audio libraries and Unity's Microphone class is unverified inside VaM),
// so this class only holds the settings, shows feedback and talks to the companion:
//   plugin -> companion: "config" (all mic settings), "ptt" (push-to-talk state), "list_devices"
//   companion -> plugin: "config_ack", "devices", "mic_state", "mic_level"
// All settings are JSONStorables, so they are saved with the scene. Changes are sent to the
// companion (debounced) and applied there live.
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
        private string _micState = "unknown (companion not connected)";
        private string _ackText = "";
        private string _levelText = "";
        private float _levelAge = 999f;

        public MicConfig(MVRScript plugin, Action<JSONClass> send)
        {
            _plugin = plugin;
            _send = send;
        }

        /// <summary>Lets the Session plugin add more settings (engines) to every config event.</summary>
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

        public void CreateUI(bool rightSide)
        {
            UIDynamicTextField header = _plugin.CreateTextField(new JSONStorableString("mic header", "<b>Microphone</b> (captured by the companion)"), rightSide);
            header.height = 40f;
            _plugin.CreateToggle(Enabled, rightSide);
            _plugin.CreatePopup(Mode, rightSide);
            _plugin.CreatePopup(Device, rightSide);
            _plugin.CreateButton("Refresh device list", rightSide).button.onClick.AddListener(RequestDevices);
            _plugin.CreateToggle(_pttActive, rightSide);
            _plugin.CreateToggle(PttInterrupts, rightSide);
            UIDynamicTextField status = _plugin.CreateTextField(_status, rightSide);
            status.height = 160f;
            _plugin.CreateToggle(LevelMeter, rightSide);
            _plugin.CreateSlider(Threshold, rightSide);
            _plugin.CreateSlider(Gain, rightSide);
            _plugin.CreateSlider(SilenceMs, rightSide);
            _plugin.CreateSlider(MinUtteranceMs, rightSide);
            _plugin.CreateSlider(MaxUtteranceMs, rightSide);
            _plugin.CreateSlider(EchoTail, rightSide);
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
            evt["mic"] = mic;
            if (DecorateConfig != null) DecorateConfig(evt);
            return evt;
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
                _ackText = "companion rejected: " + string.Join("; ", list.ToArray());
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
            _micState = "unknown (companion not connected)";
            _levelText = "";
        }
    }
}
