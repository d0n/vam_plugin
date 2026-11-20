// Test harness (not part of the plugin): runs the plugin's real IdlePoses.cs (with PoseVocabulary.cs) outside VaM.
// Reads one JSON object per line: {"poses":[...], "commands":[[cmd,pose],...] or null (= starters), "default":"...",
// "min":s, "max":s, "steps":[[dt, busy, bodyControl, "event", count?], ...]} where event is "" or "user" (a user pose command, before the step).
// Writes one JSON array per line: the pose names the scheduler chose, with the step index ("3:Sit Down").
using System;
using System.Collections.Generic;
using System.Text.Json;
using AIBody;

public static class Program
{
    public static int Main()
    {
        string line;
        while ((line = Console.ReadLine()) != null)
        {
            JsonElement a = JsonDocument.Parse(line).RootElement;
            PoseVocabulary v = new PoseVocabulary();
            if (a.GetProperty("commands").ValueKind == JsonValueKind.Null) v.SetStarters();
            else foreach (JsonElement c in a.GetProperty("commands").EnumerateArray()) v.Add(c[0].GetString(), c[1].GetString());
            List<string> poses = new List<string>();
            foreach (JsonElement p in a.GetProperty("poses").EnumerateArray()) poses.Add(p.GetString());
            IdlePoseScheduler s = new IdlePoseScheduler(7);
            s.DefaultPose = a.GetProperty("default").GetString();
            s.MinSeconds = (float)a.GetProperty("min").GetDouble();
            s.MaxSeconds = (float)a.GetProperty("max").GetDouble();
            if (a.TryGetProperty("enabled", out JsonElement en)) s.Enabled = en.GetBoolean();
            List<string> chosen = new List<string>();
            int i = 0;
            foreach (JsonElement step in a.GetProperty("steps").EnumerateArray())
            {
                int count = step.GetArrayLength() > 4 ? step[4].GetInt32() : 1;   // optional 5th: repeat count
                if (step[3].GetString() == "user") s.NoteUserPose();
                for (int k = 0; k < count; k++)
                {
                    string pose = s.Update((float)step[0].GetDouble(), step[1].GetBoolean(), step[2].GetBoolean(), v, poses);
                    if (pose != null) chosen.Add(i + ":" + pose);
                    i++;
                }
            }
            Console.WriteLine(JsonSerializer.Serialize(chosen));
        }
        return 0;
    }
}
