# Release notes of version 51 (22.11.2026)

This text is the GitHub release v51.

**AIBody v51**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.51.var` (the plugin, the AI-Buddy scene and the Dollmaster assets, about 98 MB) into your VaM folder. `d0n.AIBody.51.var` is attached too, for installing it by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v50, no uninstall needed. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.51` (or re-add AIBody from `d0n.AIBody.51` in your own scene and save it).

**Idle poses (Leon's test of v49/v50)**
1. **Random of all poses**: when nothing happens, the character now changes to a random pose of **all** its poses (your pose files in `Custom/Atom/Person/Pose` and `.../AIBody`, gestures.json poses, the poses of your pose commands and the Idle default pose), **never the same pose twice in a row** and without going back to the default pose every second time.
2. **Why it only switched between two poses**: up to v50 only poses linked by a pose command were used (the starter commands like "Lay Down" rarely match a pose file name, so often just one was usable), and every second change went back to the Idle default pose.
3. **How often it changes**: the existing sliders **Idle pose min wait (s)** and **Idle pose max wait (s)** set the random wait between two changes. Defaults **30 s** and **300 s (5 min)**, range **30 to 18000 s (300 min)**. Type an exact value into the slider's value field (or set `body.idle_pose_min_s` / `body.idle_pose_max_s` in config.json). Min is never above max. The wait counts only while idle (no speech) and pauses while Dollmaster is active.
4. The info field shows how many poses are in the pool; with Logging Verbose the log names each idle pose and the pool size.

**Fixed: empty dropdowns after Reset to Default**
After **Reset to Default** every menu gets its full list again (engines, AI mode, voice, language, persona, mic mode, VAD engine, idle default pose, pose commands, expressions, gestures). Cause: the reset set each menu back to its start value, but some lists were only filled later (by the companion app or from the character) and nothing rebuilt them after the reset, so a menu could be left with a value that was not in its list, which VaM shows as an empty dropdown.

Test steps: `docs/TEST_PROTOCOL.md` T86.
