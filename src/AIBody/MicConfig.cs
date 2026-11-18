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
        public const string DefaultDevice = MicDeviceList.DefaultChoice;   // saved value: "" in config.json

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
        private JSONStorableString _pttHelp;
        private JSONStorableString _status;

        private bool _dirty;
        private float _sinceChange;
        private string _micState = "unknown (companion app not connected)";
        private string _ackText = "";
        private string _levelText = "";
        private float _levelAge = 999f;
        private string _devicesText = "Mikrofon-Liste: noch keine Antwort (Companion-App starten)";
        private float _devicesAsked = -1f;      // seconds since the last list_devices, -1 = none pending
        private float _sinceDevicesAsked = 999f;
        // Diagnostics for the info field (version 16): what was asked, what came back, what the menu holds.
        private int _requests;
        private string _requestedAt = "";
        private string _receivedText = "";
        private string _defaultName = "";

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
            // Plain choices, no displayChoices (version 16, see MicDeviceList.cs). "Standard" is always in.
            Device = new JSONStorableStringChooser("Mic device", new List<string> { DefaultDevice }, DefaultDevice,
                "Mic device", (string v) => MarkDirty());
            // Opening the menu asks the companion app for the current list (Embody / Timeline pattern).
            Device.popupOpenCallback = RequestDevicesSoon;
            _plugin.RegisterStringChooser(Device);
            // RMS level (0..1) above which a frame counts as speech.
            Threshold = Reg(new JSONStorableFloat("VAD threshold", 0.01f, (float v) => MarkDirty(), 0.001f, 0.5f));
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
                "Push-to-talk active: solange angehakt, hört die Companion-App zu (wie eine gedrückte Funk-Taste). "
                + "Nur im Mic mode Push-to-talk. Per Trigger/Taste: Aktionen 'Push-to-talk start / stop / toggle'.");

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
            EnsureDeviceChoices();
            page.ScrollablePopup(Device);
            // Set the list once more on the popup that now exists (choices refresh a shown popup: E24, E25).
            Device.choices = new List<string>(Device.choices);
            page.Button("Mikrofone neu laden", RequestDevices);
            page.Toggle(_pttActive);
            page.Toggle(PttInterrupts);
            page.Toggle(LevelMeter);
            page.Slider(Threshold);
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
            _sinceDevicesAsked += deltaTime;
            // Scenes saved up to version 15 hold "(system default)": shown as "Standard" now.
            if (Device.val == MicDeviceList.LegacyDefault) Device.val = DefaultDevice;
            if (_devicesAsked >= 0f)
            {
                _devicesAsked += deltaTime;
                if (_devicesAsked > 5f)
                {
                    _devicesAsked = -1f;
                    _devicesText = connected
                        ? "<color=red>Mikrofon-Liste: keine Antwort der Companion-App</color> (Konsole prüfen)"
                        : "Mikrofon-Liste: Companion-App nicht verbunden - Liste kommt, sobald sie läuft";
                }
            }
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
            mic["device"] = MicDeviceList.ToConfig(Device.val);
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
                Device.val = MicDeviceList.ToChoice(Protocol.GetString(mic, "device", ""));
                EnsureDeviceChoices();
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
            _sinceDevicesAsked = 0f;
            _devicesAsked = 0f;
            _requests++;
            _requestedAt = DateTime.Now.ToString("HH:mm:ss");
            _devicesText = "Mikrofon-Liste: angefordert um " + _requestedAt + " (Anfrage " + _requests + ") ...";
            Log.Debug("list_devices gesendet");
            _send(Protocol.NewEvent(Protocol.EvtListDevices));
        }

        /// <summary>Menu opened: ask again unless a list was asked for in the last 2 s.</summary>
        private void RequestDevicesSoon()
        {
            if (_sinceDevicesAsked > 2f) RequestDevices();
        }

        // ------------------------------------------------------------------ incoming

        public void HandleDevices(JSONClass msg)
        {
            _devicesAsked = -1f;
            List<string> names = new List<string>();
            string api = "";
            _defaultName = "";
            JSONArray devices = msg["devices"] as JSONArray;
            int received = devices != null ? devices.Count : 0;
            if (devices != null)
            {
                for (int i = 0; i < devices.Count; i++)
                {
                    JSONClass d = devices[i] as JSONClass;
                    string name = d != null ? d["name"].Value : devices[i].Value;
                    names.Add(name);
                    if (d == null) continue;
                    if (api.Length == 0) api = d["hostapi"].Value;
                    if (_defaultName.Length == 0 && Protocol.GetBool(d, "default", false)) _defaultName = name;
                }
            }
            int found;
            bool missing;
            List<string> choices = MicDeviceList.Build(names, Device.val, out found, out missing);
            Device.choices = choices;   // refreshes a shown popup (E24, E25)
            if (MicDeviceList.IsDefault(Device.val) && Device.val != DefaultDevice) Device.val = DefaultDevice;
            string error = Protocol.GetString(msg, "error", "");
            _receivedText = "Mikrofon-Liste: " + received + " empfangen von der Companion-App"
                + (api.Length > 0 ? " (Host-API " + api + ")" : "") + " um " + DateTime.Now.ToString("HH:mm:ss")
                + (_requestedAt.Length > 0 ? ", angefordert " + _requestedAt : "")
                + (found != received ? ", davon " + found + " verwendbar" : "");
            _devicesText = found > 0
                ? _receivedText
                : "<color=red>" + _receivedText + (error.Length > 0 ? " - " + error : "") + "</color> (Standard bleibt wählbar)";
            if (missing) _devicesText += "\n<color=red>Gespeichertes Mikrofon nicht in der Liste: " + Device.val + "</color>";
            Log.Info("Mikrofon-Liste: " + received + " empfangen" + (api.Length > 0 ? " (" + api + ")" : "")
                + ", Menü hat " + Device.choices.Count + " Einträge" + (error.Length > 0 ? ", Fehler: " + error : ""));
        }

        /// <summary>Makes sure "Standard" and the current selection are in the menu (before any list arrived).</summary>
        private void EnsureDeviceChoices()
        {
            List<string> current = Device.choices != null ? Device.choices : new List<string>();
            List<string> names = new List<string>();
            for (int i = 0; i < current.Count; i++) names.Add(current[i]);
            int found;
            bool missing;
            List<string> choices = MicDeviceList.Build(names, Device.val, out found, out missing);
            if (choices.Count != current.Count || missing) Device.choices = choices;
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

        /// <summary>What the menu holds right now (read back from the chooser), for screenshots.</summary>
        private string MenuEntriesText()
        {
            List<string> choices = Device.choices;
            int count = choices != null ? choices.Count : 0;
            string text = "Menü Mic device: " + count + " Einträge" + (count > 0 ? ": " + string.Join(", ", choices.ToArray()) : "");
            text += "\nAuswahl: " + Device.val + (_defaultName.Length > 0 ? " | Windows-Standard: " + _defaultName : "");
            return text;
        }

        private void RefreshStatus()
        {
            string text = _devicesText + "\n" + MenuEntriesText() + "\nMic: " + _micState;
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
