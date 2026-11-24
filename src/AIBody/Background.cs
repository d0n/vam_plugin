// Scene background colour (version 36, Don): tab Config > "Set background color" + a colour picker (default #00FF00).
// AIBody's own implementation; no code from other plugins.
//
// What it does while "Set background color" is on (checked once per second, no allocation when nothing changed):
//   - the player's camera (CameraTarget.centerTarget.targetCamera) clears to one solid colour:
//     Camera.clearFlags = CameraClearFlags.SolidColor and Camera.backgroundColor = the chosen colour
//     (the pattern of lfe999's AutoPupil, a sandboxed VaM plugin: docs/API_AUDIT.md E30);
//   - VaM's skybox is hidden: SkyshopLightController.singleton, its bool parameter "showSkybox" set to false (E31).
// Every camera it touched and the skybox get their old values back when the toggle goes off, the plugin is disabled
// or removed. VaM itself only shows the colour; a headset / streaming app keys it out (chroma key on the same colour).
// TODO(verify) in VaM: the VR eye camera is centerTarget.targetCamera (desktop and VR), and nothing in VaM resets
// clearFlags each frame (if it does, the once-per-second check sets it again).
using System;
using System.Collections.Generic;
using UnityEngine;

namespace AIBody
{
    public class BackgroundController
    {
        public const float CheckInterval = 1f;

        private class Touched
        {
            public Camera Cam;
            public CameraClearFlags Flags;
            public Color Color;
        }

        private readonly List<Touched> _touched = new List<Touched>(2);
        private bool _on;
        private Color _color = new Color(0f, 1f, 0f, 1f);
        private float _timer = CheckInterval;
        private JSONStorableBool _skybox;
        private bool _skyboxTouched;
        private bool _skyboxWas;
        private bool _failed;

        /// <summary>One line for the info field.</summary>
        public string Status = "off";

        public bool On { get { return _on; } }

        /// <summary>New wish from the menu; applied on the next Tick (the same frame's Update).</summary>
        public void Set(bool on, Color color)
        {
            _on = on;
            _color = color;
            _timer = CheckInterval;
            _failed = false;
        }

        public void Tick(float dt)
        {
            _timer += dt;
            if (_timer < CheckInterval) return;
            _timer = 0f;
            if (_failed) return;
            try
            {
                if (_on) Apply();
                else if (_touched.Count > 0 || _skyboxTouched) Restore();
            }
            catch (Exception e)
            {
                _failed = true;   // only the background stops; it is tried again when the setting changes
                Status = "failed: " + Diag.Describe(e);
                Log.Error("Background color: " + Status);
            }
        }

        private static Camera CurrentCamera()
        {
            CameraTarget target = CameraTarget.centerTarget;
            return target != null ? target.targetCamera : null;
        }

        private void Apply()
        {
            Camera cam = CurrentCamera();
            if (cam == null)
            {
                Status = "on, but no camera found yet";
                return;
            }
            Touched t = null;
            for (int i = 0; i < _touched.Count; i++) if (_touched[i].Cam == cam) t = _touched[i];
            if (t == null)
            {
                t = new Touched { Cam = cam, Flags = cam.clearFlags, Color = cam.backgroundColor };
                _touched.Add(t);
            }
            if (cam.clearFlags != CameraClearFlags.SolidColor) cam.clearFlags = CameraClearFlags.SolidColor;
            if (!SameColor(cam.backgroundColor, _color)) cam.backgroundColor = _color;
            HideSkybox();
            Status = "on, " + Hex(_color);
        }

        private void HideSkybox()
        {
            if (_skybox == null)
            {
                SkyshopLightController sky = SkyshopLightController.singleton;
                if (sky != null) _skybox = sky.GetBoolJSONParam("showSkybox");
                if (_skybox == null) return;
            }
            if (!_skyboxTouched)
            {
                _skyboxTouched = true;
                _skyboxWas = _skybox.val;
            }
            if (_skybox.val) _skybox.val = false;
        }

        /// <summary>Gives every touched camera and the skybox their old values back.</summary>
        public void Restore()
        {
            for (int i = 0; i < _touched.Count; i++)
            {
                Touched t = _touched[i];
                if (t.Cam == null) continue;   // camera gone (VR / desktop switch, scene change)
                try
                {
                    t.Cam.clearFlags = t.Flags;
                    t.Cam.backgroundColor = t.Color;
                }
                catch (Exception e) { Log.Debug("Background color: restoring a camera failed: " + e.Message); }
            }
            _touched.Clear();
            if (_skyboxTouched && _skybox != null)
            {
                try { _skybox.val = _skyboxWas; }
                catch (Exception e) { Log.Debug("Background color: restoring the skybox failed: " + e.Message); }
            }
            _skyboxTouched = false;
            _skybox = null;
            Status = "off";
        }

        public static bool SameColor(Color a, Color b)
        {
            return Math.Abs(a.r - b.r) < 0.002f && Math.Abs(a.g - b.g) < 0.002f && Math.Abs(a.b - b.b) < 0.002f;
        }

        public static string Hex(Color c)
        {
            return "#" + Byte(c.r).ToString("X2") + Byte(c.g).ToString("X2") + Byte(c.b).ToString("X2");
        }

        private static int Byte(float v)
        {
            int b = (int)Math.Round(v * 255f);
            return b < 0 ? 0 : b > 255 ? 255 : b;
        }
    }
}
