# Release notes of version 62 (25.11.2026)

This text is the GitHub release v62.

**AIBody v62**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.62.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.62.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v61. Remove older `d0n.AIBody.*.var` files from AddonPackages. MacGruber's **IdlePoser** is not needed for this build. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.62`.

**Test build: MacGruber IdlePoser idle movement excluded at build time to isolate the Always-Allow crash; re-enable by defining AIBODY_IDLEPOSER and re-adding the two files to AIBody.cslist.**
- VaM can crash (access violation in VaM's `mono.dll`) when the plugin permission is confirmed with **Always Allow**. v62 contains no IdlePoser code at all: `IdleMovement.cs` and `IdlePoserLink.cs` are not in `AIBody.cslist` and not in the package, every idle-movement block in `Body.cs` is behind `#if AIBODY_IDLEPOSER` (a symbol that is defined nowhere), and the package no longer depends on `MacGruber.IdlePoser.9`.
- So the AI character has no **Idle movement** section and no weight shift from leg to leg in this build. Idle poses, idle head motion and breathing are unchanged.
- If the crash is gone with v62, the IdlePoser part is the cause; if it still crashes, it is not. Please report the result (test step T117).
- How to switch it back on: `docs/IDLEPOSER_BUILD_SWITCH.md`.

Everything else is unchanged from v61.

Test steps: `docs/TEST_PROTOCOL.md` T117 (Always Allow without IdlePoser).
