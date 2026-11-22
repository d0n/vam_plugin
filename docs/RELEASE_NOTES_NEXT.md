# Release notes of version 47 (22.11.2026)

This text is the GitHub release v47.

**AIBody v47**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.47.var` (the plugin and the AI-Buddy scene) into your VaM folder. `d0n.AIBody.47.var` is attached too, for installing it by hand.

**1. Install:** double-click `AIBody Companion Setup.exe` (for your Windows user, no admin). If Windows SmartScreen says "Windows protected your PC": **More info** > **Run anyway**. You can run it over an older version, no uninstall needed; a running AIBody Companion is closed by the setup. On the page **Your VaM folder** check the folder (the one with `VaM.exe`).

**2. Use it:** start **AIBody Companion** from the Start menu, then start VaM as usual. Load **AI-Buddy** from the package `d0n.AIBody.47`, or re-add AIBody from `d0n.AIBody.47` in your own scene and save it (a saved scene keeps loading the plugin version it names). A scene you saved with v46 keeps v46's head audio distance; load the package scene again.

**Fixed**
- **The AI speaks again:** in v46 the AI's answers did not start playing (only the test tone was heard), and the sound was worse than in v45. v46 changed the character's head audio distance settings before every sentence; v47 goes back to exactly what v45 did (only the volume), and the AI-Buddy scene has its v45 head audio again. The "Full volume distance (m)" slider of v46 is gone.
- **Speech volume (%)** stays: 0 to 1000, default 100, and 100 % is the same as Speech volume 1 in v45 (200 % = 2, 300 % = 3). **Play test tone** uses its 2x copy from 150 % and its 3x copy from 250 %.

**Changed**
- Tab AI Character > *Idle motion and breathing*: the "Breath morph" and "Breath1" boxes are gone. Breathing still uses the morph Breath1 (another one: `body.breath_morph` in config.json).
- The AI-Buddy scene thumbnail is always in the package next to the scene, so VaM's scene browser shows it.

Test steps: `docs/TEST_PROTOCOL.md` T76.
