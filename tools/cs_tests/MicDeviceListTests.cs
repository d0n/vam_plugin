// Plain .NET tests for src/AIBody/MicDeviceList.cs (no VaM needed). Run by
// companion/tests/test_mic_device_list_cs.py (dotnet run); prints "OK n" or the failures.
using System;
using System.Collections.Generic;
using AIBody;

public static class MicDeviceListTests
{
    private static int _checks;
    private static readonly List<string> Failures = new List<string>();

    private static void Check(bool ok, string what)
    {
        _checks++;
        if (!ok) Failures.Add(what);
    }

    private static string Join(List<string> l) { return string.Join(" | ", l.ToArray()); }

    public static int Main()
    {
        int found;
        bool missing;

        List<string> c = MicDeviceList.Build(new List<string>(), "", out found, out missing);
        Check(Join(c) == MicDeviceList.DefaultChoice, "empty list -> only Standard: " + Join(c));
        Check(found == 0 && !missing, "empty list counts");

        c = MicDeviceList.Build(null, MicDeviceList.LegacyDefault, out found, out missing);
        Check(Join(c) == MicDeviceList.DefaultChoice && !missing, "null list + old default -> only Standard: " + Join(c));

        List<string> four = new List<string> { "Mikrofon (Realtek(R) Audio)", " Headset (USB) ", "", "Mikrofon (Realtek(R) Audio)", "Webcam Mic", "Line In" };
        c = MicDeviceList.Build(four, MicDeviceList.DefaultChoice, out found, out missing);
        Check(c.Count == 5 && c[0] == MicDeviceList.DefaultChoice, "4 mics + Standard: " + Join(c));
        Check(c[2] == "Headset (USB)", "names trimmed: " + Join(c));
        Check(found == 4 && !missing, "found 4, nothing missing: " + found);

        c = MicDeviceList.Build(four, "Old Mic", out found, out missing);
        Check(missing && c[c.Count - 1] == "Old Mic" && c.Count == 6, "saved but unplugged mic stays: " + Join(c));

        c = MicDeviceList.Build(four, "Webcam Mic", out found, out missing);
        Check(!missing && c.Count == 5, "selected mic in list: " + Join(c));

        Check(MicDeviceList.ToConfig(MicDeviceList.DefaultChoice) == "", "Standard saved as empty");
        Check(MicDeviceList.ToConfig(MicDeviceList.LegacyDefault) == "", "old default saved as empty");
        Check(MicDeviceList.ToConfig("Line In") == "Line In", "name saved as is");
        Check(MicDeviceList.ToChoice("") == MicDeviceList.DefaultChoice, "empty config -> Standard");
        Check(MicDeviceList.ToChoice("Line In") == "Line In", "config name -> menu name");

        if (Failures.Count == 0)
        {
            Console.WriteLine("OK " + _checks);
            return 0;
        }
        foreach (string f in Failures) Console.WriteLine("FAIL " + f);
        return 1;
    }
}
