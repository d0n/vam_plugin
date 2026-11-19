// Loopback UDP link to the companion app (version 30). The ONLY file that touches System.Net.
//
// - Loopback only: the plugin binds an ephemeral port on 127.0.0.1 and talks to 127.0.0.1:<port> (default 38437,
//   config.json connection.network_port). There is no way to configure another address.
// - UDP, like VAMLaunch (UdpClient, background receive thread, locked queue drained in the main thread).
// - The main thread never blocks: a receiver thread and a sender thread own the socket; Tick() only moves
//   finished datagrams between the thread queues and the plugin (see docs/API_AUDIT.md, "Network").
// - One datagram = one complete JSON message, the same text the file channel carries. Datagrams of the link
//   itself (hello / hello_ack, key "net") never reach the plugin's message handler.
// - "Live" = a datagram from the companion app arrived within AliveTimeout seconds. While not live the plugin
//   sends a hello with a growing pause (1, 2, 4, 5 s ...): that is the reconnect backoff. The caller uses the file
//   channel whenever the link is not live.
using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace AIBody
{
    public class SocketLink
    {
        public const int DefaultPort = 38437;
        public const float AliveTimeout = 6f;      // no datagram from the companion app for this long: not live
        public const float ConnectGrace = 3f;      // "connecting" is shown for this long after the start
        public const float MaxHelloPause = 5f;
        public const int MaxDatagramBytes = 60000; // larger messages travel through the file channel
        private const int MaxQueued = 500;

        private readonly int _port;
        private readonly PayloadHandler _onPayload;
        private UdpClient _client;
        private IPEndPoint _server;
        private Thread _receiver;
        private Thread _sender;
        private volatile bool _running;
        private readonly Queue<string> _incoming = new Queue<string>();
        private readonly Queue<byte[]> _outgoing = new Queue<byte[]>();
        private readonly object _inLock = new object();
        private readonly object _outLock = new object();

        // Main thread only.
        private float _sinceHeard = 999f;
        private float _sinceStart;
        private float _helloTimer;
        private float _helloPause = 1f;
        private bool _live;
        private int _liveGains;
        private string _error = "";

        public SocketLink(int port, PayloadHandler onPayload)
        {
            _port = (port > 0 && port < 65536) ? port : DefaultPort;
            _onPayload = onPayload;
        }

        public int Port { get { return _port; } }
        public bool Live { get { return _live; } }

        /// <summary>Counts how often the link became live (the caller re-sends "ready" and the settings then).</summary>
        public int LiveGains { get { return _liveGains; } }

        /// <summary>True if the socket could not be created (for example VaM blocks plugin network access).</summary>
        public bool Blocked { get { return _client == null; } }

        public string Error { get { return _error; } }

        public string Status
        {
            get
            {
                if (_client == null) return "unavailable, using files";
                if (_live) return "connected";
                return _sinceStart < ConnectGrace ? "connecting ..." : "unavailable, using files";
            }
        }

        public void Start()
        {
            try
            {
                _client = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0));
                _server = new IPEndPoint(IPAddress.Loopback, _port);
                _running = true;
                _receiver = new Thread(ReceiveLoop);
                _receiver.IsBackground = true;
                _receiver.Start();
                _sender = new Thread(SendLoop);
                _sender.IsBackground = true;
                _sender.Start();
                _helloTimer = _helloPause;   // the first hello goes out on the first Tick
            }
            catch (Exception e)
            {
                _error = e.Message;
                CloseClient();
                _running = false;
                Log.Info("Network: could not open the socket (" + e.Message + "); using files. "
                    + "VaM only allows this with 'Allow Plugins Network Access' (VaM preferences, Security).");
            }
        }

        public void Stop()
        {
            _running = false;
            lock (_outLock) { Monitor.PulseAll(_outLock); }
            // The sender thread gets a moment to push a last queued datagram (the "shutdown" event).
            if (_sender != null && _sender.IsAlive) _sender.Join(30);
            CloseClient();
            _live = false;
        }

        private void CloseClient()
        {
            try { if (_client != null) _client.Close(); } catch (Exception) { }
            _client = null;
        }

        /// <summary>Called every frame: moves received messages to the plugin, tracks liveness, says hello.</summary>
        public void Tick(float dt)
        {
            if (_client == null) return;
            _sinceStart += dt;
            _sinceHeard += dt;

            string[] batch = null;
            lock (_inLock)
            {
                if (_incoming.Count > 0)
                {
                    batch = _incoming.ToArray();
                    _incoming.Clear();
                }
            }
            if (batch != null)
            {
                for (int i = 0; i < batch.Length; i++)
                {
                    _sinceHeard = 0f;
                    if (IsLinkDatagram(batch[i])) continue;
                    if (_onPayload != null) _onPayload(batch[i]);
                }
            }

            bool live = _sinceHeard < AliveTimeout;
            if (live && !_live)
            {
                _liveGains++;
                _helloPause = 1f;
                Log.Info("Network: connected to the companion app (127.0.0.1:" + _port + ")");
            }
            else if (!live && _live)
            {
                Log.Info("Network: the companion app stopped answering; using files until it answers again.");
            }
            _live = live;

            if (!live)
            {
                _helloTimer += dt;
                if (_helloTimer >= _helloPause)
                {
                    _helloTimer = 0f;
                    _helloPause = Math.Min(_helloPause * 2f, MaxHelloPause);
                    Enqueue("{\"net\":\"hello\",\"v\":3}");
                }
            }
        }

        /// <summary>Queues one message for the sender thread. False = not sent (not live or too large): use files.</summary>
        public bool Send(string text)
        {
            if (!_live || _client == null || text == null) return false;
            return Enqueue(text);
        }

        private bool Enqueue(string text)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(text);
            if (bytes.Length > MaxDatagramBytes) return false;
            lock (_outLock)
            {
                if (_outgoing.Count >= MaxQueued) _outgoing.Dequeue();
                _outgoing.Enqueue(bytes);
                Monitor.Pulse(_outLock);
            }
            return true;
        }

        private static bool IsLinkDatagram(string text)
        {
            return text.Length < 200 && text.IndexOf("\"net\"", StringComparison.Ordinal) >= 0;
        }

        // ---------------------------------------------------------------- threads (never call Unity or VaM here)

        private void ReceiveLoop()
        {
            IPEndPoint from = new IPEndPoint(IPAddress.Loopback, 0);
            while (_running)
            {
                try
                {
                    UdpClient client = _client;
                    if (client == null) return;
                    byte[] data = client.Receive(ref from);
                    if (from.Port != _port || !IPAddress.IsLoopback(from.Address)) continue;   // only the companion app
                    string text = Encoding.UTF8.GetString(data);
                    lock (_inLock)
                    {
                        if (_incoming.Count >= MaxQueued) _incoming.Dequeue();
                        _incoming.Enqueue(text);
                    }
                }
                catch (SocketException)
                {
                    // Closed socket (Stop) or a reset after a datagram to a port nobody listens on: carry on / leave.
                    if (!_running) return;
                    Thread.Sleep(5);
                }
                catch (ObjectDisposedException)
                {
                    return;
                }
                catch (Exception)
                {
                    if (!_running) return;
                    Thread.Sleep(5);
                }
            }
        }

        private void SendLoop()
        {
            while (true)
            {
                byte[] bytes = null;
                lock (_outLock)
                {
                    if (_outgoing.Count == 0)
                    {
                        if (!_running) return;
                        Monitor.Wait(_outLock, 500);
                    }
                    if (_outgoing.Count > 0) bytes = _outgoing.Dequeue();
                    else if (!_running) return;
                }
                if (bytes == null) continue;
                try
                {
                    UdpClient client = _client;
                    if (client != null) client.Send(bytes, bytes.Length, _server);
                }
                catch (Exception)
                {
                    // Nobody listening / socket closed: the liveness timeout switches the caller to files.
                }
            }
        }
    }
}
