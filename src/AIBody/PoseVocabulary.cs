// Pose commands (version 32): the fixed vocabulary that is the ONLY way a pose is applied.
//
// A command is a text the user says or types (config.json poses.commands: command -> pose id). The companion app
// applies the hard gate (the user's WHOLE input must equal a command) and answers with {"pose":"<id>"}; this class
// is the plugin's second line: it parses that JSON strictly and checks the id against ITS OWN vocabulary, so an
// unknown or malformed pose can never be applied. The rules (normalization, pose_key, strict JSON) are the same as
// companion/aibody_companion/pose_commands.py; tests/test_pose_commands.py runs both with the same test vectors.
//
// Pure C# (no VaM types), so the rules can be run outside VaM. No Dictionary.Keys/.Values enumeration, no LINQ.
using System.Collections.Generic;
using System.Text;

namespace AIBody
{
    public class PoseCommand
    {
        public string Command;   // the text the user says, e.g. "Sit Down"
        public string Pose;      // id of a pose of the character (compared with PoseVocabulary.PoseKey)

        public PoseCommand(string command, string pose)
        {
            Command = command;
            Pose = pose;
        }
    }

    public class PoseVocabulary
    {
        /// <summary>Leon's wording (20.11.2026), exactly. Each starter command links to a pose of the same name.</summary>
        public static readonly string[] StarterCommands =
        {
            "Sit Down", "Lay Down", "Prone", "Stand Up", "Spread Your Legs", "Ankle Your Knees", "Ankle Your Elbows",
            "Turn Around", "Crawl on all fours", "Bend Over"
        };

        public const int MaxCommands = 100;
        public const int MaxCommandChars = 60;
        public const int MaxPoseChars = 200;

        private readonly List<PoseCommand> _entries = new List<PoseCommand>();

        public int Count { get { return _entries.Count; } }
        public PoseCommand this[int index] { get { return _entries[index]; } }

        public void Clear() { _entries.Clear(); }

        public void SetStarters()
        {
            _entries.Clear();
            for (int i = 0; i < StarterCommands.Length; i++) _entries.Add(new PoseCommand(StarterCommands[i], StarterCommands[i]));
        }

        /// <summary>Adds the starter commands that are missing (an existing command keeps its link). Returns how many were added.</summary>
        public int RestoreStarters()
        {
            int added = 0;
            for (int i = 0; i < StarterCommands.Length; i++)
            {
                if (IndexOf(StarterCommands[i]) >= 0) continue;
                _entries.Add(new PoseCommand(StarterCommands[i], StarterCommands[i]));
                added++;
            }
            return added;
        }

        // ---------------------------------------------------------------- normalization

        /// <summary>The characters treated as white space (the same set on both sides).</summary>
        private static bool IsWhite(char c)
        {
            return c == '\t' || c == '\n' || c == '\u000b' || c == '\u000c' || c == '\r' || c == ' ' || c == '\u0085'
                || c == '\u00a0' || c == '\u1680' || (c >= '\u2000' && c <= '\u200a') || c == '\u2028' || c == '\u2029'
                || c == '\u202f' || c == '\u205f' || c == '\u3000';
        }

        private static bool IsTrailing(char c)
        {
            return c == '.' || c == '!' || c == '?' || c == '\u2026' || c == '\u3002' || c == '\uff01' || c == '\uff1f';
        }

        /// <summary>Trims and collapses internal white space to single spaces.</summary>
        public static string Collapse(string text)
        {
            if (text == null) return "";
            StringBuilder sb = new StringBuilder();
            bool pendingSpace = false;
            for (int i = 0; i < text.Length; i++)
            {
                char c = text[i];
                if (IsWhite(c)) { pendingSpace = sb.Length > 0; continue; }
                if (pendingSpace) { sb.Append(' '); pendingSpace = false; }
                sb.Append(c);
            }
            return sb.ToString();
        }

        /// <summary>The form in which the user's input and a command text are compared ("" = nothing to compare).</summary>
        public static string NormalizeInput(string text)
        {
            string t = Collapse(text).ToLowerInvariant();
            int end = t.Length;
            while (end > 0 && (IsTrailing(t[end - 1]) || IsWhite(t[end - 1]))) end--;
            return t.Substring(0, end);
        }

        /// <summary>Pose ids compare ignoring case, spaces, '_', '-' and every other non-alphanumeric character.</summary>
        public static string PoseKey(string name)
        {
            if (name == null) return "";
            StringBuilder sb = new StringBuilder();
            string lower = name.ToLowerInvariant();
            for (int i = 0; i < lower.Length; i++) if (char.IsLetterOrDigit(lower[i])) sb.Append(lower[i]);
            return sb.ToString();
        }

        // ---------------------------------------------------------------- the gate's lookup

        private int IndexOf(string command)
        {
            string key = NormalizeInput(command);
            if (key.Length == 0) return -1;
            for (int i = 0; i < _entries.Count; i++) if (NormalizeInput(_entries[i].Command) == key) return i;
            return -1;
        }

        /// <summary>The command whose text equals the ENTIRE input, else null. No substring or fuzzy matching.</summary>
        public PoseCommand Match(string input)
        {
            int i = IndexOf(input);
            return i >= 0 ? _entries[i] : null;
        }

        /// <summary>A command that links to this pose id (compared with PoseKey), else null.</summary>
        public PoseCommand FindByPoseId(string pose)
        {
            string key = PoseKey(pose);
            if (key.Length == 0) return null;
            for (int i = 0; i < _entries.Count; i++) if (PoseKey(_entries[i].Pose) == key) return _entries[i];
            return null;
        }

        /// <summary>The character's pose (its real name) that the command links to, or null if there is none.</summary>
        public static string Resolve(PoseCommand entry, List<string> poseNames)
        {
            if (entry == null || poseNames == null) return null;
            string key = PoseKey(entry.Pose);
            for (int i = 0; i < poseNames.Count; i++) if (PoseKey(poseNames[i]) == key) return poseNames[i];
            return null;
        }

        // ---------------------------------------------------------------- Add Pose / Delete Pose

        /// <summary>Adds a command, or re-links an existing one with the same (normalized) text. Returns an error message or null.</summary>
        public string Add(string command, string pose)
        {
            string text = Collapse(command);
            string id = Collapse(pose);
            if (NormalizeInput(text).Length == 0) return "Type the command text first (letters or digits)";
            if (text.Length > MaxCommandChars) return "The command is longer than " + MaxCommandChars + " characters";
            if (PoseKey(id).Length == 0) return "Choose a pose first";
            if (id.Length > MaxPoseChars) return "The pose name is too long";
            int existing = IndexOf(text);
            if (existing >= 0)
            {
                _entries[existing].Pose = id;   // same command again: only the link changes, the label stays
                return null;
            }
            if (_entries.Count >= MaxCommands) return "At most " + MaxCommands + " pose commands";
            _entries.Add(new PoseCommand(text, id));
            return null;
        }

        /// <summary>Removes the command (matched like the gate matches). True if it existed.</summary>
        public bool Remove(string command)
        {
            int i = IndexOf(command);
            if (i < 0) return false;
            _entries.RemoveAt(i);
            return true;
        }

        // ---------------------------------------------------------------- the answer: {"pose":"<id>"}

        /// <summary>The JSON the companion sends for a matched command.</summary>
        public static string ReplyJson(string pose)
        {
            StringBuilder sb = new StringBuilder("{\"pose\":\"");
            AppendEscaped(sb, pose ?? "");
            return sb.Append("\"}").ToString();
        }

        private static void AppendEscaped(StringBuilder sb, string s)
        {
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if (c == '"') sb.Append("\\\"");
                else if (c == '\\') sb.Append("\\\\");
                else if (c < ' ') sb.Append("\\u").Append(((int)c).ToString("x4"));
                else sb.Append(c);
            }
        }

        /// <summary>
        /// Strict reader: exactly one key "pose" with a non-empty text value, nothing else (JSON white space allowed
        /// between tokens). Returns an error message (and pose = null), or null on success.
        /// </summary>
        public static string ParsePoseJson(string json, out string pose)
        {
            pose = null;
            if (json == null || json.Length == 0) return "the pose reply is empty";
            if (json.Length > 400) return "the pose reply is too long";
            int p = 0;
            SkipJsonWhite(json, ref p);
            if (p >= json.Length || json[p] != '{') return "the pose reply is not a JSON object";
            p++;
            SkipJsonWhite(json, ref p);
            string key, error = ReadJsonString(json, ref p, out key);
            if (error != null) return error;
            if (key != "pose") return "the pose reply must be exactly {\"pose\": \"<id>\"}";
            SkipJsonWhite(json, ref p);
            if (p >= json.Length || json[p] != ':') return "the pose reply is not valid JSON";
            p++;
            SkipJsonWhite(json, ref p);
            string value;
            error = ReadJsonString(json, ref p, out value);
            if (error != null) return error;
            SkipJsonWhite(json, ref p);
            if (p >= json.Length) return "the pose reply is not valid JSON";
            if (json[p] == ',') return "the pose reply must be exactly {\"pose\": \"<id>\"}";
            if (json[p] != '}') return "the pose reply is not valid JSON";
            p++;
            SkipJsonWhite(json, ref p);
            if (p != json.Length) return "the pose reply has extra text after the object";
            if (PoseKey(value).Length == 0 || value.Length > MaxPoseChars) return "the pose reply has no usable pose id";
            pose = value;
            return null;
        }

        private static void SkipJsonWhite(string s, ref int p)
        {
            while (p < s.Length && (s[p] == ' ' || s[p] == '\t' || s[p] == '\n' || s[p] == '\r')) p++;
        }

        private static string ReadJsonString(string s, ref int p, out string value)
        {
            value = null;
            if (p >= s.Length || s[p] != '"') return "the pose reply is not valid JSON";
            p++;
            StringBuilder sb = new StringBuilder();
            while (true)
            {
                if (p >= s.Length) return "the pose reply is not valid JSON";
                char c = s[p++];
                if (c == '"') break;
                if (c < ' ') return "the pose reply is not valid JSON";
                if (c != '\\') { sb.Append(c); continue; }
                if (p >= s.Length) return "the pose reply is not valid JSON";
                char e = s[p++];
                switch (e)
                {
                    case '"': sb.Append('"'); break;
                    case '\\': sb.Append('\\'); break;
                    case '/': sb.Append('/'); break;
                    case 'b': sb.Append('\b'); break;
                    case 'f': sb.Append('\f'); break;
                    case 'n': sb.Append('\n'); break;
                    case 'r': sb.Append('\r'); break;
                    case 't': sb.Append('\t'); break;
                    case 'u':
                    {
                        if (p + 4 > s.Length) return "the pose reply is not valid JSON";
                        int code = 0;
                        for (int i = 0; i < 4; i++)
                        {
                            int d = HexValue(s[p + i]);
                            if (d < 0) return "the pose reply is not valid JSON";
                            code = code * 16 + d;
                        }
                        p += 4;
                        sb.Append((char)code);
                        break;
                    }
                    default: return "the pose reply is not valid JSON";
                }
            }
            value = sb.ToString();
            return null;
        }

        private static int HexValue(char c)
        {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return c - 'a' + 10;
            if (c >= 'A' && c <= 'F') return c - 'A' + 10;
            return -1;
        }
    }
}
