// Idle poses (version 35, Leon 20.11.2026): when the character has nothing to do for a while (no speech, nobody
// talking, no pose command), it changes on its own now and then to one of the available poses of the pose-command
// vocabulary (e.g. "Sit Down", "Turn Around") and returns to the default idle pose in between, so it never freezes.
// The idle head motion and the breathing (IdleController, BreathingController) keep running on top of every pose.
//
// Rules:
//   - only commands of the vocabulary whose pose exists on the character (PoseVocabulary.Resolve);
//   - never while the AI speaks or the user talks: that resets the quiet time;
//   - a pose command of the user (spoken, typed or from the menu) is respected for CooldownSeconds first;
//   - Body control off = no idle poses (the AI / companion side may not move the body);
//   - the wait between two changes is random between MinSeconds and MaxSeconds.
//
// Pure C# (no VaM types), so tests run it outside VaM (tests/test_idle_poses.py). It only DECIDES; Body applies the
// pose through PoseController.ApplyPose. No Dictionary.Keys/.Values enumeration, no LINQ, no indexer.
using System;
using System.Collections.Generic;

namespace AIBody
{
    public class IdlePoseScheduler
    {
        public const float DefaultMinSeconds = 45f;
        public const float DefaultMaxSeconds = 120f;
        public const float LowestSeconds = 10f;
        public const float HighestSeconds = 1800f;
        public const string DefaultIdlePose = "Stand Up";

        /// <summary>After a pose command of the user, idle poses wait at least this long.</summary>
        public const float CooldownSeconds = 120f;

        public bool Enabled = true;
        public float MinSeconds = DefaultMinSeconds;
        public float MaxSeconds = DefaultMaxSeconds;
        /// <summary>Pose name (compared with PoseVocabulary.PoseKey) the character returns to between two idle poses.</summary>
        public string DefaultPose = DefaultIdlePose;

        private readonly Random _random;
        private float _quiet;          // seconds without speech / user activity
        private float _cooldown;       // seconds left after a user pose command
        private float _next;           // quiet seconds needed for the next change
        private bool _inIdlePose;      // the last change was a random pose (the next one goes back to the default)
        private string _lastKey = "";

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
            _inIdlePose = false;
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
            string home = ResolveName(DefaultPose, poseNames);
            if (_inIdlePose && home != null)
            {
                _inIdlePose = false;
                _lastKey = PoseVocabulary.PoseKey(home);
                _shownSeconds = -1; Status = "back to the default idle pose '" + home + "'";
                return home;
            }
            List<string> candidates = Candidates(vocabulary, poseNames, home);
            if (candidates.Count == 0)
            {
                _inIdlePose = false;
                _shownSeconds = -1; Status = "no idle pose available (no pose command with a pose of this character besides the default)";
                return null;
            }
            string pick = candidates[_random.Next(candidates.Count)];
            _inIdlePose = true;
            _lastKey = PoseVocabulary.PoseKey(pick);
            _shownSeconds = -1; Status = "idle pose '" + pick + "'";
            return pick;
        }

        /// <summary>The available poses of the vocabulary, without the default pose and the one shown last.</summary>
        public List<string> Candidates(PoseVocabulary vocabulary, List<string> poseNames, string home)
        {
            List<string> result = new List<string>();
            if (vocabulary == null || poseNames == null) return result;
            string homeKey = home != null ? PoseVocabulary.PoseKey(home) : "";
            for (int i = 0; i < vocabulary.Count; i++)
            {
                string actual = PoseVocabulary.Resolve(vocabulary.Get(i), poseNames);
                if (actual == null) continue;
                string key = PoseVocabulary.PoseKey(actual);
                if (key == homeKey || result.Contains(actual)) continue;
                result.Add(actual);
            }
            if (result.Count > 1)
            {
                for (int i = 0; i < result.Count; i++)
                {
                    if (PoseVocabulary.PoseKey(result[i]) != _lastKey) continue;
                    result.RemoveAt(i);
                    break;
                }
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
