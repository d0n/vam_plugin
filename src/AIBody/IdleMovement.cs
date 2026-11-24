// Idle movement (version 60, Don, call 24.11.2026): while nobody moves or poses the AI character she moves by herself
// like someone who stands and waits - the weight goes from one leg to the other, the hips and the chest turn a little,
// the free foot rests on its toes, the arms hang where they are. The animation runs in MacGruber's IdlePoser
// (VaM Hub package MacGruber.IdlePoser.9, CC BY-SA; see docs/CREDITS.md), only on the AI character.
//
// This file is pure C# (no VaM or Unity types) so tests run it outside VaM (companion/tests/test_v60_idle_movement.py):
//   - IdleMovementPlan builds the IdlePoser state set ("idlepose" JSON, the format IdlePoser itself saves with a scene,
//     read in MacGruber_IdlePoserCore.cs LoadPose) from the character's CURRENT pose, so it fits every body size and
//     every standing pose. The offsets of the states are those of MacGruber's demo scene (IdlePoserDemo_Studio01, the
//     "Body" instance: State#Left / State#Right / Inter#Mid), scaled by one liveliness value;
//   - IdleMovementGate decides every frame whether IdlePoser may run. It stops for exactly the reasons the idle poses
//     stop (Idle movement off, Body control off, Dollmaster active, the cooldown after a pose command) plus: a pose is
//     being applied (PoseGuard), the scene is loading, she is grabbed or posed from outside, she is not standing.
//     Grabbing / posing from outside also starts the idle-pose cooldown (Body), so both wait the same way.
// No Dictionary.Keys/.Values enumeration, no LINQ, no indexer.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace AIBody
{
    /// <summary>One controller of the AI character, relative to its anchor (position in m, rotation as Unity euler degrees,
    /// the same numbers IdlePoser stores as PX/PY/PZ and RX/RY/RZ).</summary>
    public class IdlePart
    {
        public string Control;
        public string Anchor;
        public float PX, PY, PZ, RX, RY, RZ;

        public IdlePart(string control, string anchor, float px, float py, float pz, float rx, float ry, float rz)
        {
            Control = control; Anchor = anchor; PX = px; PY = py; PZ = pz; RX = rx; RY = ry; RZ = rz;
        }
    }

    public static class IdleMovementPlan
    {
        /// <summary>The IdlePoser instance AIBody owns carries this plugin label (other IdlePoser instances are left alone).</summary>
        public const string PoserLabel = "AIBody Idle Movement";
        public const string PoserPackage = "MacGruber.IdlePoser.9";
        public const string PoserCslist = "MacGruber.IdlePoser.9:/Custom/Scripts/MacGruber/IdlePoser/MacGruber_IdlePoser.cslist";
        /// <summary>A plugin's storable id is plugin#N_Namespace.Class (E8); IdlePoser is class MacGruber.IdlePoser.</summary>
        public const string PoserStorableSuffix = "_MacGruber.IdlePoser";
        /// <summary>Anchor of the body controls: the Person's root controller (IdlePoser's default anchor).</summary>
        public const string RootControl = "control";
        /// <summary>The hands follow the chest (the arms hang from the shoulders).</summary>
        public const string HandAnchor = "chestControl";

        public const float DefaultLiveliness = 0.5f;

        /// <summary>Order matters: IdlePoser updates its captures in this order, so the chest moves before the hands that
        /// are anchored to it. No head: the head belongs to AIBody's idle head motion and gaze.</summary>
        public static readonly string[] Controls = { "hipControl", "chestControl", "lFootControl", "rFootControl",
            "lToeControl", "rToeControl", "lHandControl", "rHandControl" };

        public static string AnchorOf(string control)
        {
            return control == "lHandControl" || control == "rHandControl" ? HandAnchor : RootControl;
        }

        // Offsets of MacGruber's demo set (IdlePoserDemo_Studio01, IdlePoser "Body", State#Right minus Inter#Mid):
        // hip and chest turn about the vertical axis, the free foot lifts its heel and comes a bit forward.
        public const float HipYaw = 20f;
        public const float ChestYaw = 10f;
        public const float FootLift = 0.053f, FootForward = 0.037f, FootSide = 0.003f;
        public const float FootPitch = 31.4f, FootYaw = 2.0f, FootRoll = 1.2f;
        /// <summary>Not in the demo (its hip stays centred): the hips move a little over the standing leg.</summary>
        public const float HipShift = 0.015f;

        /// <summary>Amplitude factor: 0.6 (calm) .. 1.4 (lively); 1.0 at the default = the demo's values.</summary>
        public static float Amplitude(float liveliness) { return 0.6f + 0.8f * Clamp01(liveliness); }
        /// <summary>Seconds a weight shift is held: 9-20 s (calm) .. 3-8 s (lively); 6-14 s at the default.</summary>
        public static float WaitMin(float liveliness) { return 9f - 6f * Clamp01(liveliness); }
        public static float WaitMax(float liveliness) { return 20f - 12f * Clamp01(liveliness); }
        /// <summary>Time factor of the transitions: 1.4 (slow) .. 0.6 (quick); one shift = about 1.1 s at the default.</summary>
        public static float Slowness(float liveliness) { return 1.4f - 0.8f * Clamp01(liveliness); }

        public static float Clamp01(float v) { return v < 0f ? 0f : v > 1f ? 1f : v; }

        /// <summary>
        /// True when the pose is a standing pose (root-anchored parts): the hips are high above the feet, the feet are at
        /// about the same height and the chest is above the hips. Sitting, kneeling and lying poses get no weight shift.
        /// Missing parts = false.
        /// </summary>
        public static bool IsStanding(List<IdlePart> parts)
        {
            IdlePart hip = Find(parts, "hipControl"), chest = Find(parts, "chestControl");
            IdlePart lf = Find(parts, "lFootControl"), rf = Find(parts, "rFootControl");
            if (hip == null || chest == null || lf == null || rf == null) return false;
            if (hip.Anchor != RootControl || chest.Anchor != RootControl || lf.Anchor != RootControl || rf.Anchor != RootControl) return false;
            float lowFoot = Math.Min(lf.PY, rf.PY);
            return hip.PY - lowFoot >= 0.55f && Math.Abs(lf.PY - rf.PY) <= 0.12f && chest.PY - hip.PY >= 0.1f;
        }

        public static IdlePart Find(List<IdlePart> parts, string control)
        {
            if (parts == null) return null;
            for (int i = 0; i < parts.Count; i++) if (parts[i] != null && parts[i].Control == control) return parts[i];
            return null;
        }

        /// <summary>
        /// The IdlePoser state set for this base pose (the "idlepose" object of IdlePoser's scene JSON, version 9):
        /// Neutral (intermediate state = the base pose, the start) between WeightLeft, WeightRight and Rest (regular states).
        /// IdlePoser picks the next regular state at random and never the same one twice in a row. Returns null when the
        /// pose has no hips (nothing to animate).
        /// </summary>
        public static string BuildJson(string atomUid, List<IdlePart> basePose, float liveliness)
        {
            if (Find(basePose, "hipControl") == null) return null;
            float a = Amplitude(liveliness), s = Slowness(liveliness);
            string wMin = Num(WaitMin(liveliness)), wMax = Num(WaitMax(liveliness));
            StringBuilder b = new StringBuilder();
            b.Append("{\"Info\":{\"Format\":\"MacGruber.IdlePoser\",\"Version\":\"9\",\"Author\":\"AIBody\"},");
            b.Append("\"InitialState\":\"Neutral\",\"Paused\":\"false\",\"StateMask\":\"0\",\"DefaultToWorldAnchor\":\"false\",");
            b.Append("\"ControlCaptures\":[");
            for (int i = 0; i < basePose.Count; i++)
            {
                if (i > 0) b.Append(',');
                b.Append("{\"Name\":").Append(Str(basePose[i].Control)).Append(",\"ApplyPos\":\"true\",\"ApplyRot\":\"true\"}");
            }
            b.Append("],\"States\":[");
            State(b, "Neutral", 2, "0", "0", 0.6f * s, 0.5f, new[] { "WeightLeft", "WeightRight", "Rest" }, atomUid, basePose, 0, a, s);
            b.Append(',');
            State(b, "WeightLeft", 0, wMin, wMax, 0.5f * s, 0.5f, new[] { "Neutral" }, atomUid, basePose, -1, a, s);
            b.Append(',');
            State(b, "WeightRight", 0, wMin, wMax, 0.5f * s, 0.5f, new[] { "Neutral" }, atomUid, basePose, 1, a, s);
            b.Append(',');
            State(b, "Rest", 0, wMin, wMax, 0.5f * s, 0.3f, new[] { "Neutral" }, atomUid, basePose, 0, a, s);
            b.Append("]}");
            return b.ToString();
        }

        /// <summary>side: -1 = the weight on the LEFT leg (the right foot rests), +1 = on the right leg, 0 = the base pose.
        /// The character's right is +x in root space (the demo's rFootControl has PX +0.12).</summary>
        private static void State(StringBuilder b, string name, int type, string waitMin, string waitMax, float transition,
            float probability, string[] transitions, string atomUid, List<IdlePart> basePose, int side, float a, float s)
        {
            b.Append("{\"Name\":").Append(Str(name));
            b.Append(",\"WaitInfiniteDuration\":\"false\",\"WaitForSync\":\"false\",\"AllowInGroupT\":\"false\"");
            b.Append(",\"WaitDurationMin\":\"").Append(waitMin).Append("\",\"WaitDurationMax\":\"").Append(waitMax).Append('"');
            b.Append(",\"TransitionDuration\":\"").Append(Num(transition)).Append('"');
            b.Append(",\"EaseInDuration\":\"").Append(Num(1f * s)).Append("\",\"EaseOutDuration\":\"").Append(Num(1f * s)).Append('"');
            b.Append(",\"Probability\":\"").Append(Num(probability)).Append('"');
            b.Append(",\"StateType\":\"").Append(type).Append("\",\"StateGroup\":\"0\"");
            b.Append(",\"Transitions\":[");
            for (int i = 0; i < transitions.Length; i++) { if (i > 0) b.Append(','); b.Append(Str(transitions[i])); }
            b.Append("],\"ControlEntries\":{");
            for (int i = 0; i < basePose.Count; i++)
            {
                IdlePart p = Shifted(basePose[i], side, a);
                if (i > 0) b.Append(',');
                b.Append(Str(p.Control)).Append(":{");
                b.Append("\"PX\":\"").Append(Num(p.PX)).Append("\",\"PY\":\"").Append(Num(p.PY)).Append("\",\"PZ\":\"").Append(Num(p.PZ)).Append('"');
                b.Append(",\"RX\":\"").Append(Num(p.RX)).Append("\",\"RY\":\"").Append(Num(p.RY)).Append("\",\"RZ\":\"").Append(Num(p.RZ)).Append('"');
                b.Append(",\"AnchorMode\":\"1\",\"DampingTime\":\"0.2\",\"AnchorAAtom\":").Append(Str(atomUid));
                b.Append(",\"AnchorAControl\":").Append(Str(p.Anchor)).Append('}');
            }
            b.Append("}}");
        }

        /// <summary>The part in a weight-shift state. The hands (anchored to the chest) and the standing foot keep their offsets.</summary>
        public static IdlePart Shifted(IdlePart p, int side, float a)
        {
            IdlePart r = new IdlePart(p.Control, p.Anchor, p.PX, p.PY, p.PZ, p.RX, p.RY, p.RZ);
            if (side == 0) return r;
            float sd = side;   // -1: weight left, right foot free; +1: weight right, left foot free
            switch (p.Control)
            {
                case "hipControl":
                    r.RY += -sd * HipYaw * a;     // demo: right foot free -> hip +20 degrees
                    r.PX += sd * HipShift * a;    // over the standing leg
                    break;
                case "chestControl":
                    r.RY += -sd * ChestYaw * a;
                    r.PX += sd * HipShift * 0.5f * a;
                    break;
                case "rFootControl":
                    if (side < 0) Lift(r, 1f, a);
                    break;
                case "lFootControl":
                    if (side > 0) Lift(r, -1f, a);
                    break;
            }
            return r;
        }

        /// <summary>The free foot: heel up, a little forward (mirror = -1 for the left foot).</summary>
        private static void Lift(IdlePart r, float mirror, float a)
        {
            r.PX += mirror * FootSide * a;
            r.PY += FootLift * a;
            r.PZ += FootForward * a;
            r.RX += FootPitch * a;
            r.RY += mirror * FootYaw * a;
            r.RZ += mirror * FootRoll * a;
        }

        /// <summary>A jump of a controller (root space) in one frame that IdlePoser's own smooth motion never makes: a pose
        /// loaded from outside (VaM's Pose tab, a preset, another plugin). 5 cm plus 0.6 m/s.</summary>
        public static bool IsJump(float meters, float dt)
        {
            return meters > 0.05f + 0.6f * Math.Max(0f, Math.Min(dt, 0.5f));
        }

        public static string Num(float v)
        {
            if (float.IsNaN(v) || float.IsInfinity(v)) v = 0f;
            return Math.Round(v, 5).ToString("0.#####", CultureInfo.InvariantCulture);
        }

        public static string Str(string s)
        {
            StringBuilder b = new StringBuilder("\"");
            string v = s ?? "";
            for (int i = 0; i < v.Length; i++)
            {
                char c = v[i];
                if (c == '"' || c == '\\') b.Append('\\').Append(c);
                else if (c < ' ') b.Append(' ');
                else b.Append(c);
            }
            return b.Append('"').ToString();
        }
    }

    public enum IdleMovementStep { Keep, Stop, Start, Rebuild }

    /// <summary>What Body knows this frame (all false/true defaults = may run).</summary>
    public struct IdleMovementInputs
    {
        public bool Available;     // AIBody's IdlePoser instance exists on the AI character
        public bool BodyControl;   // Body control on and Dollmaster not active (Body.BodyControl)
        public bool Cooldown;      // the idle poses' cooldown after a pose command / posing from outside runs
        public bool Settling;      // a pose is being applied (PoseGuard active)
        public bool Loading;       // VaM loads a scene
        public bool Outside;       // grabbed, or a controller jumped (pose from outside) this frame
        public bool Standing;      // the current pose is a standing pose (only checked before a start)
    }

    public class IdleMovementGate
    {
        public bool Enabled = true;
        private float _liveliness = IdleMovementPlan.DefaultLiveliness;
        private bool _livelinessChanged;
        public bool Running { get; private set; }
        public string Status = "waiting";

        public float Liveliness
        {
            get { return _liveliness; }
            set
            {
                float v = IdleMovementPlan.Clamp01(value);
                if (Math.Abs(v - _liveliness) < 0.0001f) return;
                _liveliness = v;
                _livelinessChanged = true;
            }
        }

        /// <summary>One frame. Start = build the states from the CURRENT pose and switch IdlePoser on; Rebuild = the same states
        /// from the base pose of the last start with the new liveliness; Stop = switch IdlePoser off now (she stays as she is).</summary>
        public IdleMovementStep Update(IdleMovementInputs i)
        {
            string blocked = null;
            if (!i.Available) blocked = "not available (MacGruber.IdlePoser.9 not found on the AI character; see the log)";
            else if (!Enabled) blocked = "off";
            else if (!i.BodyControl) blocked = "paused (Body control is off or Dollmaster is active)";
            else if (i.Loading) blocked = "paused while the scene loads";
            else if (i.Outside) blocked = "stopped: she is moved or posed from outside (waits like the idle poses)";
            else if (i.Settling) blocked = "paused while a pose is applied";
            else if (i.Cooldown) blocked = "waits after a pose command or after you posed her (the idle poses' cooldown)";
            else if (!Running && !i.Standing) blocked = "paused: she is not standing (only standing poses shift their weight)";
            if (blocked != null)
            {
                Status = blocked;
                if (!Running) return IdleMovementStep.Keep;
                Running = false;
                return IdleMovementStep.Stop;
            }
            Status = "running (weight shift from leg to leg)";
            if (!Running)
            {
                Running = true;
                _livelinessChanged = false;
                return IdleMovementStep.Start;
            }
            if (_livelinessChanged)
            {
                _livelinessChanged = false;
                return IdleMovementStep.Rebuild;
            }
            return IdleMovementStep.Keep;
        }

        /// <summary>A pose is about to be applied by AIBody: IdlePoser is switched off by the caller right now.</summary>
        public void StopNow(string why)
        {
            Running = false;
            Status = why ?? "paused";
        }
    }
}
