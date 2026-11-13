// File based transport. Works without "Allow Plugins Network Access".
//
// Layout (relative to the VaM install folder):
//   Saves/PluginData/AIBody/<channel>/inbox/   companion -> plugin, one *.json file per message
//   Saves/PluginData/AIBody/<channel>/outbox/  plugin -> companion, one *.json file per event
//   Saves/PluginData/AIBody/<channel>/audio/   TTS audio written by the companion
//
// The companion writes atomically (write "name.tmp", then rename to "name.json"), so the
// plugin never sees half written JSON. The plugin cannot rename through FileManagerSecure,
// so it writes in place and the companion retries fresh files that fail to parse.
// Readers delete files after processing.
// File names must sort in send order (zero padded sequence number or timestamp first).
//
// All file access goes through FileManagerSecure because System.IO is blocked by the
// VaM plugin sandbox. Writes are only allowed below Saves/PluginData (and Custom/PluginData).
using System;
using System.Collections.Generic;
using SimpleJSON;
using MVR.FileManagementSecure;

namespace AIBody
{
    public class FileTransport : ITransport
    {
        private readonly string _inbox;
        private readonly string _outbox;
        private readonly PayloadHandler _onPayload;
        private float _pollInterval;
        private float _timer;
        private int _outCounter;
        private bool _running;
        private bool _connected;
        private string _lastError = "";

        public FileTransport(string channelDir, float pollInterval, PayloadHandler onPayload)
        {
            _inbox = channelDir + "/inbox";
            _outbox = channelDir + "/outbox";
            _pollInterval = pollInterval;
            _onPayload = onPayload;
        }

        public string Name { get { return "file"; } }
        public bool IsConnected { get { return _connected; } }
        public string LastError { get { return _lastError; } }

        public float PollInterval
        {
            get { return _pollInterval; }
            set { _pollInterval = Math.Max(0.02f, value); }
        }

        public void Start()
        {
            try
            {
                FileManagerSecure.CreateDirectory(_inbox);
                FileManagerSecure.CreateDirectory(_outbox);
                _running = true;
                _connected = true;
                _lastError = "";
            }
            catch (Exception e)
            {
                _connected = false;
                _lastError = "Cannot create transport folders: " + e.Message;
                Log.Error(_lastError);
            }
        }

        public void Stop()
        {
            _running = false;
            _connected = false;
        }

        public void Tick(float deltaTime)
        {
            if (!_running) return;
            _timer += deltaTime;
            if (_timer < _pollInterval) return;
            _timer = 0f;
            Poll();
        }

        private void Poll()
        {
            string[] files;
            try
            {
                // TODO(verify): FileManagerSecure.GetFiles(dir, pattern) returns paths usable by
                // ReadAllText/DeleteFile. Confirmed usage in community plugins, but check on 1.22.
                files = FileManagerSecure.GetFiles(_inbox, "*.json");
            }
            catch (Exception e)
            {
                _connected = false;
                _lastError = "Inbox poll failed: " + e.Message;
                return;
            }

            _connected = true;
            if (files == null || files.Length == 0) return;
            Array.Sort(files, StringComparer.Ordinal);

            for (int i = 0; i < files.Length; i++)
            {
                string path = files[i];
                string text = null;
                try
                {
                    text = FileManagerSecure.ReadAllText(path);
                }
                catch (Exception e)
                {
                    // Most likely still being written; try again next poll.
                    Log.Debug("Could not read " + path + ": " + e.Message);
                    continue;
                }

                try
                {
                    FileManagerSecure.DeleteFile(path);
                }
                catch (Exception e)
                {
                    _lastError = "Could not delete processed inbox file " + path + ": " + e.Message;
                    Log.Error(_lastError);
                }

                if (_onPayload != null) _onPayload(text);
            }
        }

        public void Send(JSONClass evt)
        {
            if (!_running || evt == null) return;
            try
            {
                _outCounter++;
                string name = DateTime.UtcNow.Ticks.ToString("D20") + "_" + _outCounter.ToString("D6");
                // FileManagerSecure has no rename/move we can rely on, so the file is written in
                // place. The companion treats unparseable, very fresh files as "still being
                // written" and retries them on its next poll.
                FileManagerSecure.WriteAllText(_outbox + "/" + name + ".json", evt.ToString());
            }
            catch (Exception e)
            {
                _lastError = "Outbox write failed: " + e.Message;
                Log.Error(_lastError);
            }
        }
    }
}
