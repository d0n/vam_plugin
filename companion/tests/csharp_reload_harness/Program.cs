// Test harness for src/AIBody/ReloadState.cs (version 67): one command per line (tab separated), one answer per line.
//   fresh STAMP NOW_ISO MAXAGE -> 1|0 ; applies FRESH(1|0) SAVEDATOM ATOM SCENE(1|0) -> 1|0 ; stamp NOW_ISO -> stamp ; const -> file\tmax
using System;
using System.Globalization;
using AIBody;

public static class Program
{
    static DateTime T(string s) { return DateTime.Parse(s, CultureInfo.InvariantCulture, DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal); }

    public static void Main()
    {
        string line;
        while ((line = Console.ReadLine()) != null)
        {
            string[] p = line.Split('\t');
            if (p[0] == "fresh") Console.WriteLine(ReloadState.Fresh(p[1], T(p[2]), double.Parse(p[3], CultureInfo.InvariantCulture)) ? "1" : "0");
            else if (p[0] == "applies") Console.WriteLine(ReloadState.Applies(p[1] == "1", p[2], p[3], p[4] == "1") ? "1" : "0");
            else if (p[0] == "stamp") Console.WriteLine(ReloadState.Stamp(T(p[1])));
            else Console.WriteLine(ReloadState.FileName + "\t" + ReloadState.MaxAgeSeconds.ToString(CultureInfo.InvariantCulture));
        }
    }
}
