// AIBody - gives an AI a body in Virt-A-Mate 1.22. ONE plugin, ONE load step:
//
//   Select the AI character's Person atom > Plugins tab > Add Plugin >
//     AddonPackages > d0n.AIBody.<n>:/Custom/Scripts/d0n/AIBody/AIBody.cslist
//     (loose-file install: Custom/Scripts/d0n/AIBody/AIBody.cslist)
//   and start the companion app (the external Python program in companion/).
//
// This is the only MVRScript in AIBody.cslist. It owns two plain components and wires them
// together in-process (no cross-plugin bridge, no atom scanning):
//   - AppLink: file transport to the companion app, heartbeat/status, mic/push-to-talk menu,
//     engine menus
//   - Body: speech with lip sync on the head audio, morphs, expressions, gestures, poses, idle,
//     breathing
// All settings are saved with the Person atom.
//
// Init is built to be diagnosable: the header and the status box are created FIRST, then every
// phase runs in its own try/catch (Diag). A failing phase is shown in the status box and the log,
// and the rest of the UI still appears. A non-Person atom gets an explanation instead of a blank
// window.
using System;
using SimpleJSON;
using UnityEngine;

namespace AIBody
{
    public class AIBodyPlugin : MVRScript
    {
        public const string PluginVersion = "0.6.2";

        private AppLink _link;
        private Body _body;
        private JSONStorableBool _verboseJson;
        private JSONStorableString _statusJson;
        private Diag _diag;

        private bool _initialized;
        private bool _linkBroken;
        private bool _bodyBroken;
        private float _uiTimer;
        private string _atomType = "?";
        private string _writable = "noch nicht geprüft";
        private string _live = "";

        public override void Init()
        {
            Log.Prefix = "AIBody: ";
            _diag = new Diag();
            _statusJson = new JSONStorableString("Status", "AIBody " + PluginVersion + " startet ...");

            // 1. Header and status box before anything that could fail.
            try
            {
                UiHelper.Header(this, "<b>AIBody " + PluginVersion + "</b> (needs the companion app running)", false);
                UIDynamicTextField status = CreateTextField(_statusJson);
                status.height = 640f;
            }
            catch (Exception e)
            {
                _diag.Fail("Statusfeld anlegen", e);
            }
            _diag.Changed = RefreshStatus;
            _diag.Step("Init gestartet (AIBody " + PluginVersion + ")");

            // 2. Right atom?
            try
            {
                _atomType = containingAtom != null ? containingAtom.type : "(kein Atom)";
            }
            catch (Exception e)
            {
                _diag.Fail("Atomtyp lesen", e);
            }
            if (_atomType != "Person")
            {
                string msg = "Dieses Plugin gehört in den Plugins-Tab einer Person-Figur, nicht in Session/Scene "
                    + "Plugins oder auf ein Empty – aktuell: " + _atomType;
                _diag.Warn(msg);
                _diag.Step("Init beendet: AIBody bleibt hier inaktiv. Plugin hier entfernen und auf der "
                    + "KI-Figur (Person) unter Plugins > Add Plugin hinzufügen.");
                return;
            }
            _diag.Step("Atom: Person '" + containingAtom.uid + "'");

            // 3. Components and storables, each phase on its own.
            _diag.Run("AppLink anlegen", () => _link = new AppLink(this, PluginVersion, _diag));
            _diag.Run("Body anlegen", () => _body = new Body(this, containingAtom, SendToApp, _diag));
            if (_link != null && _body != null)
            {
                _link.OnBodyCommand = _body.Handle;
                _link.DecorateStatus = _body.AddStatus;
            }
            _diag.Run("Verbose-Schalter", () =>
            {
                _verboseJson = new JSONStorableBool("Verbose log", false, (bool v) => Log.Verbose = v);
                RegisterBool(_verboseJson);
            });
            if (_link != null) _diag.Run("AppLink.CreateStorables", _link.CreateStorables);
            if (_body != null)
            {
                _diag.Run("Body.CreateStorables", _body.CreateStorables);
                _diag.Run("Body.CreateControllers", _body.CreateControllers);
            }
            if (_verboseJson != null) Log.Verbose = _verboseJson.val;

            // 4. UI; each block guards itself, so one broken block does not hide the others.
            if (_body != null) _diag.Run("Body.CreateUI", _body.CreateUI);
            if (_link != null) _diag.Run("AppLink.CreateUI", _link.CreateUI);
            if (_verboseJson != null) _diag.Run("UI Verbose-Schalter", () => CreateToggle(_verboseJson));

            // 5. Start the link and run the self test.
            _initialized = true;
            if (_link != null)
            {
                _link.Ready = true;
                _diag.Run("Restart (Verbindung starten)", _link.Restart);
                _diag.Run("Selbsttest PluginData", () =>
                {
                    string error = _link.TestWritable();
                    _writable = error == null ? "ja (" + _link.ChannelDir + ")" : "NEIN: " + error;
                });
            }
            _diag.Step(_diag.FailureCount == 0
                ? "Init fertig, keine Fehler."
                : "Init fertig mit " + _diag.FailureCount + " Fehler(n): " + string.Join(", ", ToArray(_diag.FailedPhases)));
        }

        private void SendToApp(JSONClass evt)
        {
            if (_link != null && !_linkBroken) _link.Send(evt);
        }

        private static string[] ToArray(System.Collections.Generic.IEnumerable<string> items)
        {
            return new System.Collections.Generic.List<string>(items).ToArray();
        }

        // ---------------------------------------------------------------- status box

        private string SelfTest()
        {
            bool person = _atomType == "Person";
            string text = "<b>Selbsttest</b>\n";
            text += "  Person-Atom: " + (person ? "ja" : "NEIN (" + _atomType + ")") + "\n";
            if (!person) return text;
            text += "  Kopf-Audio (HeadAudioSource): " + (_body != null && _body.SpeechAvailable ? "ja" : "NEIN" + Reason(_body != null ? _body.SpeechError : "Body fehlt")) + "\n";
            text += "  Morphs (geometry): " + (_body != null && _body.MorphsAvailable ? "ja" : "NEIN" + Reason(_body != null ? _body.MorphsError : "Body fehlt")) + "\n";
            text += "  PluginData beschreibbar: " + _writable + "\n";
            text += "  Companion-App-Heartbeat: " + (_link != null && _link.AppSeen ? "ja" : "noch nicht") + "\n";
            return text;
        }

        private static string Reason(string error)
        {
            return string.IsNullOrEmpty(error) ? "" : " (" + error + ")";
        }

        private void RefreshStatus()
        {
            if (_statusJson == null) return;
            string uid = "?";
            try { if (containingAtom != null) uid = containingAtom.uid; }
            catch (Exception) { }
            _statusJson.val = "AIBody " + PluginVersion + " auf '" + uid + "'\n"
                + SelfTest()
                + (_live.Length > 0 ? "<b>Live</b>\n" + _live : "")
                + "<b>Start-Protokoll</b>\n" + (_diag != null ? _diag.Text : "");
        }

        // ---------------------------------------------------------------- frame loop

        private void Update()
        {
            if (!_initialized) return;
            float dt = Time.deltaTime;
            if (_link != null && !_linkBroken)
            {
                try { _link.Update(dt); }   // may hand body commands to _body synchronously
                catch (Exception e) { _linkBroken = true; _diag.Fail("AppLink.Update (Verbindung angehalten)", e); }
            }
            if (_body != null && !_bodyBroken)
            {
                try { _body.Update(dt); }
                catch (Exception e) { _bodyBroken = true; _diag.Fail("Body.Update (Körper angehalten)", e); }
            }

            _uiTimer += dt;
            if (_uiTimer < 0.5f) return;
            _uiTimer = 0f;
            try
            {
                string live = "";
                if (_link != null) live += _link.StatusText();
                if (_body != null) live += _body.StatusText();
                _live = live;
                RefreshStatus();
            }
            catch (Exception e)
            {
                _live = "Statusanzeige fehlgeschlagen: " + Diag.Describe(e) + "\n";
            }
        }

        // ---------------------------------------------------------------- teardown

        private void OnDisable()
        {
            if (!_initialized) return;
            try { if (_link != null) _link.Stop(); }
            catch (Exception e) { Log.Error("OnDisable: link stop failed", e); }
            try { if (_body != null) _body.Restore(); }
            catch (Exception e) { Log.Error("OnDisable: body restore failed", e); }
        }

        private void OnEnable()
        {
            if (!_initialized || _link == null) return;
            try { if (!_link.IsRunning && _link.Active) _link.Restart(); }
            catch (Exception e) { Log.Error("OnEnable: restart failed", e); }
        }

        private void OnDestroy()
        {
            OnDisable();
        }
    }
}
