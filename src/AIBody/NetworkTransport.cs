// Network transport (version 30): the loopback socket (SocketLink) with the file channel (FileTransport) as the
// fallback. Used only while "Network Active" is on; with the toggle off AppLink uses FileTransport alone and none of
// the socket code runs.
//
// - Both channels are always polled, so nothing is lost when the app switches between them.
// - Sending: the socket while it is live, else the files. Messages that carry the token ("keys", the config event)
//   always go through the file channel, never over the socket; messages above one datagram do too.
// - The connection epoch also counts every time the socket became live, so the plugin re-sends "ready" and its
//   settings over the new path.
using System;
using SimpleJSON;

namespace AIBody
{
    public class NetworkTransport : ITransport
    {
        private readonly FileTransport _file;
        private readonly SocketLink _link;

        public NetworkTransport(FileTransport file, SocketLink link)
        {
            _file = file;
            _link = link;
        }

        public string Name { get { return _link.Live ? "socket" : "file"; } }
        public bool IsConnected { get { return _file.IsConnected || _link.Live; } }
        public string State { get { return _file.State; } }
        public string LastError { get { return _file.LastError; } }
        public int ConnectionEpoch { get { return _file.ConnectionEpoch + _link.LiveGains; } }

        /// <summary>Short status for the info field: "Network: connected" / "connecting ..." / "unavailable, using files".</summary>
        public string NetworkStatus { get { return "Network: " + _link.Status; } }

        public int Port { get { return _link.Port; } }

        public void Start()
        {
            _file.Start();
            _link.Start();
        }

        public void Stop()
        {
            _link.Stop();
            _file.Stop();
        }

        public void Tick(float deltaTime)
        {
            _file.Tick(deltaTime);
            _link.Tick(deltaTime);
        }

        public int PruneOutbox(int keep)
        {
            return _file.PruneOutbox(keep);
        }

        public void Send(JSONClass evt)
        {
            if (evt == null) return;
            if (_link.Live && !Protocol.Has(evt, "keys") && _link.Send(evt.ToString())) return;
            _file.Send(evt);
        }
    }
}
