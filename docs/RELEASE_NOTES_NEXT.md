# Release notes of version 68 (26.11.2026)

This text is the GitHub release v68.

**AIBody v68**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.68.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.68.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v67. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.68`. Allow plugins from `d0n.AIBody.68` when VaM asks.

**Fixed**
- **VaM crashed right after allowing the plugin (v67).** The crash happened inside VaM's script compiler while it compiled AIBody (access violation in `mono.dll`). The one C# `enum` in the plugin (new in v66, used by the root reset) is replaced by plain constants. Every AIBody build that compiled an enum (v60, v61, v63, v67) crashed this way; the builds without one (v62, v64, v65) did not. A test now keeps enums out of the plugin.

**Not in this release:** after VaM's *Reload Plugin* the **Active** toggle (tab Voice) was reported to come back unchecked; still being checked.

Everything else is unchanged from v67 (and v66: idle pose pool dropdown, root reset to the scene-load place, idle motion and face fixes).

Test step: `docs/TEST_PROTOCOL.md` T126.
