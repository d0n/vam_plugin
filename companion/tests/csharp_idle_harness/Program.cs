// Test harness (not part of the plugin): runs the plugin's real IdlePoses.cs (with PoseVocabulary.cs) outside VaM.
// Reads one JSON object per line: {"poses":[...], "commands":[[cmd,pose],...] or null (= starters), "default":"...",
// "min":s, "max":s, "steps":[[dt, busy, bodyControl, "event", count?], ...]} where event is "" or "user" (a user pose command, before the step).
// Optional "fail": [...] = pose names whose load fails (version 57: as Body.UpdateIdlePoses does, the pose is excluded at
// once and the next one is picked with PickNow on the next step, no wait; a failed pick is written as "3:Sit Down!", an
// empty pool after failures once as "7:EMPTY").
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
            List<string> fail = new List<string>();
            if (a.TryGetProperty("fail", out JsonElement fl)) foreach (JsonElement f in fl.EnumerateArray()) fail.Add(f.GetString());
            bool nextNow = false, emptyNoted = false;
            List<string> chosen = new List<string>();
            int i = 0;
            foreach (JsonElement step in a.GetProperty("steps").EnumerateArray())
            {
                int count = step.GetArrayLength() > 4 ? step[4].GetInt32() : 1;   // optional 5th: repeat count
                if (step[3].GetString() == "user") s.NoteUserPose();
                for (int k = 0; k < count; k++)
                {
                    string pose;
                    if (nextNow && !step[1].GetBoolean()) { nextNow = false; pose = s.PickNow(v, poses, poses); }
                    else pose = s.Update((float)step[0].GetDouble(), step[1].GetBoolean(), step[2].GetBoolean(), v, poses);
                    if (pose != null && fail.Contains(pose)) { s.Exclude(pose); nextNow = true; chosen.Add(i + ":" + pose + "!"); }
                    else if (pose != null) chosen.Add(i + ":" + pose);
                    else if (s.PoolSize == 0 && s.ExcludedCount > 0 && !emptyNoted) { emptyNoted = true; chosen.Add(i + ":EMPTY"); }
                    i++;
                }
            }
            Console.WriteLine(JsonSerializer.Serialize(chosen));
        }
        return 0;
    }
}
