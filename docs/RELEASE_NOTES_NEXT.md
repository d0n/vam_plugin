# Release notes of version 66 (26.11.2026)

This text is the GitHub release v66.

**AIBody v66**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.66.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.66.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v65. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.66`.

**Changes**
- **Idle pose pool is a dropdown.** The checkbox *Idle poses from all pose files* is replaced by the dropdown **Idle pose pool** (tab AI Character > Idle poses) with two clear entries: **AIBody poses only** (default) uses the pose files in `Custom/Atom/Person/Pose/AIBody` plus the gestures.json poses, the poses of your pose commands and the Idle default pose; **All pose files** uses every pose file of your library, including other packages, plus those. The info text names the chosen pool and what it includes.
- **Old settings still work.** In `config.json` the new key is `body.idle_pose_pool` (`"aibody"` or `"all"`). An old `body.idle_poses_all_files` is read once: `true` becomes **All pose files**, `false` or missing becomes **AIBody poses only**; the new key wins when both exist. Scenes saved with the old checkbox still load (on = **All pose files**). An unknown value falls back to **AIBody poses only**.

Everything else is unchanged from v65.

Test step: `docs/TEST_PROTOCOL.md` T122.
