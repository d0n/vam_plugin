# Release notes of version 69 (28.11.2026)

This text is the GitHub release v69.

**AIBody v69**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.69.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.69.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v68. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.69`. Allow plugins from `d0n.AIBody.69` when VaM asks.

**New**
- **Physics freeze for large corrections.** When a pose change or the root reset moves her more than 0.3 m, her physics is frozen for the move (controllers locked, VaM's simulation paused for a few frames), then released with 0.5 s to settle before anything else moves her. A big move with physics running dragged the joints along (stretching, collisions, jumps). Small corrections work as before. The log has one line per freeze: `Physics freeze: … moved her X m …, physics frozen … s, then 0.5 s to settle`.

**Fixed**
- **Reload Plugin no longer unchecks Active.** The Active toggle (tab Voice) now always comes from `config.json` (`connection.active`), like the XAI API Token.
- **No expressions while muted.** With **Mute** on, expression commands from the companion are ignored.
- **The sideways check sees the whole person.** When another person stands at her place, the root reset now checks that person's head, hands, elbows, knees and feet too (where they are now), not only hips and chest.

**Diagnostics**
- A VaM frame that takes longer than 2 s logs a warning (`Frame stall: …`) with the last pose, whether the root reset or a freeze was running, and the last correction.

Everything else is unchanged from v68.

Test step: `docs/TEST_PROTOCOL.md` T127.
