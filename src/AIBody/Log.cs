// AIBody - gives an AI a virtual body in Virt-A-Mate.
// Small logging helper so every message carries the same prefix. Shared by both plugins;
// each plugin sets its own Prefix in Init().
using System;
using System.Collections.Generic;

namespace AIBody
{
    public static class Log
    {
        public static string Prefix = "AIBody: ";
        public static bool Verbose = false;

        public static void Info(string message)
        {
            SuperController.LogMessage(Prefix + message);
        }

        /// <summary>The last debug lines (newest last) for the status box while Verbose log is on.</summary>
        public const int RecentMax = 8;
        private static readonly List<string> _recent = new List<string>();

        public static void Debug(string message)
        {
            if (!Verbose) return;
            SuperController.LogMessage(Prefix + "[debug] " + message);
            _recent.Add(DateTime.Now.ToString("HH:mm:ss") + " " + message);
            if (_recent.Count > RecentMax) _recent.RemoveAt(0);
        }

        public static string RecentText()
        {
            return _recent.Count == 0 ? "" : string.Join("\n", _recent.ToArray()) + "\n";
        }

        /// <summary>A short warning in the normal (not red) log: something was ignored on purpose.</summary>
        public static void Warn(string message)
        {
            SuperController.LogMessage(Prefix + "Warning: " + message);
        }

        public static void Error(string message)
        {
            SuperController.LogError(Prefix + message);
        }

        public static void Error(string message, Exception e)
        {
            SuperController.LogError(Prefix + message + "\n" + e);
        }
    }
}
