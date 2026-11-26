# Release notes of version 65 (26.11.2026)

This text is the GitHub release v65.

**AIBody v65**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.65.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.65.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v64. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.65`.

**Changes**
- **Menus with only one entry are a line, not a dropdown.** In the plugin tabs, a choice menu (Idle default pose, Expression, Pose command, and the other choosers) is shown as a short read-only line when it has fewer than two entries, and as a dropdown when it has two or more. Dynamic lists switch automatically. The saved name and value are unchanged, so older scenes and `config.json` still load.
- **A saved "0" is no longer a menu entry.** If a saved value is `"0"` or empty, the default stays (for example Idle default pose `Stand Up`, Voice `eve`, Speech-to-text `xai`). Real choices such as **Not set** (gender), **None** (Dollmaster Thrust Control) and **null** (the offline speech-to-text engine) are kept.

Everything else is unchanged from v64.

Test step: `docs/TEST_PROTOCOL.md` T121.
