// Version 66 test harness: runs the pure C# IdlePoolMode (src/AIBody/IdlePoses.cs) outside VaM.
// One command per input line, fields separated by a tab; one result line each (fields separated by a tab).
using System;
using System.Collections.Generic;
using AIBody;

public static class Harness
{
    public static int Main()
    {
        string line;
        while ((line = Console.In.ReadLine()) != null)
        {
            string[] f = line.Split('\t');
            string arg = f.Length > 1 ? f[1] : "";
            switch (f[0])
            {
                case "labels": Console.WriteLine(string.Join("\t", IdlePoolMode.Labels().ToArray())); break;
                case "constants":
                    Console.WriteLine(IdlePoolMode.DefaultLabel + "\t" + IdlePoolMode.MenuName + "\t" + IdlePoolMode.LegacyToggleName); break;
                case "normalize": Console.WriteLine(IdlePoolMode.Normalize(arg)); break;
                case "islabel": Console.WriteLine(IdlePoolMode.IsLabel(arg) ? "1" : "0"); break;
                case "isall": Console.WriteLine(IdlePoolMode.IsAll(arg) ? "1" : "0"); break;
                case "keyof": Console.WriteLine(IdlePoolMode.KeyOf(arg)); break;
                case "labelofkey": Console.WriteLine(IdlePoolMode.LabelOfKey(arg)); break;
                case "legacy": Console.WriteLine(IdlePoolMode.LabelOfLegacy(arg == "true")); break;
                case "describe": Console.WriteLine(IdlePoolMode.Describe(arg, "Custom/Atom/Person/Pose/AIBody")); break;
                default: Console.WriteLine("?"); return 2;
            }
        }
        return 0;
    }
}
