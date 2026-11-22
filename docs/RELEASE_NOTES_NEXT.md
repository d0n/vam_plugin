# Release notes of version 48 (22.11.2026)

This text is the GitHub release v48.

**AIBody v48**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.48.var` (the plugin and the AI-Buddy scene) into your VaM folder. `d0n.AIBody.48.var` is attached too, for installing it by hand.

**1. Install:** double-click `AIBody Companion Setup.exe` (for your Windows user, no admin). If Windows SmartScreen says "Windows protected your PC": **More info** > **Run anyway**. You can run it over an older version, no uninstall needed; a running AIBody Companion is closed by the setup. On the page **Your VaM folder** check the folder (the one with `VaM.exe`).

**2. Use it:** start **AIBody Companion** from the Start menu first, then start VaM as usual. Load **AI-Buddy** from the package `d0n.AIBody.48`, or re-add AIBody from `d0n.AIBody.48` in your own scene and save it (a saved scene keeps loading the plugin version it names).

**New**
- **Full volume distance (m)** is back (tab Voice > *Voice and sound*): up to this distance from the character's head the voice is at full volume, farther away it gets quieter. Default **3 m**, range 0.3 to 10 m. At 1 to 2 m the AI is clearly louder than in v47.
- This time it works like EasyMoan: the plugin sets only the head audio's "minDistance" (and "maxDistance" 500 if it is smaller), never its volume, and only when the value changed and the AI is not speaking. If you move the slider while the AI speaks, the new value is applied after the sentence. Never when a sentence starts: that is what broke speech in v46. Saved in config.json as `body.full_volume_distance`. The scene itself keeps its value (0.04 m); when AIBody is removed, the head gets that value back.
- **Speech volume (%)** stays as in v47: 0 to 1000, default 100 (= v45).

**Sound output device:** VaM always plays on the Windows default output device that was active when VaM started; neither the plugin nor the companion can choose another one. With SteamVR / Oculus start the headset app first (or set the Windows sound output to the headset), then start VaM. The companion writes `Windows default output device: ...` to companion.log once at start.

Test steps: `docs/TEST_PROTOCOL.md` T77.
