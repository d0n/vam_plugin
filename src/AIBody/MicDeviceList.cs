// Builds the entries of the "Mic device" menu from the companion app's device list.
// Pure list logic without VaM or SimpleJSON types, so tools/cs_tests can run it with plain .NET.
//
// Version 16: the menu uses plain choices only (no displayChoices). In version 15 the mic menu was
// the only chooser of the plugin with displayChoices, and in VaM it showed "(not selected)" with an
// empty list (not even "Standard", which the plugin sets from the start). TODO(verify): that
// displayChoices is the reason; the info field now lists the menu entries, so a screenshot shows
// whether the plugin had them. Every entry is shown as stored; "Standard (System-Mikrofon)" is a
// real value.
using System.Collections.Generic;

namespace AIBody
{
    public static class MicDeviceList
    {
        /// <summary>First entry, always present; saved as "" in config.json (= system default).</summary>
        public const string DefaultChoice = "Standard (System-Mikrofon)";

        /// <summary>Value saved with scenes up to version 15; read as DefaultChoice.</summary>
        public const string LegacyDefault = "(system default)";

        public static bool IsDefault(string value)
        {
            return string.IsNullOrEmpty(value) || value == DefaultChoice || value == LegacyDefault;
        }

        /// <summary>Menu value for a config.json / companion device name ("" = DefaultChoice).</summary>
        public static string ToChoice(string device)
        {
            return IsDefault(device) ? DefaultChoice : device.Trim();
        }

        /// <summary>config.json value for a menu value (DefaultChoice = "").</summary>
        public static string ToConfig(string choice)
        {
            return IsDefault(choice) ? "" : choice;
        }

        /// <summary>
        /// DefaultChoice, then every received name once (trimmed, empty ones skipped), then the current
        /// selection if it is not in the list (a saved but unplugged mic stays visible).
        /// found = number of usable received names; missing = current selection was not received.
        /// </summary>
        public static List<string> Build(List<string> names, string current, out int found, out bool missing)
        {
            List<string> choices = new List<string> { DefaultChoice };
            found = 0;
            if (names != null)
            {
                for (int i = 0; i < names.Count; i++)
                {
                    string name = names[i] == null ? "" : names[i].Trim();
                    if (name.Length == 0 || IsDefault(name) || choices.Contains(name)) continue;
                    choices.Add(name);
                    found++;
                }
            }
            string selected = ToChoice(current);
            missing = !choices.Contains(selected);
            if (missing) choices.Add(selected);
            return choices;
        }
    }
}
