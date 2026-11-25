# Release notes of version 64 (25.11.2026)

This text is the GitHub release v64.

**AIBody v64**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.64.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.64.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v63. Remove older `d0n.AIBody.*.var` files from AddonPackages. MacGruber's **IdlePoser** is not needed. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.64`.

**Changes**
- **Idle movement removed.** v63 crashed VaM on plugin / scene load. v64 contains no IdlePoser code at all: `IdleMovement.cs` and `IdlePoserLink.cs` are deleted and not in the package, the **Idle movement** toggle and slider are gone, and the package does not depend on `MacGruber.IdlePoser.9`. An older `config.json` with `body.idle_movement`, `body.idle_movement_opt_in` or `body.idle_movement_liveliness` still loads; those keys are ignored.
- **Kept from v63:** **Center body on control point** (tab AI Character > Body position, `body.pose_root_reset`, default on): when a pose is applied the pose is kept, but her hips are put back over her control point.

Everything else is unchanged from v63.

Test steps: `docs/TEST_PROTOCOL.md` T120 (Always Allow and scene load without IdlePoser) and T119 (center body on control point).
