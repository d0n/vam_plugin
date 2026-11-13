// OPTIONAL: only compiled in the AIBODY_HTTP build. Not listed in the default .cslist files,
// because VaM 1.22 may refuse to load plugins that reference UnityEngine.Networking.
// To enable: add "#define AIBODY_HTTP" as the first line of Session/AIBodySession.cs and
// Person/SpeechPlayer.cs and add Optional/*.cs to AIBodySession.cslist.
#if AIBODY_HTTP
// HTTP transport against the companion's local HTTP server (primary transport).
//
// Needs "Allow Plugins Network Access" in VaM's security settings (off by default).
// Raw sockets and WebSockets are not usable from the plugin sandbox / Unity 2018.1 Mono,
// so this uses UnityWebRequest only:
//   - long-poll for commands (the server holds the request until a command arrives or
//     `wait` seconds pass), so latency is near zero without hammering the server
//   - batched POSTs for events
//   - hello handshake with a server session id; a changed session id means the companion
//     restarted, which bumps ConnectionEpoch so the plugin re-sends ready + config
//   - exponential backoff with jitter on any failure, then a fresh hello
// TODO(verify): on VaM 1.22 confirm UnityWebRequest to 127.0.0.1 works with network access
// enabled and fails cleanly (isNetworkError) when it is disabled.
//
// Endpoints (see protocol/PROTOCOL.md):
//   GET  {base}/v1/hello?channel=<c>&plugin=<version>        -> {"session": "...", "protocol": 1, ...}
//   GET  {base}/v1/commands?channel=<c>&after=<seq>&wait=<s> -> {"commands":[...], "last": <seq>, "session": "..."}
//   POST {base}/v1/events?channel=<c>                        body: JSON array of events
//   GET  {base}/v1/audio/<file>                              speech audio (used by SpeechPlayer)
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
        private enum Phase { Stopped, Connecting, Connected, Backoff }

        private const int MaxQueuedEvents = 500;
        private const int MaxBatch = 50;
        private const float BaseBackoff = 0.5f;
        private const float MaxBackoff = 10f;

        private readonly MonoBehaviour _host;
        private readonly string _baseUrl;
        private readonly string _channel;
        private readonly string _pluginVersion;
        private readonly PayloadHandler _onPayload;

        private Phase _phase = Phase.Stopped;
        private int _generation;
        private long _lastSeq;
        private string _session;
        private int _epoch;
        private int _failures;
        private float _backoffRemaining;
        private string _lastError = "";
        private readonly List<string> _outQueue = new List<string>();
        private bool _pollInFlight;
        private bool _sendInFlight;
        private UnityWebRequest _pollRequest;
        private float _connectedFor;
        private int _reconnects;

        /// <summary>Seconds the server may hold a command poll open.</summary>
        public int LongPollSeconds = 10;

        public HttpTransport(MonoBehaviour host, string hostName, int port, string channel, string pluginVersion,
            PayloadHandler onPayload)
        {
            _host = host;
            _baseUrl = "http://" + (string.IsNullOrEmpty(hostName) ? "127.0.0.1" : hostName.Trim()) + ":" + port;
            _channel = channel;
            _pluginVersion = pluginVersion;
            _onPayload = onPayload;
        }

        public string Name { get { return "http"; } }
        public bool IsConnected { get { return _phase == Phase.Connected; } }
        public string LastError { get { return _lastError; } }
        public int ConnectionEpoch { get { return _epoch; } }
        public string HttpBaseUrl { get { return IsConnected ? _baseUrl : null; } }
        public string BaseUrl { get { return _baseUrl; } }

        public string State
        {
            get
            {
                switch (_phase)
                {
                    case Phase.Connected: return "connected to " + _baseUrl + " (" + Mathf.FloorToInt(_connectedFor) + "s)";
                    case Phase.Connecting: return "connecting to " + _baseUrl + "...";
                    case Phase.Backoff: return "retry in " + _backoffRemaining.ToString("0.0") + "s (attempt " + (_failures + 1) + ")";
                    default: return "stopped";
                }
            }
        }

        public void Start()
        {
            _generation++;
            _failures = 0;
            _pollInFlight = false;
            _sendInFlight = false;
            BeginConnect();
        }

        public void Stop()
        {
            _generation++;
            AbortPoll();
            _phase = Phase.Stopped;
            _pollInFlight = false;
            _sendInFlight = false;
            _outQueue.Clear();
        }

        public void Tick(float deltaTime)
        {
            switch (_phase)
            {
                case Phase.Backoff:
                    _backoffRemaining -= deltaTime;
                    if (_backoffRemaining <= 0f) BeginConnect();
                    break;
                case Phase.Connected:
                    _connectedFor += deltaTime;
                    if (!_pollInFlight) _host.StartCoroutine(PollRoutine(_generation));
                    if (!_sendInFlight && _outQueue.Count > 0) _host.StartCoroutine(SendRoutine(_generation));
                    break;
            }
        }

        public void Send(JSONClass evt)
        {
            if (_phase == Phase.Stopped || evt == null) return;
            if (_outQueue.Count >= MaxQueuedEvents) _outQueue.RemoveAt(0);
            _outQueue.Add(evt.ToString());
        }

        // ------------------------------------------------------------------ internals

        private string Url(string path)
        {
            return _baseUrl + path + (path.IndexOf('?') >= 0 ? "&" : "?") + "channel=" + UnityWebRequest.EscapeURL(_channel);
        }

        private void BeginConnect()
        {
            _phase = Phase.Connecting;
            _host.StartCoroutine(HelloRoutine(_generation));
        }

        private void Fail(string message)
        {
            _lastError = message;
            _failures++;
            _generation++; // invalidates every coroutine of the old connection
            AbortPoll();
            _pollInFlight = false;
            _sendInFlight = false;
            float delay = Mathf.Min(MaxBackoff, BaseBackoff * Mathf.Pow(2f, Mathf.Min(_failures - 1, 6)));
            _backoffRemaining = delay * UnityEngine.Random.Range(0.8f, 1.2f);
            if (_phase == Phase.Connected) Log.Info("Lost connection to companion: " + message);
            _phase = Phase.Backoff;
        }

        private void AbortPoll()
        {
            if (_pollRequest == null) return;
            try { _pollRequest.Abort(); } catch (Exception) { }
            _pollRequest = null;
        }

        private static bool Failed(UnityWebRequest req)
        {
            return req.isNetworkError || req.isHttpError;
        }

        private static string Describe(UnityWebRequest req)
        {
            string text = req.error ?? "unknown error";
            if (req.isNetworkError) text += " (is the companion running and 'Allow Plugins Network Access' enabled?)";
            return text;
        }

        private IEnumerator HelloRoutine(int gen)
        {
            UnityWebRequest req = UnityWebRequest.Get(Url("/v1/hello?plugin=" + UnityWebRequest.EscapeURL(_pluginVersion)));
            req.timeout = 5;
            yield return req.SendWebRequest();
            try
            {
                if (gen != _generation) yield break;
                if (Failed(req))
                {
                    Fail("hello failed: " + Describe(req));
                    yield break;
                }
                JSONClass root = JSON.Parse(req.downloadHandler.text) as JSONClass;
                if (root == null || !Protocol.Has(root, "session"))
                {
                    Fail("hello: unexpected response (is something else listening on " + _baseUrl + "?)");
                    yield break;
                }
                if (root["protocol"].AsInt != Protocol.Version)
                {
                    Log.Error("Companion speaks protocol " + root["protocol"].Value + ", plugin " + Protocol.Version);
                }
                AdoptSession(root["session"].Value);
                // Anything queued while offline is stale; the plugin re-sends ready + config.
                _outQueue.Clear();
                _phase = Phase.Connected;
                _connectedFor = 0f;
                _failures = 0;
                _lastError = "";
                _reconnects++;
                _epoch++;
                Log.Info("Connected to companion at " + _baseUrl + " (session " + _session + ")");
            }
            finally
            {
                req.Dispose();
            }
        }

        private void AdoptSession(string session)
        {
            if (session == _session) return;
            _session = session;
            _lastSeq = 0; // sequence numbers restart with every companion session
        }

        private IEnumerator PollRoutine(int gen)
        {
            _pollInFlight = true;
            UnityWebRequest req = UnityWebRequest.Get(Url("/v1/commands?after=" + _lastSeq + "&wait=" + LongPollSeconds));
            req.timeout = LongPollSeconds + 5;
            _pollRequest = req;
            yield return req.SendWebRequest();
            try
            {
                if (gen != _generation) yield break;
                _pollRequest = null;
                _pollInFlight = false;
                if (Failed(req))
                {
                    Fail("poll failed: " + Describe(req));
                    yield break;
                }
                HandlePollResponse(req.downloadHandler.text);
            }
            finally
            {
                req.Dispose();
            }
        }

        private void HandlePollResponse(string body)
        {
            JSONClass root = JSON.Parse(body) as JSONClass;
            if (root == null)
            {
                Fail("poll: invalid JSON from companion");
                return;
            }
            if (Protocol.Has(root, "session") && root["session"].Value != _session)
            {
                // Companion restarted without us noticing a failed request.
                AdoptSession(root["session"].Value);
                _epoch++;
            }
            long last;
            if (Protocol.Has(root, "last") && long.TryParse(root["last"].Value, out last)) _lastSeq = last;
            JSONArray commands = root["commands"] as JSONArray;
            if (commands != null && commands.Count > 0 && _onPayload != null) _onPayload(commands.ToString());
        }

        private IEnumerator SendRoutine(int gen)
        {
            _sendInFlight = true;
            int count = Math.Min(MaxBatch, _outQueue.Count);
            List<string> batch = _outQueue.GetRange(0, count);
            _outQueue.RemoveRange(0, count);

            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < batch.Count; i++)
            {
                if (i > 0) sb.Append(',');
                sb.Append(batch[i]);
            }
            sb.Append(']');

            UnityWebRequest req = new UnityWebRequest(Url("/v1/events"), "POST");
            req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(sb.ToString()));
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            req.timeout = 5;
            yield return req.SendWebRequest();
            try
            {
                if (gen != _generation) yield break;
                _sendInFlight = false;
                if (Failed(req))
                {
                    // Put the batch back so it is not lost if the connection recovers quickly.
                    _outQueue.InsertRange(0, batch);
                    Fail("event post failed: " + Describe(req));
                }
            }
            finally
            {
                req.Dispose();
            }
        }
    }
}
#endif
