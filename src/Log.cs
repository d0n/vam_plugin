// AIBody - gives an AI a virtual body in Virt-A-Mate.
// Small logging helper so every message carries the same prefix.
using System;

namespace AIBody
{
    public static class Log
    {
        public const string Prefix = "AIBody: ";
        public static bool Verbose = false;

        public static void Info(string message)
        {
            SuperController.LogMessage(Prefix + message);
        }

        public static void Debug(string message)
        {
            if (Verbose) SuperController.LogMessage(Prefix + "[debug] " + message);
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
