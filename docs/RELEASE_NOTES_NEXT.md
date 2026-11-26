# Release notes of version 66 (26.11.2026)

This text is the GitHub release v66.

**AIBody v66**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.66.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.66.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v65. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.66`.

**Changes**
- **Idle pose pool is a dropdown.** The checkbox *Idle poses from all pose files* is replaced by the dropdown **Idle pose pool** (tab AI Character > Idle poses) with two clear entries: **AIBody poses only** (default) uses the pose files in `Custom/Atom/Person/Pose/AIBody` plus the gestures.json poses, the poses of your pose commands and the Idle default pose; **All pose files** uses every pose file of your library, including other packages, plus those. The info text names the chosen pool and what it includes.
- **Old settings still work.** In `config.json` the new key is `body.idle_pose_pool` (`"aibody"` or `"all"`). An old `body.idle_poses_all_files` is read once: `true` becomes **All pose files**, `false` or missing becomes **AIBody poses only**; the new key wins when both exist. Scenes saved with the old checkbox still load (on = **All pose files**). An unknown value falls back to **AIBody poses only**.
- **Shorter idle pose interval.** The slider **Idle pose interval (s)** (`body.idle_pose_interval_s`) now goes down to 5 s (it was 30 s); the default stays 165 s and the maximum 18000 s. Each wait is still the interval plus or minus 25 % at random, so 5 s gives 3.75 to 6.25 s. That is longer than the time VaM needs to settle a pose, and a pose change that starts while she is still being put back keeps her original place, so idle poses do not overlap or starve; after a pose command of yours they still wait 120 s. Saved values below 5 s are raised to 5 s.

Everything else is unchanged from v65.

Test step: `docs/TEST_PROTOCOL.md` T122.
