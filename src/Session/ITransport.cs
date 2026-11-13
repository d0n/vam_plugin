// Transport abstraction between the plugin and the companion app.
using System;
using SimpleJSON;

namespace AIBody
{
    public interface ITransport
    {
        /// <summary>"http", "file" or "auto".</summary>
        string Name { get; }

        /// <summary>True while the companion is reachable (file transport: folders are usable).</summary>
        bool IsConnected { get; }

        /// <summary>Human readable connection state for the status UI.</summary>
        string State { get; }

        /// <summary>Last error text, or empty.</summary>
        string LastError { get; }

        /// <summary>
        /// Incremented on every (re)connect, including a companion restart behind the same URL.
        /// The plugin re-sends "ready" and its configuration when this changes.
        /// </summary>
        int ConnectionEpoch { get; }

        /// <summary>
        /// Base URL of the companion's HTTP server while connected over HTTP (used to download
        /// audio), otherwise null.
        /// </summary>
        string HttpBaseUrl { get; }

        void Start();

        void Stop();

        /// <summary>Called every frame from the plugin's Update(). Implementations poll at their own rate.</summary>
        void Tick(float deltaTime);

        /// <summary>Sends one event to the companion. Must never throw.</summary>
        void Send(JSONClass evt);
    }

    /// <summary>Called for every raw payload (one JSON object or an array) the transport receives.</summary>
    public delegate void PayloadHandler(string payload);
}
