// Start-up diagnostics: every Init step and every failure goes to the plugin window's status box
// AND to the VaM log, so a broken start is never just an empty window.
// Only plain C# / SuperController logging; no reflection (exception type and first stack line
// are read from Exception.ToString()).
using System;
using System.Collections.Generic;

namespace AIBody
{
    public class Diag
    {
        private readonly List<string> _lines = new List<string>();
        private readonly List<string> _failed = new List<string>();

        /// <summary>Called after every new line (the plugin refreshes its status box).</summary>
        public Action Changed;

        public int FailureCount { get { return _failed.Count; } }
        public IEnumerable<string> FailedPhases { get { return _failed; } }

        public void Step(string text)
        {
            _lines.Add(text);
            Log.Info(text);
            Notify();
        }

        public void Warn(string text)
        {
            _lines.Add("WARNUNG: " + text);
            Log.Error(text);
            Notify();
        }

        /// <summary>Runs one phase; a failure is recorded and does not stop the caller.</summary>
        public bool Run(string phase, Action action)
        {
            try
            {
                action();
                _lines.Add("ok: " + phase);
                Log.Debug("ok: " + phase);
                Notify();
                return true;
            }
            catch (Exception e)
            {
                Fail(phase, e);
                return false;
            }
        }

        public void Fail(string phase, Exception e)
        {
            _failed.Add(phase);
            string line = "FEHLER in " + phase + ": " + Describe(e);
            _lines.Add(line);
            Log.Error(line + "\n" + e);
            Notify();
        }

        /// <summary>"Type: message | at first stack frame" from Exception.ToString().</summary>
        public static string Describe(Exception e)
        {
            if (e == null) return "(null)";
            string[] parts = e.ToString().Split('\n');
            string head = parts.Length > 0 ? parts[0].Trim() : e.Message;
            for (int i = 1; i < parts.Length; i++)
            {
                string p = parts[i].Trim();
                if (p.StartsWith("at ")) return head + " | " + p;
            }
            return head;
        }

        public string Text
        {
            get { return string.Join("\n", _lines.ToArray()); }
        }

        private void Notify()
        {
            if (Changed == null) return;
            try { Changed(); }
            catch (Exception e) { Log.Error("status refresh failed", e); }
        }
    }
}
