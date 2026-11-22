# Release notes of version 46 (22.11.2026)

This text is the GitHub release v46.

**AIBody v46**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.46.var` (the plugin and the AI-Buddy scene) into your VaM folder. `d0n.AIBody.46.var` is attached too, for installing it by hand.

**1. Install:** double-click `AIBody Companion Setup.exe` (for your Windows user, no admin). If Windows SmartScreen says "Windows protected your PC": **More info** > **Run anyway**. You can run it over an older version, no uninstall needed; a running AIBody Companion is closed by the setup. On the page **Your VaM folder** check the folder (the one with `VaM.exe`).

**2. Use it:** start **AIBody Companion** from the Start menu, then start VaM as usual. Load **AI-Buddy** from the package `d0n.AIBody.46`, or re-add AIBody from `d0n.AIBody.46` in your own scene and save it (a saved scene keeps loading the plugin version it names).

**Fixed**
- **The voice was too quiet, and much quieter a little away from the head:** the AI-Buddy scene set the character's head audio to full volume only within 4 cm, so at a normal viewing distance of 1-2 m the voice was about 30 dB quieter. A higher Speech volume could not make up for that. Now the voice is at full volume within 2 m.

**New**
- **Full volume distance (m)** (tab Voice > Voice and sound, below the volume, default 2, from 0.3 to 10): up to this distance from the head the voice is at full volume, and beyond it the voice gets quieter. Removing the plugin puts the scene's own value back.
- **Speech volume (%)**: the volume slider now shows percent, from 0 to 300, default 100 (100 = the full volume, 200 = twice, 300 = three times). Scenes saved with the old slider keep their volume (1 becomes 100 %). Above about 150 % the voice mostly gets harsher rather than louder.
- companion.log shows the speech level once per volume change: the peak before and after the gain, and how much is cut at full scale.

Test steps: `docs/TEST_PROTOCOL.md` T75.
