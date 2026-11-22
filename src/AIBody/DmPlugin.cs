// Dollmaster (VAMDeluxe, 2019; Leon's copy of Dollmaster, upstream github.com/vamdeluxe/DeluxePlugin, MIT) ported into
// AIBody (22.11.2026, Leon): same code, types prefixed Dm, namespace AIBody; changes only where the project rules need them
// (marked "AIBody port:").
//
// AIBody port: the old DollmasterPlugin was its own MVRScript on the female Person. One plugin = one MVRScript (project
// rule), so DmPlugin is a plain class run by AIBodyPlugin: its containingAtom is the AI character (the atom 'AI', where
// Dollmaster sat in the old scenes), the menu controls go to the AIBody tab "Dollmaster" (right column, shown only on that
// tab), the storables are registered on AIBody under their old names (saved scenes keep their values), Update / LateUpdate
// / RestoreFromJSON / PostRestore / OnDestroy are forwarded by AIBodyPlugin. "Activate" (off by default): while it is off
// nothing runs - no Update, no world panel, no helper atoms (thrust animation pattern, sound effect source), no persona
// audio loaded, no change to the head audio's lip sync or to AutoExpressions / Eyes.
using System;
using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using SimpleJSON;
using System.Linq;

namespace AIBody
{
    public class DmPlugin
    {
        public static string PLUGIN_PATH;
        public static string ASSETS_PATH;
        public static string LOAD_PATH;
        public static string VAMASUTRA_PATH;

        public DmPersonas personas;
        public DmPersonality personality;
        public DmPluginState ps;
        public DmUI ui;

        public List<DmBaseModule> modules = new List<DmBaseModule>();

        public DmConfig config;
        public DmExpressions expressions;
        public DmExpressionController expressionController;
        public DmThrustController thrustController;
        public DmThrustAutoController thrustAutoController;
        public DmHeadController headController;
        public DmArousal arousal;
        public DmBreathController breathController;
        public DmMontageController montageController;
        public DmPoseController poseController;
        public DmDressController dressController;
        public DmClimaxController climaxController;
        public DmKissController kissController;
        public DmSFXController sfxController;

        public AudioSourceControl headAudioSource;

        string lastAtomName = "";

        // ---------------------------------------------------------------- AIBody port: host, activation, menu

        /// <summary>AIBodyPlugin (the one MVRScript).</summary>
        public readonly MVRScript host;
        /// <summary>The AI character (Dollmaster's Person).</summary>
        public Atom containingAtom;
        public MVRPluginManager manager { get { return host.manager; } }
        /// <summary>True while AIBody speaks (Dollmaster's moans wait, AIBody's speech owns the head audio).</summary>
        public Func<bool> HostSpeaking;

        public bool Active { get; private set; }
        public bool Started { get; private set; }

        /// <summary>Helper atoms are made only while active; the creation is kept so a new activation makes them again.</summary>
        private readonly List<Func<IEnumerator>> _atomMakers = new List<Func<IEnumerator>>();
        private readonly List<string> _atomKeys = new List<string>();
        private float _savedVolumeTriggerMultiplier = -1f;

        // menu controls of the tab "Dollmaster" (hidden on the other tabs)
        private readonly List<UIDynamicToggle> _toggles = new List<UIDynamicToggle>();
        private readonly List<UIDynamicSlider> _sliders = new List<UIDynamicSlider>();
        private readonly List<UIDynamicPopup> _popups = new List<UIDynamicPopup>();
        private readonly List<UIDynamicButton> _buttons = new List<UIDynamicButton>();
        private readonly List<UIDynamic> _spacers = new List<UIDynamic>();
        private bool _menuVisible = true;
        public string Problem = "";

        public DmPlugin(MVRScript host, Atom person, string pluginFolder)
        {
            this.host = host;
            containingAtom = person;
            PLUGIN_PATH = pluginFolder;
        }

        public UIDynamicToggle CreateToggle(JSONStorableBool p, bool rightSide = false)
        {
            UIDynamicToggle t = host.CreateToggle(p, true);   // AIBody port: right column (left = AIBody's info field)
            _toggles.Add(t); Show(t, _menuVisible);
            return t;
        }

        public UIDynamicSlider CreateSlider(JSONStorableFloat p, bool rightSide = false)
        {
            UIDynamicSlider s = host.CreateSlider(p, true);
            _sliders.Add(s); Show(s, _menuVisible);
            return s;
        }

        public UIDynamicPopup CreatePopup(JSONStorableStringChooser p, bool rightSide = false)
        {
            UIDynamicPopup p2 = host.CreatePopup(p, true);
            _popups.Add(p2); Show(p2, _menuVisible);
            return p2;
        }

        public UIDynamicButton CreateButton(string label, bool rightSide = false)
        {
            UIDynamicButton b = host.CreateButton(label, true);
            _buttons.Add(b); Show(b, _menuVisible);
            return b;
        }

        public UIDynamic CreateSpacer(bool rightSide = false)
        {
            UIDynamic s = host.CreateSpacer(true);
            _spacers.Add(s); Show(s, _menuVisible);
            return s;
        }

        private readonly List<JSONStorableBool> _bools = new List<JSONStorableBool>();
        private readonly List<JSONStorableFloat> _floats = new List<JSONStorableFloat>();
        private readonly List<JSONStorableStringChooser> _choosers = new List<JSONStorableStringChooser>();
        private readonly List<JSONStorableUrl> _urls = new List<JSONStorableUrl>();

        public void RegisterBool(JSONStorableBool p) { host.RegisterBool(p); _bools.Add(p); }
        public void RegisterFloat(JSONStorableFloat p) { host.RegisterFloat(p); _floats.Add(p); }
        public void RegisterStringChooser(JSONStorableStringChooser p) { host.RegisterStringChooser(p); _choosers.Add(p); }
        public void RegisterAction(JSONStorableAction a) { host.RegisterAction(a); }
        public void RegisterUrl(JSONStorableUrl p) { host.RegisterUrl(p); _urls.Add(p); }

        /// <summary>
        /// AIBody port: Dollmaster was made after VaM restored the scene (the AI character appeared late): set its saved
        /// values now, from the plugin's JSON of the scene (same keys as the old plugin's storables).
        /// </summary>
        public void RestoreLate(JSONClass jc)
        {
            for (int i = 0; i < _bools.Count; i++) if (jc[_bools[i].name] != null) _bools[i].val = jc[_bools[i].name].AsBool;
            for (int i = 0; i < _floats.Count; i++) if (jc[_floats[i].name] != null) _floats[i].val = jc[_floats[i].name].AsFloat;
            for (int i = 0; i < _choosers.Count; i++) if (jc[_choosers[i].name] != null) _choosers[i].val = jc[_choosers[i].name].Value;
            for (int i = 0; i < _urls.Count; i++) if (jc[_urls[i].name] != null) _urls[i].val = jc[_urls[i].name].Value;
            RestoreFromJSON(jc);
        }

        public Coroutine StartCoroutine(IEnumerator routine) { return host.StartCoroutine(routine); }

        /// <summary>AIBody port: BaseModule.CreateAtom goes through here - made now when active, else at activation.</summary>
        public void MakeAtom(string key, Func<IEnumerator> maker)
        {
            int at = _atomKeys.IndexOf(key);
            if (at >= 0) _atomMakers[at] = maker;   // e.g. "Generate Animation Pattern" again: one maker per helper atom
            else { _atomKeys.Add(key); _atomMakers.Add(maker); }
            if (Active) host.StartCoroutine(maker());
        }

        private static void Show(Component c, bool on)
        {
            if (c != null && c.gameObject != null) c.gameObject.SetActive(on);
        }

        /// <summary>The tab "Dollmaster" is open (true) or another tab (false).</summary>
        public void ShowMenu(bool on)
        {
            _menuVisible = on;
            for (int i = 0; i < _toggles.Count; i++) Show(_toggles[i], on);
            for (int i = 0; i < _sliders.Count; i++) Show(_sliders[i], on);
            for (int i = 0; i < _popups.Count; i++) Show(_popups[i], on);
            for (int i = 0; i < _buttons.Count; i++) Show(_buttons[i], on);
            for (int i = 0; i < _spacers.Count; i++) Show(_spacers[i], on);
        }

        /// <summary>Checkbox "Activate".</summary>
        public void SetActive(bool on)
        {
            if (on == Active || !Started) { if (!Started) Active = on; return; }
            Active = on;
            try
            {
                if (on) OnActivated();
                else OnDeactivated();
            }
            catch (Exception e)
            {
                Problem = "Dollmaster " + (on ? "activation" : "deactivation") + " failed: " + e.Message;
                SuperController.LogError("AIBody: " + Problem + "\n" + e);
            }
        }

        private bool _eyesSaved;
        private EyesControl.LookMode _savedLookMode;

        private void OnActivated()
        {
            EyesControl eyes = containingAtom.GetStorableByID("Eyes") as EyesControl;
            if (eyes != null) { _savedLookMode = eyes.currentLookMode; _eyesSaved = true; }
            if (headAudioSource != null)
            {
                JSONStorableFloat vtm = headAudioSource.GetFloatJSONParam("volumeTriggerMultiplier");
                if (vtm != null) _savedVolumeTriggerMultiplier = vtm.val;
                // Prevent mouth from getting too big. (Dollmaster ExpressionController constructor)
                headAudioSource.SetFloatParamValue("volumeTriggerMultiplier", 0);
            }
            for (int i = 0; i < _atomMakers.Count; i++) host.StartCoroutine(_atomMakers[i]());
            sfxController.LoadClips();
            if (personality != null) personality.Load();
            config.Apply();
            montageController.LoadMontagesFromPath(montageController.montagePath.val);   // old Start()
        }

        private void OnDeactivated()
        {
            if (ui != null && ui.canvas != null) ui.canvas.enabled = false;
            modules.ForEach((module) =>
            {
                // removes the helper atoms, zeroes the expression morphs, frees the effect clips; the head controller keeps
                // its look target object for the next activation (its OnDestroy runs when the plugin is removed)
                if (module != headController) module.OnDestroy();
            });
            EyesControl eyes = containingAtom.GetStorableByID("Eyes") as EyesControl;
            if (eyes != null && _eyesSaved) eyes.currentLookMode = _savedLookMode;
            if (personality != null) personality.Unload();
            JSONStorable eyelids = containingAtom.GetStorableByID("EyelidControl");
            if (eyelids != null) eyelids.SetBoolParamValue("blinkEnabled", true);   // ExpressionController.Update switched it
            if (headAudioSource != null && _savedVolumeTriggerMultiplier >= 0f)
                headAudioSource.SetFloatParamValue("volumeTriggerMultiplier", _savedVolumeTriggerMultiplier);
        }

        // ---------------------------------------------------------------- Dollmaster.cs

        public void Init()
        {
            try
            {
                if (containingAtom == null || containingAtom.type != "Person")
                {
                    Problem = "Dollmaster needs the AI character (a Person atom named 'AI').";
                    return;
                }

                lastAtomName = containingAtom.uid;

                ASSETS_PATH = PLUGIN_PATH + "/Assets";
                VAMASUTRA_PATH = ASSETS_PATH + "/VAMasutra";
                LOAD_PATH = SuperController.singleton.currentLoadDir;

                headAudioSource = containingAtom.GetStorableByID("HeadAudioSource") as AudioSourceControl;

                RegisterActions();

                ui = new DmUI(host, 0.001f);
                ui.canvas.transform.Translate(0, 0.2f, 0);
                ui.canvas.enabled = false;   // AIBody port: shown by ui.Update only while active

                config = new DmConfig(this);

                personas = new DmPersonas(this);

                ps = new DmPluginState(this);

                arousal = new DmArousal(this);

                expressions = new DmExpressions(this);

                expressionController = new DmExpressionController(this);

                sfxController = new DmSFXController(this);

                thrustController = new DmThrustController(this);

                thrustAutoController = new DmThrustAutoController(this);

                breathController = new DmBreathController(this);

                headController = new DmHeadController(this);

                poseController = new DmPoseController(this);

                montageController = new DmMontageController(this, poseController);

                dressController = new DmDressController(this);

                climaxController = new DmClimaxController(this);

                kissController = new DmKissController(this);

                new DmTopButtons(this);

                //new WorldUI(this);

                CreateSpacer().height = 200;

                Started = true;
                if (Active) { Active = false; SetActive(true); }
            }
            catch (Exception e)
            {
                Problem = "Dollmaster start failed: " + e.Message;
                SuperController.LogError("AIBody: Dollmaster exception caught: " + e);
            }
        }

        void RegisterActions()
        {
            JSONStorableAction emotionTrigger = new JSONStorableAction("emotionTrigger", () =>
            {
                if (!Active) return;
                ForcePlayExpression();
            });
            RegisterAction(emotionTrigger);

            CreateButton("Test Emotion Trigger", true).button.onClick.AddListener(() =>
            {
                emotionTrigger.actionCallback();
            });

            JSONStorableAction climaxTrigger = new JSONStorableAction("climaxTrigger", () =>
            {
                if (!Active) return;
                arousal.MaxOut();
            });
            RegisterAction(climaxTrigger);

            CreateButton("Test Climax Trigger", true).button.onClick.AddListener(() =>
            {
                climaxTrigger.actionCallback();
            });


            CreateSpacer(true);

            CreateButton("Zero Pose Morphs", true).button.onClick.AddListener(() =>
            {
                DmExpressionController.ZeroPoseMorphs(containingAtom);
            });
        }

        /// <summary>Forwarded from AIBodyPlugin.RestoreFromJSON (after base).</summary>
        public void RestoreFromJSON(JSONClass jc)
        {
            if (dressController != null) dressController.OnRestore();
        }

        /// <summary>Forwarded from AIBodyPlugin.PostRestore.</summary>
        public void PostRestore()
        {
            if (Active && config != null) config.Apply();
        }

        public void Update()
        {
            if (!Active || !Started) return;
            try
            {
                modules.ForEach((module) =>
                {
                    module.Update();
                });

                //  name change handlers are breaking for some reason
                //  hack around this...
                if (lastAtomName != containingAtom.uid)
                {
                    HandleRename(lastAtomName, containingAtom.uid);
                    lastAtomName = containingAtom.uid;
                }
            }
            catch(Exception e)
            {
                SuperController.LogError("AIBody: Dollmaster exception caught: " + e);
            }
        }

        public void LateUpdate()
        {
            if (!Active || !Started) return;
            if (ui != null)
            {
                ui.Update();
            }
        }

        public void OnDestroy()
        {
            try
            {
                if (ui != null)
                {
                    ui.OnDestroy();
                }

                if (Active) OnDeactivated();
                Active = false;
                if (headController != null) headController.OnDestroy();

                if (personality != null)
                {
                    personality.OnDestroy();
                }
            }
            catch (Exception e)
            {
                SuperController.LogError("AIBody: Dollmaster exception caught: " + e);
            }

        }

        public void SetPersonality(string name)
        {
            if (personality != null)
            {
                personality.Unload();
            }
            personality = personas.GetPersonality(name);
            if (Active && personality != null) personality.Load();   // AIBody port: audio is loaded only while active
        }

        public void PlayAudio(NamedAudioClip clip)
        {
            if (clip != null)
            {
                if (HostSpeaking != null && HostSpeaking()) return;   // AIBody port: AIBody's speech owns the head audio
                headAudioSource.PlayNow(clip);
            }
        }

        public void TriggerExpression()
        {
            sfxController.Trigger();

            if (climaxController.isClimaxing || climaxController.isResting)
            {
                return;
            }

            if (thrustController.sliderValue <= .2f)
            {
                return;
            }

            arousal.Trigger();
            headController.Trigger();
            expressionController.Trigger();
            poseController.Trigger();
        }

        public void ForcePlayExpression()
        {
            arousal.Trigger();
            expressionController.StartExpression();
            poseController.Trigger();
        }

        public void TriggerClimax()
        {
            expressionController.TriggerClimax();
            montageController.RandomPose();
        }

        public static NamedAudioClip LoadAudio(string path)
        {
            string localPath = SuperController.singleton.NormalizeLoadPath(path);
            NamedAudioClip existing = URLAudioClipManager.singleton.GetClip(localPath);
            if (existing != null)
            {
                return existing;
            }

            URLAudioClip clip = URLAudioClipManager.singleton.QueueClip(SuperController.singleton.NormalizeMediaPath(path));
            if (clip == null)
            {
                return null;
            }

            NamedAudioClip nac = URLAudioClipManager.singleton.GetClip(clip.uid);
            if (nac == null)
            {
                return null;
            }
            return nac;
        }

        protected void HandleRename(string oldId, string newId)
        {
            modules.ForEach((module) =>
            {
                module.HandleRename(oldId, newId);
            });
        }

        public static Atom GetSomeoneElse(Atom notThisPerson)
        {
            List<Atom> otherPeople = SuperController.singleton.GetAtoms().Where(other =>
            {
                return other.type == "Person" && other != notThisPerson;
            }).ToList();

            if (otherPeople.Count > 0)
            {
                return otherPeople[0];
            }
            return null;
        }
    }
}
