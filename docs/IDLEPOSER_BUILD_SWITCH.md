# IdlePoser idle movement: optional toggle (version 63; build switch in version 62)

## Version 63: compiled in, runtime toggle, off by default

The idle movement with MacGruber's IdlePoser (version 60/61, `MacGruber.IdlePoser.9`) is compiled in again, as in v61:
`src/AIBody/IdleMovement.cs` and `src/AIBody/IdlePoserLink.cs` are listed in `src/AIBody/AIBody.cslist` (and packaged),
and there are no `#if AIBODY_IDLEPOSER` wrappers any more. It is an **optional runtime toggle that is off by default**:

- Toggle **Idle movement** (tab AI Character > *Idle movement*, storable "Idle movement", `config.json`
  `body.idle_movement`), default **off** (`Body.IdleMovementDefault`; companion `settings_file.DEFAULTS`;
  `examples/config.json`). **Reset to Default** switches it off.
- While it is off, nothing of IdlePoser runs: `Body.Update` calls `UpdateIdleMovement` only when the toggle is on
  (`IdleMovementOn`); the gate (`IdleMovementGate`) and the VaM link (`IdlePoserLink`) are created only the first time it
  is switched on (`CreateIdleMovement`). So no search for IdlePoser, no `CreatePlugin`, no IdlePoser instance added.
  `StopIdleMovement` (before a pose load, when the plugin stops, when the toggle goes off) runs only if it was ever on.
- An older `config.json` does not switch it on: v60/v61 wrote `"idle_movement": true` as their default. The plugin uses
  `body.idle_movement` only together with `body.idle_movement_opt_in` (`true`, written by v63 and later,
  `Body.IdleMovementFromConfig`). A scene saved with v60/v61 did not store the old default, so it loads with the new
  default (off).
- `packaging/meta.json` has **no** dependency on `MacGruber.IdlePoser.9`. To use the toggle, install MacGruber's IdlePoser
  yourself (VaM Hub, free, CC BY-SA). Without it, switching the toggle on only shows "MacGruber.IdlePoser.9 is not
  installed" in the info field and the log (`IdlePoserLink.Find` checks the package with `FileManagerSecure.FileExists`).

Risk: if the Always-Allow crash (access violation in VaM's `mono.dll`, v60/v61) comes from VaM compiling or loading
the IdlePoser code itself, rather than from running it, v63 can crash again even with the toggle off. Version 62 (no
IdlePoser code at all) is the build to compare with (test step T117; v63: T118).

## Version 62: build switch (history)

Version 62 was a test build: `IdleMovement.cs` / `IdlePoserLink.cs` were out of `AIBody.cslist`, their content and every
idle-movement block in `Body.cs` were wrapped in `#if AIBODY_IDLEPOSER ... #endif` (a symbol defined nowhere, VaM
compiles a `.cslist` without extra symbols), and `packaging/meta.json` had no `MacGruber.IdlePoser.9` dependency. To build
such a package again: remove the two files from `AIBody.cslist` and do not call into them from `Body.cs`
(see the v62 commit `8426d3b`).
