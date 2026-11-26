// Test harness (not part of the plugin): runs the plugin's real MorphBlendLayer (extracted from MorphHelper.cs by the test)
// outside VaM with minimal stand-ins for DAZMorph, MorphHelper.Find and Mathf. One command per line (tab separated):
//   morph NAME ORIGINAL | blend SECONDS | set NAME VALUE | release NAME | releaseall | releaseexcept A,B | update DT [COUNT] | print
// print writes "A=0.123;B=0.5|active=2".
using System;
using System.Collections.Generic;
using System.Globalization;
using AIBody;

namespace UnityEngine
{
    public static class Mathf
    {
        public static float Max(float a, float b) { return a > b ? a : b; }
        public static float Abs(float a) { return Math.Abs(a); }
        public static bool Approximately(float a, float b) { return Math.Abs(a - b) < 1e-6f; }
        public static float MoveTowards(float current, float target, float maxDelta)
        {
            if (Math.Abs(target - current) <= maxDelta) return target;
            return current + Math.Sign(target - current) * maxDelta;
        }
    }
}

namespace AIBody
{
    public class DAZMorph { public float morphValue; }

    public class MorphHelper
    {
        public Dictionary<string, DAZMorph> Morphs = new Dictionary<string, DAZMorph>();
        public DAZMorph Find(string name) { DAZMorph m; return Morphs.TryGetValue(name, out m) ? m : null; }
    }
}

public static class Program
{
    static float F(string s) { return float.Parse(s, CultureInfo.InvariantCulture); }

    public static int Main()
    {
        MorphHelper helper = new MorphHelper();
        MorphBlendLayer layer = new MorphBlendLayer(helper);
        string line;
        while ((line = Console.ReadLine()) != null)
        {
            string[] p = line.Split('\t');
            switch (p[0])
            {
                case "morph": { DAZMorph m = new DAZMorph(); m.morphValue = F(p[2]); helper.Morphs[p[1]] = m; break; }
                case "blend": layer.BlendSeconds = F(p[1]); break;
                case "set": Console.WriteLine(layer.SetTarget(p[1], F(p[2])) ? "ok" : "missing"); break;
                case "release": layer.Release(p[1]); break;
                case "releaseall": layer.ReleaseAll(); break;
                case "releaseexcept": layer.ReleaseAllExcept(new HashSet<string>(p[1].Split(','))); break;
                case "update":
                {
                    int n = p.Length > 2 ? int.Parse(p[2]) : 1;
                    for (int i = 0; i < n; i++) layer.Update(F(p[1]));
                    break;
                }
                case "print":
                {
                    List<string> parts = new List<string>();
                    foreach (KeyValuePair<string, DAZMorph> kv in helper.Morphs) parts.Add(kv.Key + "=" + kv.Value.morphValue.ToString("0.000", CultureInfo.InvariantCulture));
                    Console.WriteLine(string.Join(";", parts) + "|active=" + layer.ActiveCount);
                    break;
                }
            }
        }
        return 0;
    }
}
