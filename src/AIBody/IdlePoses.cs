// Idle poses (version 35, Leon 20.11.2026; version 51, Leon 22.11.2026 20:38-20:57): when the character has nothing to do
// for a while (no speech, nobody talking, no pose command), it changes on its own to a RANDOM pose of ALL poses it has,
// so it never freezes. The idle head motion and the breathing (IdleController, BreathingController) keep running on top.
//
// Rules:
//   - the pool: every pose of the character (gestures.json poses + the pose files the plugin lists), the poses linked by
//     pose commands (also files chosen with Add Pose) and the Idle default pose; never the same pose twice in a row when
//     the pool has more than one (version 51; up to v50 only pose-command poses were used and every second change went
//     back to the default pose, so with one usable command the character only switched between two poses);
//   - never while the AI speaks or the user talks: that resets the quiet time;
//   - a pose command of the user (spoken, typed or from the menu) is respected for CooldownSeconds first;
//   - Body control off = no idle poses (the AI / companion side may not move the body); Dollmaster active = paused;
//   - the wait between two changes is random between MinSeconds and MaxSeconds (sliders "Idle pose min wait (s)" /
//     "Idle pose max wait (s)", default 30 / 300 s, 30 - 18000 s; both 300 = a fixed 5-minute switch).
//
// Pure C# (no VaM types), so tests run it outside VaM (tests/test_idle_poses.py). It only DECIDES; Body applies the
// pose through PoseController.ApplyPose. No Dictionary.Keys/.Values enumeration, no LINQ, no indexer.
using System;
using System.Collections.Generic;

namespace AIBody
{
    public class IdlePoseScheduler
    {
        public const float DefaultMinSeconds = 30f;      // version 51 (Leon 20:38): 30 s / 300 s
        public const float DefaultMaxSeconds = 300f;
        public const float LowestSeconds = 30f;          // version 51 (Leon 20:39): 30 s to 18000 s (300 min)
        public const float HighestSeconds = 18000f;
        public const string DefaultIdlePose = "Stand Up";

        /// <summary>After a pose command of the user, idle poses wait at least this long.</summary>
        public const float CooldownSeconds = 120f;

        public bool Enabled = true;
        public float MinSeconds = DefaultMinSeconds;
        public float MaxSeconds = DefaultMaxSeconds;
        /// <summary>Idle default pose (compared with PoseVocabulary.PoseKey): one of the pool (version 51: no forced return to it).</summary>
        public string DefaultPose = DefaultIdlePose;

        private readonly Random _random;
        private float _quiet;          // seconds without speech / user activity
        private float _cooldown;       // seconds left after a user pose command
        private float _next;           // quiet seconds needed for the next change
        private string _lastKey = "";  // the pose shown last (never picked twice in a row)

        /// <summary>Size of the pool at the last change or check (info field, verbose log).</summary>
        public int PoolSize;

        /// <summary>What happened last, for the info field.</summary>
        public string Status = "waiting";

        /// <summary>Version 36 (performance): false while the plugin UI is closed; the per-frame countdown text is skipped.</summary>
        public bool Describe = true;
        private int _shownSeconds = -1;

        public IdlePoseScheduler(int seed)
        {
            _random = new Random(seed);
            PlanNext();
        }

        private float Lo { get { return Clamp(Math.Min(MinSeconds, MaxSeconds)); } }
        private float Hi { get { return Clamp(Math.Max(MinSeconds, MaxSeconds)); } }

        private static float Clamp(float v)
        {
            return v < LowestSeconds ? LowestSeconds : v > HighestSeconds ? HighestSeconds : v;
        }

        private void PlanNext()
        {
            _next = Lo + (float)_random.NextDouble() * (Hi - Lo);
        }

        /// <summary>Seconds of quiet still needed before the next change (for the info field and tests).</summary>
        public float SecondsLeft { get { return Math.Max(_cooldown, _next - _quiet); } }

        /// <summary>The user gave a pose command (or applied a pose from the menu): wait CooldownSeconds first.</summary>
        public void NoteUserPose()
        {
            _cooldown = CooldownSeconds;
            _quiet = 0f;
            PlanNext();
        }

        /// <summary>Speech, listening or another activity: the quiet time starts again.</summary>
        public void NoteActivity()
        {
            _quiet = 0f;
        }

        /// <summary>
        /// One frame. busy = the AI speaks or the user talks. Returns the pose NAME (as the character has it) to apply
        /// now, or null.
        /// </summary>
        public string Update(float dt, bool busy, bool bodyControl, PoseVocabulary vocabulary, List<string> poseNames)
        {
            if (_cooldown > 0f) _cooldown = Math.Max(0f, _cooldown - dt);
            if (!Enabled) { _quiet = 0f; _shownSeconds = -1; Status = "off"; return null; }
            if (!bodyControl) { _quiet = 0f; _shownSeconds = -1; Status = "paused (Body control is off)"; return null; }
            if (busy) { _quiet = 0f; _shownSeconds = -1; Status = "paused while someone speaks"; return null; }
            if (_next < Lo || _next > Hi) PlanNext();   // the wait settings changed
            _quiet += dt;
            if (_cooldown > 0f || _quiet < _next)
            {
                int seconds = (int)Math.Round(SecondsLeft);
                if (Describe && seconds != _shownSeconds)   // a new string once per second, not every frame
                {
                    _shownSeconds = seconds;
                    Status = "next change in about " + seconds + " s of quiet";
                }
                return null;
            }
            _quiet = 0f;
            PlanNext();
            List<string> pool = Pool(vocabulary, poseNames);
            PoolSize = pool.Count;
            List<string> candidates = WithoutLast(pool);
            if (candidates.Count == 0)
            {
                _shownSeconds = -1; Status = "no idle pose available (this character has no pose; Reload poses)";
                return null;
            }
            string pick = candidates[_random.Next(candidates.Count)];
            _lastKey = PoseVocabulary.PoseKey(pick);
            _shownSeconds = -1; Status = "idle pose '" + pick + "' (random of " + pool.Count + ")";
            return pick;
        }

        /// <summary>The pose shown last (key), e.g. after a pose command; it is not picked next.</summary>
        public void NoteShown(string pose)
        {
            _lastKey = PoseVocabulary.PoseKey(pose);
        }

        /// <summary>
        /// Version 51: every pose the character has (poseNames: gestures.json poses + listed pose files), the poses of the
        /// pose commands (Resolve: also files linked with Add Pose) and the Idle default pose; each once (by PoseKey).
        /// </summary>
        public List<string> Pool(PoseVocabulary vocabulary, List<string> poseNames)
        {
            List<string> result = new List<string>();
            List<string> keys = new List<string>();
            if (poseNames != null)
                for (int i = 0; i < poseNames.Count; i++) AddOnce(result, keys, poseNames[i]);
            if (vocabulary != null)
                for (int i = 0; i < vocabulary.Count; i++) AddOnce(result, keys, PoseVocabulary.Resolve(vocabulary.Get(i), poseNames));
            AddOnce(result, keys, ResolveName(DefaultPose, poseNames));
            return result;
        }

        private static void AddOnce(List<string> result, List<string> keys, string pose)
        {
            if (string.IsNullOrEmpty(pose)) return;
            string key = PoseVocabulary.PoseKey(pose);
            if (key.Length == 0 || keys.Contains(key)) return;
            keys.Add(key);
            result.Add(pose);
        }

        /// <summary>The pool without the pose shown last (only when more than one is left).</summary>
        public List<string> WithoutLast(List<string> pool)
        {
            List<string> result = new List<string>(pool);
            if (result.Count < 2) return result;
            for (int i = 0; i < result.Count; i++)
            {
                if (PoseVocabulary.PoseKey(result[i]) != _lastKey) continue;
                result.RemoveAt(i);
                break;
            }
            return result;
        }

        /// <summary>The character's pose whose key equals the name's key, or null.</summary>
        public static string ResolveName(string name, List<string> poseNames)
        {
            if (string.IsNullOrEmpty(name) || poseNames == null) return null;
            return PoseVocabulary.Resolve(new PoseCommand(name, name), poseNames);
        }
    }
}
