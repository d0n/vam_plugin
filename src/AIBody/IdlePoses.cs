// Idle poses (version 35, Don 20.11.2026; version 51, Don 22.11.2026 20:38-20:57): when the character has nothing to do
// for a while (no speech, nobody talking, no pose command), it changes on its own to a RANDOM pose of ALL poses it has,
// so it never freezes. The idle head motion and the breathing (IdleController, BreathingController) keep running on top.
//
// Rules:
//   - version 54 (Don 23:31): the pool is the gestures.json poses and the pose files in Custom/Atom/Person/Pose/AIBody
//     plus the poses linked by pose commands and the Idle default pose; version 66: the menu "Idle pose pool" (IdlePoolMode;
//     before: the toggle "Idle poses from all pose files", off by default) "All pose files" adds every pose file of the
//     library again; a pose that fails to load is dropped for the session;
//   - up to v53 the pool: every pose of the character (gestures.json poses + the pose files the plugin lists), the poses linked by
//     pose commands (also files chosen with Add Pose) and the Idle default pose; never the same pose twice in a row when
//     the pool has more than one (version 51; up to v50 only pose-command poses were used and every second change went
//     back to the default pose, so with one usable command the character only switched between two poses);
//   - never while the AI speaks or the user talks: that resets the quiet time;
//   - a pose command of the user (spoken, typed or from the menu) is respected for CooldownSeconds first;
//   - Body control off = no idle poses (the AI / companion side may not move the body); Dollmaster active = paused;
//   - version 59: the wait between two changes is IntervalSeconds +/- Jitter (25 %) at random (one slider "Idle pose
//     interval (s)", default 165 s = the mean of the old 30 / 300 s, 30 - 18000 s); up to v58 a random wait between the
//     sliders "Idle pose min wait (s)" and "Idle pose max wait (s)" (old values migrate to their mean, MigrateInterval).
//
// Pure C# (no VaM types), so tests run it outside VaM (tests/test_idle_poses.py). It only DECIDES; Body applies the
// pose through PoseController.ApplyPose. No Dictionary.Keys/.Values enumeration, no LINQ, no indexer.
using System;
using System.Collections.Generic;

namespace AIBody
{
    public class IdlePoseScheduler
    {
        /// <summary>Version 59: one interval, each wait = interval +/- Jitter at random. Default = the mean of v51's 30 / 300 s.</summary>
        public const float DefaultIntervalSeconds = 165f;
        public const float Jitter = 0.25f;
        /// <summary>The old v51-v58 defaults (migration of saved min / max values only).</summary>
        public const float OldDefaultMinSeconds = 30f;
        public const float OldDefaultMaxSeconds = 300f;
        public const float LowestSeconds = 30f;          // version 51 (Don 20:39): 30 s to 18000 s (300 min)
        public const float HighestSeconds = 18000f;
        public const string DefaultIdlePose = "Stand Up";

        /// <summary>After a pose command of the user, idle poses wait at least this long.</summary>
        public const float CooldownSeconds = 120f;

        public bool Enabled = true;
        /// <summary>Version 59: slider "Idle pose interval (s)" (LowestSeconds - HighestSeconds).</summary>
        public float IntervalSeconds = DefaultIntervalSeconds;
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

        /// <summary>Version 59: the shortest / longest wait (interval -/+ 25 %; the interval itself is clamped to 30 - 18000 s).</summary>
        public float Lo { get { return Clamp(IntervalSeconds) * (1f - Jitter); } }
        public float Hi { get { return Clamp(IntervalSeconds) * (1f + Jitter); } }

        /// <summary>Version 59: saved v51-v58 "Idle pose min wait (s)" / "max wait (s)" values become one interval, their mean.</summary>
        public static float MigrateInterval(float minSeconds, float maxSeconds)
        {
            return Clamp((minSeconds + maxSeconds) / 2f);
        }

        public static float Clamp(float v)
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
            return Update(dt, busy, bodyControl, vocabulary, poseNames, poseNames);
        }

        /// <summary>Version 54: poolNames = the poses idle may pick on their own (gestures.json poses and the AIBody pose folder,
        /// or every pose file with the pool "All pose files"); allNames = every pose (to resolve the linked poses).</summary>
        public string Update(float dt, bool busy, bool bodyControl, PoseVocabulary vocabulary, List<string> poolNames, List<string> allNames)
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
            return PickNow(vocabulary, poolNames, allNames);
        }

        /// <summary>Version 57 (Don 15:57): a random pose of the pool right now, without any wait (also used right after a
        /// pose failed and was excluded: the next one comes at once). null = the pool is empty.</summary>
        public string PickNow(PoseVocabulary vocabulary, List<string> poolNames, List<string> allNames)
        {
            List<string> pool = Pool(vocabulary, poolNames, allNames);
            PoolSize = pool.Count;
            List<string> candidates = WithoutLast(pool);
            if (candidates.Count == 0)
            {
                _shownSeconds = -1;
                Status = ExcludedCount > 0
                    ? "no idle pose left (every pose of the pool failed and was left out for this session)"
                    : "no idle pose available (this character has no pose; Reload poses)";
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
            return Pool(vocabulary, poseNames, poseNames);
        }

        /// <summary>Version 54 (Don 23:31): the pool is poolNames (gestures.json poses + the AIBody pose folder, or every pose
        /// file with the pool "All pose files") plus the poses linked by pose commands and the Idle default pose
        /// (resolved in allNames), without the poses that failed to load (Exclude).</summary>
        public List<string> Pool(PoseVocabulary vocabulary, List<string> poolNames, List<string> allNames)
        {
            List<string> result = new List<string>();
            List<string> keys = new List<string>();
            if (poolNames != null)
                for (int i = 0; i < poolNames.Count; i++) AddOnce(result, keys, poolNames[i]);
            if (vocabulary != null)
                for (int i = 0; i < vocabulary.Count; i++) AddOnce(result, keys, PoseVocabulary.Resolve(vocabulary.Get(i), allNames));
            AddOnce(result, keys, ResolveName(DefaultPose, allNames));
            return result;
        }

        private readonly List<string> _bad = new List<string>();

        /// <summary>Version 54: a pose that could not be loaded (file missing, not a .vap, ...) is never picked again this session.</summary>
        public void Exclude(string pose)
        {
            string key = PoseVocabulary.PoseKey(pose ?? "");
            if (key.Length > 0 && !_bad.Contains(key)) _bad.Add(key);
        }

        /// <summary>Poses dropped by Exclude (info field).</summary>
        public int ExcludedCount { get { return _bad.Count; } }

        private void AddOnce(List<string> result, List<string> keys, string pose)
        {
            if (string.IsNullOrEmpty(pose)) return;
            string key = PoseVocabulary.PoseKey(pose);
            if (key.Length == 0 || keys.Contains(key) || _bad.Contains(key)) return;
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

    /// <summary>
    /// Version 66 (menu "Idle pose pool", replaces the version 54 toggle "Idle poses from all pose files"): which pose files
    /// the idle poses may pick. The menu value is the label shown to the user; config.json (body.idle_pose_pool) keeps the
    /// short key. An unknown or empty value (also a saved "0") is the default. Pure C#, no VaM types (tests run it).
    /// </summary>
    public static class IdlePoolMode
    {
        public const string AibodyKey = "aibody";
        public const string AllKey = "all";
        public const string AibodyLabel = "AIBody poses only";
        public const string AllLabel = "All pose files";
        public const string DefaultLabel = AibodyLabel;
        public const string MenuName = "Idle pose pool";
        /// <summary>The storable name of the version 54-65 toggle; old scenes still restore it (Body maps true to All).</summary>
        public const string LegacyToggleName = "Idle poses from all pose files";

        public static List<string> Labels()
        {
            return new List<string> { AibodyLabel, AllLabel };
        }

        /// <summary>True when the label is the pool of every pose file.</summary>
        public static bool IsAll(string label)
        {
            return label == AllLabel;
        }

        /// <summary>A menu value as one of the two labels; anything else (unknown, empty, "0", an old key) is the default.</summary>
        public static string Normalize(string value)
        {
            if (value == AllLabel || value == AllKey) return AllLabel;
            return DefaultLabel;
        }

        /// <summary>True when the value is exactly one of the two labels (no repair needed).</summary>
        public static bool IsLabel(string value)
        {
            return value == AibodyLabel || value == AllLabel;
        }

        /// <summary>config.json value for a label: "all" or "aibody".</summary>
        public static string KeyOf(string label)
        {
            return IsAll(label) ? AllKey : AibodyKey;
        }

        /// <summary>The label for a config.json key; an unknown key is the default.</summary>
        public static string LabelOfKey(string key)
        {
            return key == AllKey ? AllLabel : DefaultLabel;
        }

        /// <summary>The label for the old config.json boolean idle_poses_all_files (true = All, false = AIBody poses only).</summary>
        public static string LabelOfLegacy(bool allFiles)
        {
            return allFiles ? AllLabel : AibodyLabel;
        }

        /// <summary>One sentence for the menu's info text: what the chosen pool includes.</summary>
        public static string Describe(string label, string ownFolder)
        {
            if (IsAll(label))
                return "<b>" + MenuName + "</b> is <b>" + AllLabel + "</b>: every pose file of your library, including other packages, "
                    + "plus the gestures.json poses, the poses of your pose commands and the Idle default pose";
            return "<b>" + MenuName + "</b> is <b>" + AibodyLabel + "</b>: the pose files in " + ownFolder
                + " plus the gestures.json poses, the poses of your pose commands and the Idle default pose (choose <b>"
                + AllLabel + "</b> to add every pose file of your library, including other packages)";
        }
    }
}
