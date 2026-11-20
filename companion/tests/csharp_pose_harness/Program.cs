// Test harness (not part of the plugin): runs the plugin's real PoseVocabulary.cs outside VaM. Reads one JSON array per
// line from stdin ["op", args...] and writes one JSON array per line to stdout. The Python tests feed it the same
// vectors as the companion's pose_commands.py. Ops: norm, key, match, parse, reply, script.
using System;
using System.Collections.Generic;
using System.Text.Json;
using AIBody;

public static class Program
{
    static string S(JsonElement e, int i) { return e[i].GetString(); }

    public static int Main()
    {
        PoseVocabulary starters = new PoseVocabulary();
        starters.SetStarters();
        string line;
        while ((line = Console.ReadLine()) != null)
        {
            JsonElement a = JsonDocument.Parse(line).RootElement;
            string op = S(a, 0);
            object result;
            if (op == "norm") result = PoseVocabulary.NormalizeInput(S(a, 1));
            else if (op == "key") result = PoseVocabulary.PoseKey(S(a, 1));
            else if (op == "match") { PoseCommand m = starters.Match(S(a, 1)); result = m == null ? null : m.Command; }
            else if (op == "reply") result = PoseVocabulary.ReplyJson(S(a, 1));
            else if (op == "parse")
            {
                string pose;
                string error = PoseVocabulary.ParsePoseJson(S(a, 1), out pose);
                result = error == null ? new string[] { "ok", pose } : new string[] { "error", error };
            }
            else if (op == "script")
            {
                // ["script", [["add","cmd","pose"],["remove","cmd"],["restore"],["clear"]...]] -> final list + messages
                PoseVocabulary v = new PoseVocabulary();
                v.SetStarters();
                List<string> messages = new List<string>();
                for (int i = 0; i < a[1].GetArrayLength(); i++)
                {
                    JsonElement step = a[1][i];
                    string what = S(step, 0);
                    if (what == "add") messages.Add(v.Add(S(step, 1), S(step, 2)) ?? "ok");
                    else if (what == "remove") messages.Add(v.Remove(S(step, 1)) ? "removed" : "missing");
                    else if (what == "restore") messages.Add("restored " + v.RestoreStarters());
                    else if (what == "clear") { v.Clear(); messages.Add("cleared"); }
                    else if (what == "match") { PoseCommand m = v.Match(S(step, 1)); messages.Add(m == null ? "-" : m.Command + ">" + m.Pose); }
                    else if (what == "byid") { PoseCommand m = v.FindByPoseId(S(step, 1)); messages.Add(m == null ? "-" : m.Command); }
                }
                List<string> entries = new List<string>();
                for (int i = 0; i < v.Count; i++) entries.Add(v.Get(i).Command + ">" + v.Get(i).Pose);
                result = new object[] { messages, entries };
            }
            else result = "unknown op";
            Console.WriteLine(JsonSerializer.Serialize(result, new JsonSerializerOptions { Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping }));
        }
        return 0;
    }
}
