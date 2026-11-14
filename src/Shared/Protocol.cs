// Message protocol shared with the companion app (Python), and the bridge contract between the
// AIBody Client plugin and the AIBody Companion plugin. Compiled into both plugins: the build
// (tools/assemble_plugins.py) renames the namespace AIBodyShared to AIBodyClientShared /
// AIBodyCompanionShared, so the two plugins never define the same type names.
// See protocol/PROTOCOL.md for the authoritative description.
using System;
using System.Collections.Generic;
using SimpleJSON;
using UnityEngine;

namespace AIBodyShared
{
    public static class Protocol
    {
        public const int Version = 2;

        // Commands (companion -> plugin)
        public const string CmdPing = "ping";
        public const string CmdSpeak = "speak";
        public const string CmdStopSpeaking = "stop_speaking";
        public const string CmdExpression = "expression";
        public const string CmdSetMorphs = "set_morphs";
        public const string CmdResetMorphs = "reset_morphs";
        public const string CmdGesture = "gesture";
        public const string CmdPose = "pose";
        public const string CmdTrigger = "trigger";
        public const string CmdIdle = "idle";
        public const string CmdBreathing = "breathing";
        public const string CmdConfigAck = "config_ack";
        public const string CmdDevices = "devices";
        public const string CmdMicState = "mic_state";
        public const string CmdMicLevel = "mic_level";
        public const string CmdCompanionHeartbeat = "companion_heartbeat";

        // Events (plugin -> companion)
        public const string EvtReady = "ready";
        public const string EvtPong = "pong";
        public const string EvtAck = "ack";
        public const string EvtError = "error";
        public const string EvtHeartbeat = "heartbeat";
        public const string EvtSpeechStarted = "speech_started";
        public const string EvtSpeechEnded = "speech_ended";
        public const string EvtGestureDone = "gesture_done";
        public const string EvtShutdown = "shutdown";
        public const string EvtConfig = "config";
        public const string EvtPtt = "ptt";
        public const string EvtListDevices = "list_devices";
        public const string EvtCompanions = "companions";
        public const string EvtCompanionStatus = "companion_status";

        // ---- Client <-> Companion bridge (inside VaM, no files or network involved) ----
        // The Companion plugin (on the AI's Person atom) registers three JSONStorableString params.
        // The Client plugin finds them by scanning SuperController.singleton.GetAtoms():
        //   Client writes ONE message (JSON object, with "via":"aibody_client" and "client":<its
        //   atom uid>) into CompanionInboxParam; the Companion's callback checks the sender,
        //   handles it synchronously and resets the value to "".
        //   Companion appends events (with "atom") to a JSON array in CompanionOutboxParam; the
        //   Client reads the array, resets the value to "" and forwards the events.
        public const string CompanionInboxParam = "AIBody Companion Inbox";
        public const string CompanionOutboxParam = "AIBody Companion Outbox";
        public const string CompanionVersionParam = "AIBody Companion Version";
        public const string ViaClient = "aibody_client";
        public const int MaxOutboxEvents = 100;

        // Error codes of the bridge (also in protocol/PROTOCOL.md).
        public const string ErrNoCompanion = "no_companion";
        public const string ErrCompanionConflict = "companion_conflict";
        public const string ErrNotFromClient = "not_from_client";
        public const string ErrClientConflict = "client_conflict";

        /// <summary>Command types the Client plugin forwards to the Companion plugin.</summary>
        public static readonly string[] BodyCommands =
        {
            CmdSpeak, CmdStopSpeaking, CmdExpression, CmdSetMorphs, CmdResetMorphs,
            CmdGesture, CmdPose, CmdTrigger, CmdIdle, CmdBreathing
        };

        public static bool IsBodyCommand(string type)
        {
            return Array.IndexOf(BodyCommands, type) >= 0;
        }

        private static int _eventCounter;

        /// <summary>Creates an event envelope: {"v":1,"type":...,"id":...,"ts":...}.</summary>
        public static JSONClass NewEvent(string type)
        {
            JSONClass evt = new JSONClass();
            evt["v"].AsInt = Version;
            evt["type"] = type;
            _eventCounter++;
            evt["id"] = "evt-" + DateTime.UtcNow.Ticks + "-" + _eventCounter;
            evt["ts"].AsDouble = UnixTimeSeconds();
            return evt;
        }

        public static JSONClass NewError(string replyTo, string code, string message)
        {
            JSONClass evt = NewEvent(EvtError);
            if (!string.IsNullOrEmpty(replyTo)) evt["reply_to"] = replyTo;
            evt["code"] = code;
            evt["message"] = message;
            return evt;
        }

        public static JSONClass NewAck(string replyTo, string commandType)
        {
            JSONClass evt = NewEvent(EvtAck);
            evt["reply_to"] = replyTo ?? "";
            evt["command"] = commandType ?? "";
            return evt;
        }

        /// <summary>
        /// Parses a raw payload. A payload may hold one message object or an array of them.
        /// Returns an empty list if the payload is not valid JSON.
        /// </summary>
        public static List<JSONClass> ParseMessages(string raw)
        {
            List<JSONClass> result = new List<JSONClass>();
            if (string.IsNullOrEmpty(raw)) return result;
            JSONNode node = JSON.Parse(raw);
            if (node == null) return result;

            JSONClass obj = node as JSONClass;
            if (obj != null)
            {
                result.Add(obj);
                return result;
            }

            JSONArray arr = node as JSONArray;
            if (arr != null)
            {
                for (int i = 0; i < arr.Count; i++)
                {
                    JSONClass item = arr[i] as JSONClass;
                    if (item != null) result.Add(item);
                }
            }
            return result;
        }

        public static double UnixTimeSeconds()
        {
            return (DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
        }

        // --- Small typed accessors with defaults (SimpleJSON returns lazy nodes for missing keys) ---

        public static bool Has(JSONClass msg, string key)
        {
            JSONNode n = msg[key];
            return n != null && !string.IsNullOrEmpty(n.Value);
        }

        public static string GetString(JSONClass msg, string key, string fallback)
        {
            return Has(msg, key) ? msg[key].Value : fallback;
        }

        public static float GetFloat(JSONClass msg, string key, float fallback)
        {
            return Has(msg, key) ? msg[key].AsFloat : fallback;
        }

        public static bool GetBool(JSONClass msg, string key, bool fallback)
        {
            return Has(msg, key) ? msg[key].AsBool : fallback;
        }
    }
}
