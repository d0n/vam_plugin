// Root-position reset on pose load (version 63): a pose keeps the offsets of its controllers relative to each other, but
// the body is put back over the AI character's control point (the Person's main controller "control" = the place the
// scene or the Body position sliders gave her, the "zero point"). Without it the hips can end up far from the control
// point after a few poses (a pose file stores where the hips are relative to its own root), she walks off her place,
// runs into other objects and the physics load grows.
//
// This file is pure C# (no VaM or Unity types) so tests run it outside VaM (companion/tests/test_version63.py). The VaM
// side is BodyMover.CenterOnControl / PoseGuard in PoseController.cs (Atom.mainController, Atom.freeControllers,
// GetStorableByID("hipControl") as FreeControllerV3, FreeControllerV3.transform position / rotation: E1, E6, E12, E28, the
// same calls BodyMover.Relocate already makes).
using System;

namespace AIBody
{
    public static class RootReset
    {
        /// <summary>The controller whose place counts as "the body": the hips.</summary>
        public const string BodyControl = "hipControl";
        /// <summary>Hips closer than this to the control point (flat, in metres) are left alone (no jitter, no needless move).</summary>
        public const float ToleranceMetres = 0.02f;
        /// <summary>Default of the toggle "Center body on control point" / config.json body.pose_root_reset.</summary>
        public const bool DefaultOn = true;

        /// <summary>
        /// The hips' offset from the control point in the control point's own frame (x = right, y = up, z = forward, metres)
        /// -> the shift (same frame) that puts the hips straight over the control point: only the flat part (x, z) is taken
        /// back, the height (y) stays (sitting, kneeling and lying poses keep their height). Returns the flat distance moved
        /// (0 = within ToleranceMetres, nothing to do; the shift is then 0).
        /// </summary>
        public static float LocalShift(float x, float y, float z, float tolerance, out float sx, out float sy, out float sz)
        {
            sx = 0f; sy = 0f; sz = 0f;
            if (float.IsNaN(x) || float.IsNaN(z) || float.IsInfinity(x) || float.IsInfinity(z)) return 0f;
            float flat = (float)Math.Sqrt(x * x + z * z);
            if (flat <= Math.Max(0f, tolerance)) return 0f;
            sx = -x;
            sz = -z;
            return flat;
        }

        /// <summary>Which pose changes are re-centred: every pose AIBody applies (pose commands, Apply Pose, idle poses, the
        /// AI's pose tool) and the start of the idle movement - not a Dollmaster montage (it places two people relative to
        /// each other; re-centring one would break the arrangement) and nothing while the toggle is off.</summary>
        public static bool Applies(bool enabled, bool montage)
        {
            return enabled && !montage;
        }
    }
}
