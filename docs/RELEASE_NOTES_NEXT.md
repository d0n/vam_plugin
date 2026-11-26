# Release notes of version 67 (26.11.2026)

This text is the GitHub release v67.

**AIBody v67**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.67.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.67.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v66. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.67`. When VaM asks whether to allow plugins from `d0n.AIBody.67`, allow them.

**Fixed**
- **The plugin did not load (yellow in the plugin list, no menu).** VaM's log said "Plugin scripts from packages d0n.AIBody.66 were not loaded because they are in packages that have always been denied plugin loading": plugins of that package were set to *always denied* in VaM. That choice is kept by VaM per package version, so v67 is asked about again. If it happens again: VaM > Package Manager > the package > tab **User Prefs** > allow plugins. AIBody Companion now says so in its console at start when an installed AIBody package has plugins denied.
- **Reload Plugin keeps the Activate toggle.** VaM's *Reload Plugin* used to set scene-only values (the Dollmaster **Activate** toggle and Dollmaster's settings) back to their defaults. The plugin now keeps them across a reload (saved when it is unloaded, read back once within 30 s on the same character). Loading a scene or a new scene is not affected: the scene's own values win.

Everything else is unchanged from v66.

Test step: `docs/TEST_PROTOCOL.md` T125.
