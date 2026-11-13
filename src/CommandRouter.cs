// Dispatches parsed commands to the controllers and answers with ack / error events.
using System;
using System.Collections.Generic;
using SimpleJSON;

namespace AIBody
{
    public class CommandRouter
    {
        private readonly Action<JSONClass> _send;
        private readonly AudioController _audio;
        private readonly ExpressionController _expressions;
        private readonly PoseController _poses;
        private readonly IdleController _idle;
        private readonly BreathingController _breathing;
        private readonly StateReporter _state;
        private readonly Func<JSONClass> _statusProvider;

        /// <summary>Send an "ack" for every successful command (useful while debugging).</summary>
        public bool AckAll = false;

        public CommandRouter(Action<JSONClass> send, AudioController audio, ExpressionController expressions,
            PoseController poses, IdleController idle, BreathingController breathing, StateReporter state,
            Func<JSONClass> statusProvider)
        {
            _send = send;
            _audio = audio;
            _expressions = expressions;
            _poses = poses;
            _idle = idle;
            _breathing = breathing;
            _state = state;
            _statusProvider = statusProvider;
        }

        public void HandlePayload(string payload)
        {
            List<JSONClass> messages;
            try
            {
                messages = Protocol.ParseMessages(payload);
            }
            catch (Exception e)
            {
                _send(Protocol.NewError(null, "bad_json", e.Message));
                return;
            }
            if (messages.Count == 0)
            {
                _send(Protocol.NewError(null, "bad_json", "Payload contained no message objects"));
                return;
            }
            for (int i = 0; i < messages.Count; i++) Handle(messages[i]);
        }

        public void Handle(JSONClass msg)
        {
            string type = Protocol.GetString(msg, "type", "");
            string id = Protocol.GetString(msg, "id", "");
            string error;
            try
            {
                error = Dispatch(type, id, msg);
            }
            catch (Exception e)
            {
                Log.Error("Command '" + type + "' failed", e);
                error = "Exception: " + e.Message;
            }

            if (error != null)
            {
                _send(Protocol.NewError(id, "command_failed", error));
            }
            else if (AckAll || Protocol.GetBool(msg, "ack", false))
            {
                _send(Protocol.NewAck(id, type));
            }
        }

        // Returns null on success, else an error message.
        private string Dispatch(string type, string id, JSONClass msg)
        {
            switch (type)
            {
                case Protocol.CmdPing:
                {
                    JSONClass pong = _statusProvider();
                    pong["type"] = Protocol.EvtPong;
                    pong["reply_to"] = id;
                    _send(pong);
                    return null;
                }

                case Protocol.CmdSpeak:
                {
                    string audio = Protocol.GetString(msg, "audio", "");
                    if (audio.Length == 0) return "speak needs 'audio' (file path relative to the VaM folder)";
                    string utteranceId = id.Length > 0 ? id : "utt-" + DateTime.UtcNow.Ticks;
                    if (Protocol.Has(msg, "expression"))
                    {
                        _expressions.SetExpression(Protocol.GetString(msg, "expression", ""),
                            Protocol.GetFloat(msg, "intensity", 1f), 0.4f, -1f);
                    }
                    _audio.Play(utteranceId, audio, OnAudioError);
                    return null;
                }

                case Protocol.CmdStopSpeaking:
                    _state.NotifyStopRequested();
                    _audio.Stop();
                    return null;

                case Protocol.CmdExpression:
                {
                    string name = Protocol.GetString(msg, "name", "neutral");
                    bool ok = _expressions.SetExpression(name,
                        Protocol.GetFloat(msg, "intensity", 1f),
                        Protocol.GetFloat(msg, "blend", 0.4f),
                        Protocol.GetFloat(msg, "hold", -1f));
                    return ok ? null : "Unknown expression '" + name + "'";
                }

                case Protocol.CmdSetMorphs:
                {
                    JSONClass morphs = msg["morphs"] as JSONClass;
                    if (morphs == null) return "set_morphs needs a 'morphs' object";
                    List<string> missing = _expressions.SetMorphs(ExpressionController.ToFloatMap(morphs),
                        Protocol.GetFloat(msg, "blend", 0.3f), Protocol.GetBool(msg, "release_others", false));
                    return missing.Count == 0 ? null : "Morphs not found: " + string.Join(", ", missing.ToArray());
                }

                case Protocol.CmdResetMorphs:
                    _expressions.Reset(Protocol.GetFloat(msg, "blend", 0.4f));
                    return null;

                case Protocol.CmdGesture:
                    return _poses.PlayGesture(Protocol.GetString(msg, "name", ""),
                        Protocol.GetFloat(msg, "duration", 0f), Protocol.GetFloat(msg, "amplitude", 0f));

                case Protocol.CmdPose:
                    return _poses.LoadPose(Protocol.GetString(msg, "path", ""));

                case Protocol.CmdTrigger:
                    return _poses.Trigger(msg);

                case Protocol.CmdIdle:
                    _idle.Enabled = Protocol.GetBool(msg, "enabled", _idle.Enabled);
                    _idle.Intensity = Protocol.GetFloat(msg, "intensity", _idle.Intensity);
                    return null;

                case Protocol.CmdBreathing:
                    _breathing.Enabled = Protocol.GetBool(msg, "enabled", _breathing.Enabled);
                    _breathing.Rate = Protocol.GetFloat(msg, "rate", _breathing.Rate);
                    _breathing.Depth = Protocol.GetFloat(msg, "depth", _breathing.Depth);
                    return null;

                case "":
                    return "Message has no 'type'";

                default:
                    return "Unknown command type '" + type + "'";
            }
        }

        private void OnAudioError(string utteranceId, string message)
        {
            _send(Protocol.NewError(utteranceId, "audio_failed", message));
        }
    }
}
