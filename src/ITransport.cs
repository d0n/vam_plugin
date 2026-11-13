// Transport abstraction between the plugin and the companion app.
using System;
using SimpleJSON;

namespace AIBody
{
    public interface ITransport
    {
        string Name { get; }

        /// <summary>True when the last poll succeeded (file transport: folders are usable).</summary>
        bool IsConnected { get; }

        /// <summary>Last error text, or empty.</summary>
        string LastError { get; }

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
