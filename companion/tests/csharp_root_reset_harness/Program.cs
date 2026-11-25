// Test harness for src/AIBody/RootReset.cs (version 63): one JSON case per line on stdin, one JSON answer per line.
//   {"cmd":"shift","x":..,"y":..,"z":..,"tol":..} -> {"moved":..,"sx":..,"sy":..,"sz":..}
//   {"cmd":"applies","enabled":true,"montage":false} -> {"applies":true}
//   {"cmd":"constants"} -> {"body":"hipControl","tol":0.02,"on":true}
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
            if (cmd == "shift")
            {
                float sx, sy, sz;
                float moved = RootReset.LocalShift(c.GetProperty("x").GetSingle(), c.GetProperty("y").GetSingle(),
                    c.GetProperty("z").GetSingle(), c.GetProperty("tol").GetSingle(), out sx, out sy, out sz);
                Console.WriteLine("{\"moved\":" + F(moved) + ",\"sx\":" + F(sx) + ",\"sy\":" + F(sy) + ",\"sz\":" + F(sz) + "}");
            }
            else if (cmd == "applies")
            {
                bool a = RootReset.Applies(c.GetProperty("enabled").GetBoolean(), c.GetProperty("montage").GetBoolean());
                Console.WriteLine("{\"applies\":" + (a ? "true" : "false") + "}");
            }
            else
            {
                Console.WriteLine("{\"body\":\"" + RootReset.BodyControl + "\",\"tol\":" + F(RootReset.ToleranceMetres)
                    + ",\"on\":" + (RootReset.DefaultOn ? "true" : "false") + "}");
            }
        }
    }
}
