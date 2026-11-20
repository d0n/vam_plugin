// Dispatches body commands (speak, expression, gesture, pose, ...) to the body controllers and
// answers with ack / error events. Called in-process by the plugin's Body component.
//
// Speech never depends on the body: a speak is queued first, its optional expression is applied
// afterwards and may fail on its own. With "Body control" off, expression / morph / gesture / pose /
// trigger commands are ignored (no error), so a plain question-and-answer flow only needs the head
// audio. Version 35: the companion's idle / breathing commands are body commands too, so with Body control off the
// AI / companion side cannot move the body at all (the plugin's own idle motion and breathing keep their own toggles).
// A controller that could not be created gives a clear error instead of an exception.
using System;
using System.Collections.Generic;
using SimpleJSON;

namespace AIBody
{
    public class CommandRouter
    {
        private readonly Action<JSONClass> _send;
        private readonly SpeechPlayer _speech;
        private readonly ExpressionController _expressions;
        private readonly PoseController _poses;
        private readonly IdleController _idle;
        private readonly BreathingController _breathing;

        private readonly Func<bool> _bodyControl;

        /// <summary>Send an "ack" for every successful command (useful while debugging).</summary>
        public bool AckAll = false;

        public CommandRouter(Action<JSONClass> send, SpeechPlayer speech, ExpressionController expressions,
            PoseController poses, IdleController idle, BreathingController breathing, Func<bool> bodyControl)
        {
            _bodyControl = bodyControl;
            _send = send;
            _speech = speech;
            _expressions = expressions;
            _poses = poses;
            _idle = idle;
            _breathing = breathing;
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
            if (type != Protocol.CmdPing)
                Log.Debug("Command " + type + " " + id + (Protocol.Has(msg, "audio") ? " audio=" + Protocol.GetString(msg, "audio", "") : ""));
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
                Log.Debug("Command " + type + " " + id + " failed: " + error);
                _send(Protocol.NewError(id, "command_failed", error));
            }
            else if (AckAll || Protocol.GetBool(msg, "ack", false))
            {
                _send(Protocol.NewAck(id, type));
            }
        }

        private bool BodyOn { get { return _bodyControl == null || _bodyControl(); } }

        private static bool IsBodyCommand(string type)
        {
            return type == Protocol.CmdExpression || type == Protocol.CmdSetMorphs || type == Protocol.CmdResetMorphs
                || type == Protocol.CmdGesture || type == Protocol.CmdPose || type == Protocol.CmdTrigger
                || type == Protocol.CmdIdle || type == Protocol.CmdBreathing;
        }

        // Returns null on success, else an error message.
        private string Dispatch(string type, string id, JSONClass msg)
        {
            if (IsBodyCommand(type))
            {
                if (!BodyOn)
                {
                    Log.Debug("Body control off: ignoring '" + type + "'");
                    return null;
                }
                if (type == Protocol.CmdGesture || type == Protocol.CmdPose || type == Protocol.CmdTrigger)
                {
                    if (_poses == null) return "Poses are not available: the pose part of the plugin did not start (see the Self-test in tab Config)";
                }
                else if (type == Protocol.CmdIdle || type == Protocol.CmdBreathing) { }   // checked in their case below
                else if (_expressions == null) return "Expressions are not available: the plugin found no morphs on this character yet (see the Self-test in tab Config)";
            }
            switch (type)
            {
                case Protocol.CmdSpeak:
                {
                    if (_speech == null) return "The character cannot speak: the speech part of the plugin did not start (see the Self-test in tab Config)";
                    string utteranceId = id.Length > 0 ? id : "utt-" + DateTime.UtcNow.Ticks;
                    bool interrupt = Protocol.GetString(msg, "queue", "append") == "interrupt";
                    string error = _speech.Enqueue(utteranceId, Protocol.GetString(msg, "audio", ""), interrupt);
                    if (error == null && Protocol.Has(msg, "expression") && BodyOn && _expressions != null)
                    {
                        try
                        {
                            _expressions.SetExpression(Protocol.GetString(msg, "expression", ""),
                                Protocol.GetFloat(msg, "intensity", 1f), 0.4f, -1f);
                        }
                        catch (Exception e)
                        {
                            Log.Error("speak: expression failed (speech continues)", e);
                        }
                    }
                    return error;
                }

                case Protocol.CmdStopSpeaking:
                    if (_speech != null) _speech.StopAll("stopped");
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
                {
                    // Version 32: only {"json": "{\"pose\":\"<id>\"}"}, checked against the pose vocabulary. The old
                    // fields path / name are not accepted any more.
                    string poseError = _poses.ApplyPoseJson(Protocol.GetString(msg, "json", ""));
                    if (poseError != null) Log.Warn("Pose ignored: " + poseError);
                    return poseError;
                }

                case Protocol.CmdTrigger:
                    return _poses.Trigger(msg);

                case Protocol.CmdLookAt:
                    // Removed after version 36 (Leon): the eyes belong to VaM. An older companion may still send it.
                    Log.Debug("look_at ignored: AIBody does not move the eyes");
                    return null;

                case Protocol.CmdIdle:
                    if (_idle == null) return "Head motion not available";
                    _idle.Enabled = Protocol.GetBool(msg, "enabled", _idle.Enabled);
                    _idle.Intensity = Protocol.GetFloat(msg, "intensity", _idle.Intensity);
                    return null;

                case Protocol.CmdBreathing:
                    if (_breathing == null) return "Breathing not available (no morphs)";
                    _breathing.Enabled = Protocol.GetBool(msg, "enabled", _breathing.Enabled);
                    _breathing.Rate = Protocol.GetFloat(msg, "rate", _breathing.Rate);
                    _breathing.Depth = Protocol.GetFloat(msg, "depth", _breathing.Depth);
                    return null;

                case "":
                    return "Message has no 'type'";

                default:
                    return "Command type '" + type + "' is not a body command";
            }
        }
    }
}
