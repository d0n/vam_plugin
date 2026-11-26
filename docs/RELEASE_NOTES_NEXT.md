# Release notes of version 67 (26.11.2026)

This text is the GitHub release v67.

**AIBody v67**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.67.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.67.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v66. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.67`. When VaM asks whether to allow plugins from `d0n.AIBody.67`, allow them.

**Fixed**
- **The plugin did not load (yellow in the plugin list, no menu).** VaM's log said "Plugin scripts from packages d0n.AIBody.66 were not loaded because they are in packages that have always been denied plugin loading": plugins of that package were set to *always denied* in VaM. That choice is kept by VaM per package version, so v67 is asked about again. If it happens again: VaM > Package Manager > the package > tab **User Prefs** > allow plugins. AIBody Companion now says so in its console at start when an installed AIBody package has plugins denied.

**Not in this release:** after VaM's *Reload Plugin* the **Active** toggle (tab Voice, above the XAI API Token) was reported to come back unchecked. The code reads it from `config.json` (`connection.active`) after every load; the cause is being checked and will be fixed in a later version.

Everything else is unchanged from v66.

Test step: `docs/TEST_PROTOCOL.md` T125.
