// Test harness for PhysicsFreeze / FrameStall / OriginReset.Sideways in src/AIBody/RootReset.cs (version 69).
// One JSON case per line on stdin, one JSON answer per line on stdout.
using System;
using System.Globalization;
using System.Text.Json;
using AIBody;

public static class Program
{
    private static string F(float v) { return v.ToString("R", CultureInfo.InvariantCulture); }

    public static void Main()
    {
        string line;
        while ((line = Console.ReadLine()) != null)
        {
            if (line.Trim().Length == 0) continue;
            JsonElement c = JsonDocument.Parse(line).RootElement;
            string cmd = c.GetProperty("cmd").GetString();
            if (cmd == "large")
                Console.WriteLine("{\"large\":" + (PhysicsFreeze.IsLarge(c.GetProperty("dx").GetSingle(), c.GetProperty("dz").GetSingle()) ? "true" : "false") + "}");
            else if (cmd == "steps")
                Console.WriteLine("{\"n\":" + PhysicsFreeze.Steps(c.GetProperty("m").GetSingle(), c.GetProperty("step").GetSingle()) + "}");
            else if (cmd == "usesteps")
                Console.WriteLine("{\"use\":" + (PhysicsFreeze.UseSteps(c.GetProperty("on").GetBoolean(), c.GetProperty("dx").GetSingle(), c.GetProperty("dz").GetSingle()) ? "true" : "false") + "}");
            else if (cmd == "log")
                Console.WriteLine(JsonSerializer.Serialize(new { line = PhysicsFreeze.LogLine(c.GetProperty("what").GetString(), c.GetProperty("dx").GetSingle(), c.GetProperty("dz").GetSingle(), c.GetProperty("s").GetSingle()) }));
            else if (cmd == "stall")
                Console.WriteLine("{\"stall\":" + (FrameStall.IsStall(c.GetProperty("s").GetDouble()) ? "true" : "false") + "}");
            else if (cmd == "stalllog")
                Console.WriteLine(JsonSerializer.Serialize(new { line = FrameStall.LogLine(c.GetProperty("s").GetDouble(), c.GetProperty("pose").GetString(), c.GetProperty("origin").GetBoolean(), c.GetProperty("freeze").GetBoolean(), c.GetProperty("d").GetSingle()) }));
            else if (cmd == "consts")
                Console.WriteLine("{\"large\":" + F(PhysicsFreeze.LargeMoveMetres) + ",\"freeze\":" + F(PhysicsFreeze.FreezeSeconds) + ",\"settle\":" + F(PhysicsFreeze.SettleSeconds)
                    + ",\"frames\":" + PhysicsFreeze.PauseFrames + ",\"steps\":" + (PhysicsFreeze.StepsEnabled ? "true" : "false") + ",\"step\":" + F(PhysicsFreeze.StepMetres)
                    + ",\"stall\":" + FrameStall.StallSeconds.ToString("R", CultureInfo.InvariantCulture) + ",\"controls\":" + JsonSerializer.Serialize(OriginReset.OtherControls) + "}");
            else if (cmd == "side")
            {
                JsonElement f = c.GetProperty("from"), t = c.GetProperty("t"), os = c.GetProperty("others");
                float[] others = new float[os.GetArrayLength()];
                for (int i = 0; i < others.Length; i++) others[i] = os[i].GetSingle();
                float tx = t[0].GetSingle(), tz = t[1].GetSingle();
                bool moved = OriginReset.Sideways(f[0].GetSingle(), f[1].GetSingle(), ref tx, ref tz, others, OriginReset.ClearanceMetres);
                Console.WriteLine("{\"moved\":" + (moved ? "true" : "false") + ",\"t\":[" + F(tx) + "," + F(tz) + "]}");
            }
        }
    }
}
