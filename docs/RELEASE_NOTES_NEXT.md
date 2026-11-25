# Release notes of version 63 (25.11.2026)

This text is the GitHub release v63.

**AIBody v63**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.63.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.63.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v62. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.63`.

**Changes**
- **Idle movement is back as an optional toggle, off by default.** The MacGruber IdlePoser code (excluded at build time in v62) is compiled in again, but the toggle **Idle movement** (tab AI Character, `config.json` `body.idle_movement`) is off on a fresh install, after **Reset to Default**, and for an older `config.json` that still has the v60/v61 default (the value counts only together with the new key `body.idle_movement_opt_in`). While it is off nothing of IdlePoser runs: no search, no IdlePoser plugin added. The package does not depend on `MacGruber.IdlePoser.9`; to use the toggle, install MacGruber's IdlePoser from the VaM Hub yourself.
- **Root-position reset on pose load.** New toggle **Center body on control point** (tab AI Character > Body position, `body.pose_root_reset`, default on). When a pose is applied (pose commands, Apply Pose, idle poses, the AI's pose tool, and when the idle movement starts) the pose is kept as it is, but her body (the hips) is put back over her control point instead of where the pose's own offsets take it. Only the flat distance is corrected, the height stays (sitting, kneeling, lying). She no longer drifts away from her place after several poses, which caused collisions and a high GPU load. Dollmaster montages are not changed.

**Known risk:** if the Always-Allow crash of v60/v61 (access violation in VaM's `mono.dll`) comes from VaM compiling the IdlePoser code rather than running it, v63 may crash again even with Idle movement off. In that case v62 stays the build without any IdlePoser code; please report the result.

Everything else is unchanged from v62.

Test steps: `docs/TEST_PROTOCOL.md` T118 (idle movement optional, off by default) and T119 (center body on control point). Details: `docs/IDLEPOSER_BUILD_SWITCH.md`.
