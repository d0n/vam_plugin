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
using System;
using UnityEngine;

namespace AIBody
{
    public class AIBodyPlugin : MVRScript
    {
        public const string PluginVersion = "0.6.1";

        private AppLink _link;
        private Body _body;
        private JSONStorableBool _verboseJson;
        private JSONStorableString _statusJson;

        private bool _initialized;
        private float _uiTimer;

        public override void Init()
        {
            try
            {
                Log.Prefix = "AIBody: ";
                if (containingAtom == null || containingAtom.type != "Person")
                {
                    Log.Error("Add AIBody.cslist to the AI character's Person atom (Plugins tab).");
                    return;
                }

                _link = new AppLink(this, PluginVersion);
                _body = new Body(this, containingAtom, _link.Send);
                _link.OnBodyCommand = _body.Handle;
                _link.DecorateStatus = _body.AddStatus;

                _verboseJson = new JSONStorableBool("Verbose log", false, (bool v) => Log.Verbose = v);
                RegisterBool(_verboseJson);
                _statusJson = new JSONStorableString("Status", "Starting...");
                _link.CreateStorables();
                _body.CreateStorables();
                _body.CreateControllers();
                Log.Verbose = _verboseJson.val;

                CreateUI();
                _initialized = true;
                _link.Ready = true;
                _link.Restart();
            }
            catch (Exception e)
            {
                Log.Error("Init failed", e);
            }
        }

        private void CreateUI()
        {
            UiHelper.Header(this, "<b>AIBody " + PluginVersion + "</b> (needs the companion app running)", false);
            UIDynamicTextField status = CreateTextField(_statusJson);
            status.height = 320f;
            _body.CreateUI();
            _link.CreateUI();
            CreateToggle(_verboseJson);
        }

        // ---------------------------------------------------------------- frame loop

        private void Update()
        {
            if (!_initialized) return;
            try
            {
                float dt = Time.deltaTime;
                _link.Update(dt);   // may hand body commands to _body synchronously
                _body.Update(dt);

                _uiTimer += dt;
                if (_uiTimer > 0.5f)
                {
                    _uiTimer = 0f;
                    _statusJson.val = "AIBody " + PluginVersion + " on '" + containingAtom.uid + "'\n"
                        + _link.StatusText() + _body.StatusText();
                }
            }
            catch (Exception e)
            {
                Log.Error("Update failed; disabling the plugin", e);
                enabled = false;
            }
        }

        // ---------------------------------------------------------------- teardown

        private void OnDisable()
        {
            if (!_initialized) return;
            try
            {
                _link.Stop();
                _body.Restore();
            }
            catch (Exception e)
            {
                Log.Error("OnDisable cleanup failed", e);
            }
        }

        private void OnEnable()
        {
            if (_initialized && !_link.IsRunning && _link.Active) _link.Restart();
        }

        private void OnDestroy()
        {
            OnDisable();
        }
    }
}
