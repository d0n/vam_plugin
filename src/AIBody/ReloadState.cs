// Reload Plugin keeps the plugin's settings (version 67, Don 26.11.2026 21:34). VaM's "Reload Plugin" creates the plugin anew:
// every storable starts with its default and VaM does not restore the scene values (observed: the Dollmaster "Activate" toggle
// came back off; what config.json holds came back through the config.json seeding). So OnDestroy writes the plugin's storables
// (JSONStorable.GetJSON, E1) to Saves/PluginData/AIBody/reload_state.json with the time and the atom; the next Init reads the
// file once and deletes it, and applies it only when it is younger than MaxAgeSeconds, belongs to the same atom and VaM did
// NOT restore a scene into the new plugin (a scene load calls RestoreFromJSON: then the scene wins, so a new scene is never
// changed by it).
// TODO(verify in VaM): that Reload Plugin does not call RestoreFromJSON (Don's observation says the values are not restored).
// This file is pure C# (no VaM or Unity types), tests run it outside VaM (companion/tests/test_version67.py).
using System;
using System.Globalization;

namespace AIBody
{
    public static class ReloadState
    {
        public const string FileName = "reload_state.json";
        public const double MaxAgeSeconds = 30.0;

        /// <summary>The time stamp written into the file (UTC, round-trip format).</summary>
        public static string Stamp(DateTime utcNow)
        {
            return utcNow.ToUniversalTime().ToString("o", CultureInfo.InvariantCulture);
        }

        /// <summary>True when the stamp parses and is between 0 and maxAge seconds before now (a clock step back = not fresh).</summary>
        public static bool Fresh(string stamp, DateTime utcNow, double maxAgeSeconds)
        {
            DateTime saved;
            if (string.IsNullOrEmpty(stamp)) return false;
            if (!DateTime.TryParse(stamp, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out saved)) return false;
            double age = (utcNow.ToUniversalTime() - saved.ToUniversalTime()).TotalSeconds;
            return age >= 0.0 && age <= maxAgeSeconds;
        }

        /// <summary>Apply the saved state: fresh, the same atom, and no scene restore into the new plugin.</summary>
        public static bool Applies(bool fresh, string savedAtom, string atom, bool sceneRestored)
        {
            return fresh && !sceneRestored && !string.IsNullOrEmpty(atom) && savedAtom == atom;
        }
    }
}
