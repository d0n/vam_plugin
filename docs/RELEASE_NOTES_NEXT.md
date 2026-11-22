# Release notes of version 50 (22.11.2026)

This text is the GitHub release v50.

**AIBody v50**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.50.var` (the plugin, the AI-Buddy scene and the Dollmaster assets, about 98 MB) into your VaM folder. `d0n.AIBody.50.var` is attached too, for installing it by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v49, no uninstall needed. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.50` (or re-add AIBody from `d0n.AIBody.50` in your own scene and save it).

**Fixed (Leon's test of v49 after a full config reset)**
1. **Reset to Default now clears the XAI API Token** (field, config.json and the companion's copy). Paste your key again afterwards. The token is never written to a log.
2. **Language model** menu: shows all engines again (xai, ollama, echo) instead of only "echo".
3. **Persona** menu: no more "(none)"; it offers the female persona **Anna** (default) and the male persona **Marc** (plus persona folders of your own).
4. **Memory** is on by default.
5. **Speech-to-text** menu: shows its engines (xai, null) and is never empty.
6. **Text-to-speech** menu: shows xai, elevenlabs and tone instead of only "tone"; and **spoken input works after a reset**: all three menus now default to **xai** (before: the offline test engines, and the test speech recognition understands nothing). Without an xAI key the companion still falls back to the test engines and the info field says why.
7. **Mic enabled** and **Push-to-talk interrupts speech** are on by default (also after a reset and in a new config.json).

Why the menus were short: they were filled only by the companion app's status messages and started with just the test engine; now the full lists are built into the plugin.

Test steps: `docs/TEST_PROTOCOL.md` T85.
