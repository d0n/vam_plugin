// Test harness for OriginReset in src/AIBody/RootReset.cs: one JSON case per line on stdin, one JSON answer per line.
//   {"cmd":"delta","o":[x,z],"c":[x,z],"tol":t} -> {"v":"Ok|Tiny|Absurd","dx":..,"dz":..}
//   {"cmd":"sane","p":[x,y,z],"r":[x,y,z],"max":m} -> {"sane":bool}
//   {"cmd":"side","from":[x,z],"t":[x,z],"others":[x,z,x,z],"clear":c} -> {"moved":bool,"t":[x,z]}
//   {"cmd":"log","pose":"..","dx":..,"dz":..,"d":..,"shift":bool} -> {"line":".."}
using System;
using System.Globalization;
using System.Text.Json;
using AIBody;

public static class Program
{
    private static string F(float v) { return v.ToString("R", CultureInfo.InvariantCulture); }
    private static float G(JsonElement e, int i) { return e[i].GetSingle(); }

    public static void Main()
    {
        string line;
        while ((line = Console.ReadLine()) != null)
        {
            if (line.Trim().Length == 0) continue;
            JsonElement c = JsonDocument.Parse(line).RootElement;
            string cmd = c.GetProperty("cmd").GetString();
            if (cmd == "delta")
            {
                float dx, dz;
                JsonElement o = c.GetProperty("o"), cur = c.GetProperty("c");
                int v = OriginReset.Delta(G(o, 0), G(o, 1), G(cur, 0), G(cur, 1), c.GetProperty("tol").GetSingle(), out dx, out dz);
                Console.WriteLine("{\"v\":\"" + OriginReset.VerdictName(v) + "\",\"dx\":" + F(dx) + ",\"dz\":" + F(dz) + "}");
            }
            else if (cmd == "sane")
            {
                JsonElement p = c.GetProperty("p"), r = c.GetProperty("r");
                bool ok = OriginReset.Sane(G(p, 0), G(p, 1), G(p, 2), G(r, 0), G(r, 1), G(r, 2), c.GetProperty("max").GetSingle());
                Console.WriteLine("{\"sane\":" + (ok ? "true" : "false") + "}");
            }
            else if (cmd == "side")
            {
                JsonElement f = c.GetProperty("from"), t = c.GetProperty("t"), os = c.GetProperty("others");
                float[] others = new float[os.GetArrayLength()];
                for (int i = 0; i < others.Length; i++) others[i] = os[i].GetSingle();
                float tx = G(t, 0), tz = G(t, 1);
                bool moved = OriginReset.Sideways(G(f, 0), G(f, 1), ref tx, ref tz, others, c.GetProperty("clear").GetSingle());
                Console.WriteLine("{\"moved\":" + (moved ? "true" : "false") + ",\"t\":[" + F(tx) + "," + F(tz) + "]}");
            }
            else
            {
                string text = OriginReset.LogLine(c.GetProperty("pose").GetString(), c.GetProperty("dx").GetSingle(), c.GetProperty("dz").GetSingle(),
                    c.GetProperty("d").GetSingle(), c.GetProperty("shift").GetBoolean());
                Console.WriteLine(JsonSerializer.Serialize(new { line = text }));
            }
        }
    }
}
