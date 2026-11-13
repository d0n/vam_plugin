// "Auto" transport: HTTP is primary, the file transport is the fallback.
//
// Both run at the same time. Incoming commands are accepted from either (the companion only
// sends each command over one of them). Outgoing events go over HTTP while it is connected and
// through the shared folder otherwise. The inbox is polled more slowly while HTTP is up.
using System;
using SimpleJSON;

namespace AIBody
{
    public class AutoTransport : ITransport
    {
        private readonly HttpTransport _http;
        private readonly FileTransport _file;
        private readonly float _filePollFast;
        private int _epoch;
        private string _linkKey = "";

        public AutoTransport(HttpTransport http, FileTransport file)
        {
            _http = http;
            _file = file;
            _filePollFast = file.PollInterval;
        }

        public string Name { get { return "auto"; } }
        public bool IsConnected { get { return _http.IsConnected || _file.IsConnected; } }
        public int ConnectionEpoch { get { return _epoch; } }
        public string HttpBaseUrl { get { return _http.HttpBaseUrl; } }

        /// <summary>"http" or "file": where events currently go.</summary>
        public string ActiveLink { get { return _http.IsConnected ? "http" : "file"; } }

        public string State
        {
            get
            {
                return _http.IsConnected
                    ? "HTTP " + _http.State
                    : "file fallback (" + _file.State + "); HTTP " + _http.State;
            }
        }

        public string LastError
        {
            get { return !string.IsNullOrEmpty(_http.LastError) && !_http.IsConnected ? _http.LastError : _file.LastError; }
        }

        public void Start()
        {
            _file.Start();
            _http.Start();
        }

        public void Stop()
        {
            _http.Stop();
            _file.Stop();
        }

        public void Tick(float deltaTime)
        {
            _http.Tick(deltaTime);
            _file.PollInterval = _http.IsConnected ? Math.Max(0.5f, _filePollFast) : _filePollFast;
            _file.Tick(deltaTime);

            string key = _http.IsConnected ? "h" + _http.ConnectionEpoch : "f" + _file.ConnectionEpoch;
            if (key != _linkKey)
            {
                _linkKey = key;
                _epoch++;
            }
        }

        public void Send(JSONClass evt)
        {
            if (_http.IsConnected) _http.Send(evt);
            else _file.Send(evt);
        }
    }
}
