# IdlePoser idle movement: build switch (version 62)

Version 62 is a test build. The idle movement with MacGruber's IdlePoser (version 60/61, `MacGruber.IdlePoser.9`) is
excluded at **build time** to find out whether it causes the VaM crash (access violation in VaM's `mono.dll`) when
VaM's plugin permission is confirmed with **Always Allow**. It is not a runtime switch: VaM never compiles or loads
any IdlePoser code from this package.

## What is excluded

- `src/AIBody/IdleMovement.cs` and `src/AIBody/IdlePoserLink.cs` stay in the repository, but
  - they are no longer listed in `src/AIBody/AIBody.cslist` (so VaM does not load them and `tools/build_var.py` does
    not put them into the `.var`), and
  - their whole content is wrapped in `#if AIBODY_IDLEPOSER ... #endif`.
- `src/AIBody/Body.cs`: every idle-movement block is wrapped in `#if AIBODY_IDLEPOSER ... #endif` (the fields, the
  storables **Idle movement** / **Idle movement liveliness**, the stop before a pose load, the creation in `Init`,
  the menu section, the info text, `config.json` `body.idle_movement` / `body.idle_movement_liveliness` save and load,
  the calls in `Update`, `UpdateIdleMovement` / `StartIdleMovement` / `StopIdleMovement` and the stop in `Restore`).
  Only the two label constants stay (plain strings).
- `packaging/meta.json`: no dependency on `MacGruber.IdlePoser.9`.
- `src/AIBody/IdleController.cs` keeps `ChestSuspended` (nothing sets it any more; always false).

`AIBODY_IDLEPOSER` is defined nowhere (VaM compiles a `.cslist` without extra symbols). The companion app still
knows the `body.idle_movement` keys; the plugin of this build simply ignores them.

## How to re-enable

1. Add the two files back to `src/AIBody/AIBody.cslist`, before `PoseController.cs`:
   ```
   IdleMovement.cs
   IdlePoserLink.cs
   ```
2. Define the symbol for VaM, which has no compiler options: put `#define AIBODY_IDLEPOSER` as the very first line
   of `Body.cs`, `IdleMovement.cs` and `IdlePoserLink.cs` (a `#define` is valid only in its own file), or remove
   the `#if AIBODY_IDLEPOSER` / `#endif` lines.
3. Add the dependency back to `packaging/meta.json`:
   `"MacGruber.IdlePoser.9": { "licenseType": "CC BY-SA", "dependencies": {} }`.
4. Run `tools/check_plugin.sh` and the tests (`companion/tests/test_v60_idle_movement.py` builds its harness with
   `AIBODY_IDLEPOSER` defined).
