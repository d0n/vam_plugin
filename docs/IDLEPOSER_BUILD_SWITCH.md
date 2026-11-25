# IdlePoser idle movement: removed (version 64)

## Version 64: removed

Version 63 compiled the idle movement with MacGruber's IdlePoser back in (as an optional toggle, off by default), and VaM
crashed on plugin / scene load. Version 64 removes it completely, like version 62 but without leaving the code behind:

- `src/AIBody/IdleMovement.cs` (`IdlePart`, `IdleMovementPlan`, `IdleMovementInputs`, `IdleMovementStep`,
  `IdleMovementGate`) and `src/AIBody/IdlePoserLink.cs` are deleted: not in `src/AIBody/AIBody.cslist`, not in the `.var`,
  nothing of them is compiled or type-loaded by VaM.
- `src/AIBody/Body.cs`: no **Idle movement** / **Idle movement liveliness** storables or menu section, no
  `IdleMovementDefault` / `IdleMovementOn`, no info text, no `UpdateIdleMovement` / `CreateIdleMovement` /
  `StartIdleMovement` / `StopIdleMovement`, no IdlePoser search or `CreatePlugin`, no `body.idle_movement*` save / load.
- `src/AIBody/IdleController.cs`: `ChestSuspended` removed (back to version 59).
- `config.json`: `body.idle_movement`, `body.idle_movement_opt_in` and `body.idle_movement_liveliness` are legacy keys. An older
  file that still has them loads normally; the plugin and the companion ignore them.
- `packaging/meta.json`: no `MacGruber.IdlePoser.9` dependency.

Kept from version 63: **Center body on control point** (`RootReset.cs`, `BodyMover.CenterOnControl`, `body.pose_root_reset`).
Test step T120.

## History

- Version 60: idle movement added (IdlePoser added to the AI character at runtime, `MacGruber.IdlePoser.9` dependency).
- Version 61: guard against adding IdlePoser during a scene load. VaM crashed with **Always Allow** in v60 / v61.
- Version 62 (`8426d3b`): test build, the code excluded at build time with `#if AIBODY_IDLEPOSER` and out of the `.cslist`.
- Version 63 (`a98c04f`): compiled in again as an optional toggle, off by default; crashed on load.
- Version 64: removed. To look at the code, check out `a98c04f`.
