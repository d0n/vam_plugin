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
        /// AI's pose tool) - not a Dollmaster montage (it places two people relative to
        /// each other; re-centring one would break the arrangement) and nothing while the toggle is off.</summary>
        public static bool Applies(bool enabled, bool montage)
        {
            return enabled && !montage;
        }
    }

    /// <summary>
    /// Pure math of the "origin" root reset (SOP-10, Don 26.11.2026 20:55; NOT wired into the plugin yet, see docs/BACKLOG.md):
    /// the origin is the hips' world position captured when the scene was loaded; after a pose has settled every controller of
    /// the atom is moved by the same flat world-space delta (origin - hips), the pose's own offsets untouched, no rotation. A delta
    /// that is not a number or longer than MaxDeltaMetres is refused (the caller then snaps back to the stored origin offset and
    /// logs a warning). Another person within ClearanceMetres (flat) of the target point moves the target sideways (perpendicular
    /// to the way there) by the smallest offset that clears it. Height: the delta is flat (x, z); y keeps the pose's floor height.
    /// Plain floats, so tests run it outside VaM (companion/tests/test_version66_origin.py).
    /// </summary>
    public static class OriginReset
    {
        public const float MaxDeltaMetres = 20f;
        public const float ClearanceMetres = 0.5f;

        public enum Verdict { Ok, Tiny, Absurd }

        /// <summary>origin - current (flat). Verdict Tiny = within tolerance (nothing to do, delta 0), Absurd = NaN / infinite or
        /// longer than MaxDeltaMetres (delta 0: do not propagate it).</summary>
        public static Verdict Delta(float ox, float oz, float cx, float cz, float tolerance, out float dx, out float dz)
        {
            dx = 0f; dz = 0f;
            float rx = ox - cx, rz = oz - cz;
            if (float.IsNaN(rx) || float.IsNaN(rz) || float.IsInfinity(rx) || float.IsInfinity(rz)) return Verdict.Absurd;
            float flat = (float)Math.Sqrt(rx * rx + rz * rz);
            if (flat > MaxDeltaMetres) return Verdict.Absurd;
            if (flat <= Math.Max(0f, tolerance)) return Verdict.Tiny;
            dx = rx; dz = rz;
            return Verdict.Ok;
        }

        /// <summary>True when a controller position is a finite number within maxMetres of the reference (NaN / far away = false).</summary>
        public static bool Sane(float x, float y, float z, float refX, float refY, float refZ, float maxMetres)
        {
            if (float.IsNaN(x) || float.IsNaN(y) || float.IsNaN(z) || float.IsInfinity(x) || float.IsInfinity(y) || float.IsInfinity(z)) return false;
            float ax = x - refX, ay = y - refY, az = z - refZ;
            return Math.Sqrt(ax * ax + ay * ay + az * az) <= maxMetres;
        }

        /// <summary>
        /// The target point (tx, tz), reached from (fromX, fromZ), moved sideways (perpendicular to from -> target) by the smallest
        /// offset that puts it at least `clear` away (flat) from every other point (others = x, z pairs). Returns true when it moved.
        /// A few passes, so two neighbours are both cleared; if no clean spot is found after the passes the last candidate is returned.
        /// </summary>
        public static bool Sideways(float fromX, float fromZ, ref float tx, ref float tz, float[] others, float clear)
        {
            if (others == null || others.Length < 2) return false;
            float px = -(tz - fromZ), pz = tx - fromX;               // perpendicular to the way there
            float len = (float)Math.Sqrt(px * px + pz * pz);
            if (len < 1e-4f) { px = 1f; pz = 0f; } else { px /= len; pz /= len; }
            // Every neighbour blocks an open interval of offsets s along the perpendicular (where the point is nearer than `clear`);
            // the smallest |s| outside all intervals is one of their ends, so it clears all neighbours at once (no ping-pong).
            int n = others.Length / 2;
            float[] lo = new float[n], hi = new float[n];
            bool blocked0 = false;
            for (int i = 0; i < n; i++)
            {
                float wx = tx - others[2 * i], wz = tz - others[2 * i + 1];
                float wp = wx * px + wz * pz;
                float disc = wp * wp - (wx * wx + wz * wz) + clear * clear;   // line of offsets vs the circle of this neighbour
                if (disc <= 0f) { lo[i] = hi[i] = 0f; continue; }
                float r = (float)Math.Sqrt(disc);
                lo[i] = -wp - r; hi[i] = -wp + r;
                if (lo[i] < 0f && 0f < hi[i]) blocked0 = true;
            }
            if (!blocked0) return false;
            float best = 0f; bool found = false;
            for (int i = 0; i < n; i++)
            {
                for (int e = 0; e < 2; e++)
                {
                    float cand = e == 0 ? lo[i] : hi[i];
                    if (lo[i] == hi[i]) continue;
                    bool free = true;
                    for (int j = 0; j < n && free; j++) if (lo[j] != hi[j] && lo[j] + 1e-4f < cand && cand < hi[j] - 1e-4f) free = false;
                    if (free && (!found || Math.Abs(cand) < Math.Abs(best))) { best = cand; found = true; }
                }
            }
            if (!found) return false;
            tx += best * px; tz += best * pz;
            return true;
        }

        /// <summary>The line of the Info log per reset: pose, delta, final distance of the hips to the origin, collision shift.</summary>
        public static string LogLine(string pose, float dx, float dz, float finalHipDistance, bool collisionShift)
        {
            return "Origin reset after " + pose + ": delta " + dx.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture)
                + " / " + dz.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture) + " m (x / z), hips "
                + finalHipDistance.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture)
                + " m from the origin, collision shift " + (collisionShift ? "yes" : "no");
        }
    }
}
