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
//
// Layout: left column = header + status box (Selbsttest, live state, start log), always visible.
// Right column = a row of tab buttons and below it the controls of the active tab. Switching tabs
// removes the old controls with the standard Remove* methods (UiPage, evidence E17/E18).
// Tabs: Voice Mode (link, Einfacher Q&A-Modus, API Reconnect, sound test) | AI (engines, key file paths + status, Delay
// placeholder, proactive) | AI Character (AI mode, voice, body of this Person) | Client Character
// (microphone, push-to-talk, voice barge-in) | Post (channel, paths) | Config | Erweitert.
//
// config.json (Saves/PluginData/AIBody/config.json, one global file) is shared with the companion
// app, one object per tab category (docs/CONFIG.md). The plugin UI (saved with the scene) wins
// and is written back; a scene without saved AIBody settings is seeded from the file once.
using System;
using SimpleJSON;
using MVR.FileManagementSecure;
using UnityEngine;

namespace AIBody
{
    public class AIBodyPlugin : MVRScript
    {
        public const string PluginVersion = "0.7.2";

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

        /// <summary>Label of the connection tab, as the user said it ("Post"; may be meant as "Port").</summary>
        public const string PostTabLabel = "Post";

        private static readonly string[] Tabs = { "Voice Mode", "AI", "AI Character", "Client Character", PostTabLabel, "Config", "Erweitert" };
        private readonly JSONStorableString _configStatusJson = new JSONStorableString("Config status", "");
        private UiPage _page;
        private int _tab = -1;

        private JSONStorableBool _settingsInitJson;   // saved with the scene: "this scene has AIBody settings"
        private float _settingsAge;
        private float _settingsTimer;
        private bool _settingsChecked;
        private bool _settingsWriteWarned;
        private string _lastSettingsText;
        private string _lastSettingsPath;

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
                _link.OnAppRestarted = () =>
                {
                    // The restarted app forgot its queue and echo gate: drop the old speech too.
                    _body.StopSpeaking();
                    _diag.Step("Companion-App neu gestartet: alte Sprachausgabe abgebrochen.");
                };
                _body.PluginFolder = FindPluginFolder;
                _link.OnPathsChanged = () =>
                {
                    _body.ExpressionsPath = _link.ExpressionsPath;
                    _body.GesturesPath = _link.GesturesPath;
                    _body.ReloadConfigFiles();
                };
            }
            _diag.Run("Verbose-Schalter", () =>
            {
                _verboseJson = new JSONStorableBool("Verbose log", false, (bool v) =>
                {
                    Log.Verbose = v;
                    if (_link != null) _link.MarkConfigDirty();   // tells the companion (config event "advanced")
                });
                RegisterBool(_verboseJson);
                _settingsInitJson = new JSONStorableBool("Settings initialized", false, (bool v) => { });
                RegisterBool(_settingsInitJson);
            });
            if (_link != null) _diag.Run("AppLink.CreateStorables", _link.CreateStorables);
            if (_body != null)
            {
                _diag.Run("Body.CreateStorables", _body.CreateStorables);
                _diag.Run("Body.CreateControllers", _body.CreateControllers);
            }
            if (_verboseJson != null) Log.Verbose = _verboseJson.val;

            // 4. UI: tab buttons (right column), then the first tab. Each tab guards itself.
            _diag.Run("UI Tab-Leiste", () =>
            {
                _page = new UiPage(this, true);
                for (int i = 0; i < Tabs.Length; i++)
                {
                    int index = i;
                    CreateButton(Tabs[i], true).button.onClick.AddListener(() => ShowTab(index));
                }
            });
            ShowTab(0);

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

        /// <summary>
        /// Folder of the loaded AIBody.cslist, e.g. "d0n.AIBody.8:/Custom/Scripts/d0n/AIBody", read from
        /// the atom's PluginManager like Dollmaster's GetPluginPath (evidence E1, L283-290).
        /// </summary>
        private string FindPluginFolder()
        {
            string pluginId = storeId.Split('_')[0];
            MVRPluginManager manager = containingAtom.GetStorableByID("PluginManager") as MVRPluginManager;
            if (manager == null) return null;
            string script = manager.GetJSON(true, true)["plugins"][pluginId].Value;
            int cut = script.LastIndexOfAny(new char[] { '/', '\\' });
            return cut > 0 ? script.Substring(0, cut) : null;
        }

        // ---------------------------------------------------------------- tabs

        private void ShowTab(int index)
        {
            if (_page == null) return;
            string name = Tabs[index];
            try { _page.Clear(); }
            catch (Exception e) { _diag.Fail("Tab wechseln (alte Elemente entfernen)", e); }
            _tab = index;
            try
            {
                _page.Header("<b>" + name + "</b>");
                switch (index)
                {
                    case 0: // Voice Mode
                        _page.Button("Einfacher Q&A-Modus", EnableSimpleQa);
                        _page.Text(_simpleQaJson, 110f);
                        if (_link != null) _link.BuildVoiceModeTab(_page);
                        if (_body != null) _body.BuildVoiceModeTab(_page);
                        break;
                    case 1: // AI
                        if (_link != null) _link.BuildAiTab(_page);
                        break;
                    case 2: // AI Character
                        if (_link != null) _link.BuildCharacterVoice(_page);
                        if (_body != null) _body.BuildCharacterTab(_page);
                        break;
                    case 3: // Client Character
                        if (_link != null) _link.BuildClientCharacterTab(_page);
                        break;
                    case 4: // Post
                        if (_link != null) _link.BuildPostTab(_page);
                        break;
                    case 5: // Config
                        if (_link != null) _link.BuildConfigTab(_page, ReloadConfigJson, _configStatusJson);
                        break;
                    default: // Erweitert
                        if (_link != null) _link.BuildAdvancedTab(_page);
                        _page.Toggle(_verboseJson);
                        break;
                }
            }
            catch (Exception e)
            {
                _diag.Fail("UI Tab " + name, e);
            }
        }

        // ---------------------------------------------------------------- config.json

        /// <summary>
        /// Button "Reload Config JSON": applies config.json to the UI (paths, connection, engines, mic,
        /// body, ai keys of the tabs) and pushes the result to the companion app.
        /// </summary>
        private readonly JSONStorableString _simpleQaJson = new JSONStorableString("Simple Q&A help",
            "Einfacher Q&A-Modus: Frage sprechen oder in der Companion-Konsole tippen -> Grok antwortet -> "
            + "die Person spricht. Setzt AI mode = qa und Body control = aus (Tab AI Character). Braucht einen xAI-Key.");

        /// <summary>
        /// Button "Einfacher Q&amp;A-Modus": AI mode qa (STT -> Grok -> TTS, speech only) and body
        /// control off, saved to config.json and sent to the companion app.
        /// </summary>
        private void EnableSimpleQa()
        {
            if (_link != null) _link.SetSimpleQa();
            if (_body != null) _body.SetBodyControl(false);
            _simpleQaJson.val = "Einfacher Q&A-Modus an (" + DateTime.Now.ToString("HH:mm:ss") + "): AI mode = qa, Body control = aus. "
                + "Jetzt 'Test-Ton abspielen', dann eine Frage stellen.";
        }

        private void ReloadConfigJson()
        {
            if (_link == null) return;
            try
            {
                JSONClass file = _link.LoadSettingsFile();
                if (file == null)
                {
                    _configStatusJson.val = "Keine gültige config.json unter " + _link.SettingsPath + " – nichts geändert.";
                    return;
                }
                _link.ApplySettings(file);
                if (_body != null) _body.ApplySettings(file);
                JSONClass advanced = file["advanced"] as JSONClass;
                if (advanced != null && _verboseJson != null)
                    _verboseJson.val = Protocol.GetBool(advanced, "verbose_log", _verboseJson.val);
                if (_body != null) _body.ReloadConfigFiles();
                _link.MarkConfigDirty();
                _configStatusJson.val = "config.json neu geladen (" + DateTime.Now.ToString("HH:mm:ss") + "): " + _link.SettingsPath;
            }
            catch (Exception e)
            {
                _configStatusJson.val = "config.json laden fehlgeschlagen: " + Diag.Describe(e);
                _diag.Fail("Reload Config JSON", e);
            }
        }

        private void UpdateSettings(float dt)
        {
            if (_link == null || _settingsInitJson == null) return;
            _settingsAge += dt;
            // Wait until VaM restored the scene's saved values (that happens after Init).
            // TODO(verify): 1.5 s is enough after a scene load.
            if (!_settingsChecked)
            {
                if (_settingsAge < 1.5f) return;
                _settingsChecked = true;
                JSONClass file = null;
                _diag.Run("config.json lesen", () => file = _link.LoadSettingsFile());
                if (file != null) _diag.Run("Key-Datei-Pfade aus config.json", () => _link.AdoptKeyFiles(file));
                if (file != null && !_settingsInitJson.val)
                {
                    _diag.Run("Einstellungen aus config.json übernehmen (neue Szene)", () =>
                    {
                        _link.ApplySettings(file);
                        if (_body != null) _body.ApplySettings(file);
                        JSONClass advanced = file["advanced"] as JSONClass;
                        if (advanced != null && _verboseJson != null)
                            _verboseJson.val = Protocol.GetBool(advanced, "verbose_log", _verboseJson.val);
                    });
                }
                _settingsInitJson.val = true;
            }
            _settingsTimer += dt;
            if (_settingsTimer < 1f) return;
            _settingsTimer = 0f;
            WriteSettings();
        }

        /// <summary>Writes the UI values back to config.json when they changed (UI wins).</summary>
        private void WriteSettings()
        {
            try
            {
                JSONClass root = new JSONClass();
                root["version"].AsInt = 1;
                root["written_by"] = "AIBody plugin " + PluginVersion;
                _link.WriteSettings(root);
                if (_body != null) _body.WriteSettings(root);
                JSONClass advanced = root["advanced"] as JSONClass;
                if (advanced != null && _verboseJson != null) advanced["verbose_log"].AsBool = _verboseJson.val;
                string text = root.ToString();
                string path = _link.SettingsPath;
                if (text == _lastSettingsText && path == _lastSettingsPath) return;
                // Keep the companion-only section ("ai": persona, engine settings, key FILE paths)
                // that the companion app and the user maintain; the plugin has no UI for it.
                // The UI's ai keys (mode, proactive, voice barge-in) are merged into it.
                JSONClass existing = _link.ReadSettingsRoot();
                if (existing != null)
                {
                    JSONClass ai = existing["ai"] as JSONClass;
                    if (ai != null)
                    {
                        AppLink.MergeAi(ai, root["ai"] as JSONClass);
                        root["ai"] = ai;
                    }
                }
                FileManagerSecure.CreateDirectory(AppLink.DataRoot);
                FileManagerSecure.WriteAllText(path, root.ToString());
                _lastSettingsText = text;
                _lastSettingsPath = path;
                Log.Debug("settings written: " + path);
            }
            catch (Exception e)
            {
                if (_settingsWriteWarned) return;
                _settingsWriteWarned = true;
                _diag.Fail("config.json schreiben", e);
            }
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
            text += "  Companion-App-Heartbeat: " + (_link == null ? "-" : _link.AppSeen ? "ja" : _link.AppLost ? "GETRENNT (verbindet automatisch neu)" : "noch nicht") + "\n";
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
                + (Log.Verbose && Log.RecentText().Length > 0 ? "<b>Letzte Ereignisse</b> (Verbose log)\n" + Log.RecentText() : "")
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

            try { UpdateSettings(dt); }
            catch (Exception e) { _settingsChecked = true; _diag.Fail("config.json", e); }

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
