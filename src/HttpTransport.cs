// HTTP polling transport against the companion's local HTTP server.
//
// Only works when the user enabled "Allow Plugins Network Access" in VaM's security
// settings (off by default). Raw sockets are not available to plugins; we only use
// UnityWebRequest, which is what that setting unlocks.
// TODO(verify): confirm on VaM 1.22 that UnityWebRequest to 127.0.0.1 works with the
// setting on, and fails cleanly (isNetworkError) with it off.
//
// Endpoints (see protocol/PROTOCOL.md):
//   GET  {base}/v1/commands?channel=<channel>&after=<seq>  -> {"commands":[...], "last": <seq>}
//   POST {base}/v1/events?channel=<channel>               body: one event object
using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using SimpleJSON;
using UnityEngine;
using UnityEngine.Networking;

namespace AIBody
{
    public class HttpTransport : ITransport
    {
        private readonly MonoBehaviour _host;
        private readonly string _baseUrl;
        private readonly string _channel;
        private readonly PayloadHandler _onPayload;
        private float _pollInterval;
        private float _timer;
        private bool _running;
        private bool _pollInFlight;
        private bool _connected;
        private string _lastError = "";
        private long _lastSeq;
        private readonly Queue<string> _outQueue = new Queue<string>();
        private bool _sendInFlight;
        private const int MaxQueuedEvents = 200;

        public HttpTransport(MonoBehaviour host, string baseUrl, string channel, float pollInterval, PayloadHandler onPayload)
        {
            _host = host;
            _baseUrl = (baseUrl ?? "").TrimEnd('/');
            _channel = channel;
            _pollInterval = pollInterval;
            _onPayload = onPayload;
        }

        public string Name { get { return "http"; } }
        public bool IsConnected { get { return _connected; } }
        public string LastError { get { return _lastError; } }

        public float PollInterval
        {
            get { return _pollInterval; }
            set { _pollInterval = Math.Max(0.05f, value); }
        }

        public void Start()
        {
            _running = true;
            _lastSeq = 0;
        }

        public void Stop()
        {
            _running = false;
            _connected = false;
            _outQueue.Clear();
        }

        public void Tick(float deltaTime)
        {
            if (!_running) return;
            _timer += deltaTime;
            if (_timer >= _pollInterval && !_pollInFlight)
            {
                _timer = 0f;
                _host.StartCoroutine(PollRoutine());
            }
            if (!_sendInFlight && _outQueue.Count > 0)
            {
                _host.StartCoroutine(SendRoutine(_outQueue.Dequeue()));
            }
        }

        public void Send(JSONClass evt)
        {
            if (!_running || evt == null) return;
            if (_outQueue.Count >= MaxQueuedEvents) _outQueue.Dequeue();
            _outQueue.Enqueue(evt.ToString());
        }

        private string Url(string path)
        {
            return _baseUrl + path + (path.IndexOf('?') >= 0 ? "&" : "?") + "channel=" + UnityWebRequest.EscapeURL(_channel);
        }

        private IEnumerator PollRoutine()
        {
            _pollInFlight = true;
            UnityWebRequest req = UnityWebRequest.Get(Url("/v1/commands?after=" + _lastSeq));
            req.timeout = 5;
            yield return req.SendWebRequest();

            try
            {
                if (!_running) yield break;
                if (req.isNetworkError || req.isHttpError)
                {
                    _connected = false;
                    _lastError = "Poll failed: " + req.error + " (is the companion running and network access allowed?)";
                }
                else
                {
                    _connected = true;
                    _lastError = "";
                    HandlePollResponse(req.downloadHandler.text);
                }
            }
            finally
            {
                req.Dispose();
                _pollInFlight = false;
            }
        }

        private void HandlePollResponse(string body)
        {
            JSONClass root = JSON.Parse(body) as JSONClass;
            if (root == null) return;
            JSONArray commands = root["commands"] as JSONArray;
            if (Protocol.Has(root, "last"))
            {
                long last;
                if (long.TryParse(root["last"].Value, out last)) _lastSeq = last;
            }
            if (commands == null || commands.Count == 0) return;
            if (_onPayload != null) _onPayload(commands.ToString());
        }

        private IEnumerator SendRoutine(string json)
        {
            _sendInFlight = true;
            UnityWebRequest req = new UnityWebRequest(Url("/v1/events"), "POST");
            req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            req.timeout = 5;
            yield return req.SendWebRequest();

            if (req.isNetworkError || req.isHttpError)
            {
                _connected = false;
                _lastError = "Event post failed: " + req.error;
            }
            req.Dispose();
            _sendInFlight = false;
        }
    }
}
