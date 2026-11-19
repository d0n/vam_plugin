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
// Layout: left column = ONE big info panel (info and help for the open tab; self-test, recent
// events and startup log in the tab Config), always visible. Right column = a row of tab buttons and below it ONLY
// the controls of the active tab (no text fields; help and status go to the big field). Switching
// tabs removes the old controls with the standard Remove* methods (UiPage, evidence E17/E18).
// Tabs (version 15): Voice (Voice Mode: link, Question and Answer, realtime, API Reconnect, sound
// test; Voice > AI Character: AI mode, voice, engines, proactive) | AI Character (poses, expression
// and gesture, body of this Person) | Client Character (microphone, push-to-talk, voice barge-in)
// | Config (Reload Config JSON, Companion inbox poll interval = storable "File poll interval (s)",
// how often the companion inbox is read; verbose log).
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
        public const string PluginVersion = "22";   // = package number d0n.AIBody.22.var (scheme since version 12)

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
        private string _writable = "not checked yet";
        private string _linkLive = "";   // connection / companion live lines (tab Voice)
        private string _bodyLive = "";   // speech / body live lines (tab AI Character)

        // Tab names: self-explanatory, never just "AI" / "Client" (Leon, 17.11.2026). The former tabs
        // AI, Post and Advanced are gone (docs/BACKLOG.md, removed menu entries).
        private static readonly string[] Tabs = { "Voice", "AI Character", "Client Character", "Config" };
        private string _configStatus = "";   // result of "Reload Config JSON", shown in the info field
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
            _statusJson = new JSONStorableString("Status", "AIBody " + PluginVersion + " starting ...");

            // 1. Header and status box before anything that could fail.
            try
            {
                // Version 17: no header line above the field any more (it only repeated the version and the
                // hint that the companion app must run; both are in the field's first line / tab Voice).
                UIDynamicTextField status = CreateTextField(_statusJson);
                // The one big info field (no small text fields in the tabs), only the open tab's info.
                // Version 17: 1800, about the height of the longest tab on the right (AI Character with the
                // tab buttons), so the left column needs no extra scrolling. TODO(verify): height in VaM.
                status.height = 1800f;
            }
            catch (Exception e)
            {
                _diag.Fail("Create info panel", e);
            }
            _diag.Changed = RefreshStatus;
            _diag.Step("Init started (AIBody " + PluginVersion + ")");

            // 2. Right atom?
            try
            {
                _atomType = containingAtom != null ? containingAtom.type : "(no atom)";
            }
            catch (Exception e)
            {
                _diag.Fail("Read atom type", e);
            }
            if (_atomType != "Person")
            {
                string msg = "This plugin belongs in the Plugins tab of a Person atom, not in Session/Scene "
                    + "plugins or on an Empty. Current atom type: " + _atomType;
                _diag.Warn(msg);
                _diag.Step("Init stopped: AIBody stays inactive here. Remove it and add it to the AI "
                    + "character (Person) via Plugins > Add Plugin.");
                return;
            }
            _diag.Step("Atom: Person '" + containingAtom.uid + "'");

            // 3. Components and storables, each phase on its own.
            _diag.Run("Create AppLink", () => _link = new AppLink(this, PluginVersion, _diag));
            _diag.Run("Create Body", () => _body = new Body(this, containingAtom, SendToApp, _diag));
            if (_link != null && _body != null)
            {
                _link.OnBodyCommand = _body.Handle;
                _link.DecorateStatus = _body.AddStatus;
                _link.OnAppRestarted = () =>
                {
                    // The restarted app forgot its queue and echo gate: drop the old speech too.
                    _body.StopSpeaking();
                    _diag.Step("Companion app restarted: pending speech cancelled.");
                };
                _body.PluginFolder = FindPluginFolder;
                _link.OnPathsChanged = () =>
                {
                    _body.ExpressionsPath = _link.ExpressionsPath;
                    _body.GesturesPath = _link.GesturesPath;
                    _body.ReloadConfigFiles();
                };
            }
            _diag.Run("Verbose log toggle", () =>
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
            _diag.Run("UI tab bar", () =>
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
                _diag.Run("Restart (start connection)", _link.Restart);
                _diag.Run("Self-test PluginData", () =>
                {
                    string error = _link.TestWritable();
                    _writable = error == null ? "yes (" + _link.ChannelDir + ")" : "NO: " + error;
                });
            }
            _diag.Step(_diag.FailureCount == 0
                ? "Init complete, no errors."
                : "Init complete with " + _diag.FailureCount + " error(s): " + string.Join(", ", ToArray(_diag.FailedPhases)));
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
            catch (Exception e) { _diag.Fail("Switch tab (remove old controls)", e); }
            _tab = index;
            try
            {
                switch (index)
                {
                    case 0: // Voice
                        _page.Header("<b>Voice Mode</b> (connection, mode, sound test)");
                        _page.Button(QaButtonLabel, 90f, EnableSimpleQa);
                        if (_link != null) _link.BuildVoiceModeTab(_page);
                        if (_body != null) _body.BuildVoiceModeTab(_page);
                        _page.Header("<b>Voice > AI Character</b> (the character's voice and speech AI)");
                        if (_link != null) _link.BuildAiVoiceSection(_page);
                        break;
                    case 1: // AI Character
                        if (_body != null) _body.BuildCharacterTab(_page);
                        break;
                    case 2: // Client Character
                        if (_link != null) _link.BuildClientCharacterTab(_page);
                        break;
                    default: // Config (former Config + Advanced)
                        _page.Header("<b>Config</b> (config.json, connection, logging)");
                        if (_link != null) _link.BuildConfigTab(_page, ReloadConfigJson);
                        _page.Toggle(_verboseJson);
                        break;
                }
                RefreshStatus();
            }
            catch (Exception e)
            {
                _diag.Fail("UI Tab " + name, e);
            }
        }

        // ---------------------------------------------------------------- config.json

        /// <summary>Version 21: shown on two centered lines (a newline in the button label).</summary>
        public const string QaButtonLabel = "Question\n& Answer";

        /// <summary>
        /// Button "Reload Config JSON": applies config.json to the UI (paths, connection, engines, mic,
        /// body, ai keys of the tabs) and pushes the result to the companion app.
        /// </summary>
        private string _simpleQa = "Question and Answer: you ask a question (speak it, or type it into the companion app's console) and the "
            + "character speaks Grok's answer. This sets AI mode to 'qa' and turns Body control off (tab AI Character), "
            + "so the character only talks. It needs an xAI API key.";

        /// <summary>
        /// Button "Question and Answer" (until version 20 "Simple Q&amp;A mode"): AI mode qa (STT -> Grok -> TTS, speech only) and body
        /// control off, saved to config.json and sent to the companion app.
        /// </summary>
        private void EnableSimpleQa()
        {
            if (_link != null) _link.SetSimpleQa();
            if (_body != null) _body.SetBodyControl(false);
            _simpleQa = "Question and Answer is on (" + DateTime.Now.ToString("HH:mm:ss") + "): AI mode is 'qa' and Body control is off. "
                + "Press 'Play test tone' to check that you can hear the character, then ask a question.";
        }

        private void ReloadConfigJson()
        {
            if (_link == null) return;
            try
            {
                JSONClass file = _link.LoadSettingsFile();
                if (file == null)
                {
                    _configStatus = "No valid config.json at " + _link.SettingsPath + "; nothing changed.";
                    return;
                }
                _link.ApplySettings(file);
                if (_body != null) _body.ApplySettings(file);
                JSONClass advanced = file["advanced"] as JSONClass;
                if (advanced != null && _verboseJson != null)
                    _verboseJson.val = Protocol.GetBool(advanced, "verbose_log", _verboseJson.val);
                if (_body != null) _body.ReloadConfigFiles();
                _link.MarkConfigDirty();
                _configStatus = "config.json reloaded (" + DateTime.Now.ToString("HH:mm:ss") + "): " + _link.SettingsPath;
            }
            catch (Exception e)
            {
                _configStatus = "Loading config.json failed: " + Diag.Describe(e);
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
                _diag.Run("Read config.json", () => file = _link.LoadSettingsFile());
                if (file != null) _diag.Run("Key file paths from config.json", () => _link.AdoptKeyFiles(file));
                if (file != null && !_settingsInitJson.val)
                {
                    _diag.Run("Apply settings from config.json (new scene)", () =>
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
                _diag.Fail("Write config.json", e);
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
            string text = "<b>Self-test</b>\n";
            text += "  Person atom: " + (person ? "yes" : "NO (" + _atomType + ")") + "\n";
            if (!person) return text;
            text += "  Head audio (HeadAudioSource): " + (_body != null && _body.SpeechAvailable ? "yes" : "NO" + Reason(_body != null ? _body.SpeechError : "Body missing")) + "\n";
            text += "  Morphs (geometry): " + (_body != null && _body.MorphsAvailable ? "yes" : "NO" + Reason(_body != null ? _body.MorphsError : "Body missing")) + "\n";
            if (_body != null) text += _body.SelfTestText();
            text += "  PluginData writable: " + _writable + "\n";
            text += "  Companion app heartbeat: " + (_link == null ? "-" : _link.AppSeen ? "yes" : _link.AppLost ? "DISCONNECTED (reconnects automatically)" : "not yet") + "\n";
            return text;
        }

        /// <summary>Help and status for the open tab (the tabs themselves have no text fields).</summary>
        private string TabInfo()
        {
            if (_tab < 0 || _tab >= Tabs.Length) return "";
            string text = "";
            try
            {
                switch (_tab)
                {
                    case 0:
                        text = (_simpleQa.Length > 0 ? _simpleQa + "\n" : "") + (_link != null ? _link.VoiceInfoText() : "")
                            + Section("Connection", _linkLive);
                        break;
                    case 1:
                        text = (_body != null ? _body.CharacterInfoText() : "") + Section("Body", _bodyLive);
                        break;
                    case 2:
                        text = _link != null ? _link.ClientInfoText() : "";
                        break;
                    default:
                        text = (_link != null ? "config.json: " + _link.SettingsPath + "\n" + _link.ChannelInfoText() + "\n"
                                + _link.FilePollInfoText() + "\n" : "")
                            + (_configStatus.Length > 0 ? _configStatus + "\n" : "")
                            + SelfTest()
                            + (Log.Verbose && Log.RecentText().Length > 0 ? "<b>Recent events</b> (Verbose log)\n" + Log.RecentText() : "")
                            + "<b>Startup log</b>\n" + (_diag != null ? _diag.Text : "");
                        break;
                }
            }
            catch (Exception e)
            {
                text = "Info failed: " + Diag.Describe(e) + "\n";
            }
            if (text.Length > 0 && !text.EndsWith("\n")) text += "\n";
            return "<b>Info: " + Tabs[_tab] + "</b>\n" + text;
        }

        private static string Section(string title, string body)
        {
            return string.IsNullOrEmpty(body) ? "" : "<b>" + title + "</b>\n" + body;
        }

        /// <summary>One line on every tab: start result; failures in red (details in the tab Config).</summary>
        private string StartLine()
        {
            if (_diag == null) return "";
            if (_diag.FailureCount == 0) return _initialized ? "Startup: ok\n" : "Starting ...\n";
            return "<color=red>Startup: " + _diag.FailureCount + " error(s) (" + string.Join(", ", ToArray(_diag.FailedPhases))
                + ")</color> - details in the tab Config\n";
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
            // Version 16: only the open tab's info (self test, recent events and start log: tab Config).
            _statusJson.val = "<b>AIBody " + PluginVersion + "</b> on '" + uid + "' - " + StartLine()
                + TabInfo();
        }

        // ---------------------------------------------------------------- frame loop

        private void Update()
        {
            if (!_initialized) return;
            float dt = Time.deltaTime;
            if (_link != null && !_linkBroken)
            {
                try { _link.Update(dt); }   // may hand body commands to _body synchronously
                catch (Exception e) { _linkBroken = true; _diag.Fail("AppLink.Update (connection stopped)", e); }
            }
            if (_body != null && !_bodyBroken)
            {
                try { _body.Update(dt); }
                catch (Exception e) { _bodyBroken = true; _diag.Fail("Body.Update (body stopped)", e); }
            }

            try { UpdateSettings(dt); }
            catch (Exception e) { _settingsChecked = true; _diag.Fail("config.json", e); }

            if (_body != null && _body.RebuildTab)
            {
                _body.RebuildTab = false;   // next frame, not inside the button's own click handler
                if (_tab == 1) ShowTab(_tab);
            }

            _uiTimer += dt;
            if (_uiTimer < 0.5f) return;
            _uiTimer = 0f;
            try
            {
                _linkLive = _link != null ? _link.StatusText() : "";
                _bodyLive = _body != null ? _body.StatusText() : "";
                RefreshStatus();
            }
            catch (Exception e)
            {
                _linkLive = "Status display failed: " + Diag.Describe(e) + "\n";
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
