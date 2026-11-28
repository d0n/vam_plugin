# Release notes of version 70 (28.11.2026)

This text is the GitHub release v70.

**AIBody v70**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.70.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.70.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v69. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.70`. Allow plugins from `d0n.AIBody.70` when VaM asks.

**Finding (character voice):** no voice-pipeline fix is included. The plugin playback path (`SpeechPlayer.cs`, clip load / PlayNow / lip sync) is unchanged since v59. The v65–v68 companion log (26–27.11) shows TTS files were written and sent, but VaM often did not start them (`audio_failed`: did not start playing within 3 s, both `Custom/Sounds/AIBody/...` and the `PluginData` fallback). In those sessions `ai.driver` was `grok_bot` (the companion hands the transcript to Grok Bot and does not run the local language model; TTS for a normal answer then depends on the bridge), and on 27.11 the Windows default output device changed from the Jabra headset to Realtek USB (VaM keeps the device that was active when VaM started). Those are setup / runtime conditions on the machine, not a regression in the playback code. v70 adds diagnostics so the next session can confirm this with Verbose on.

**New**
- **In-game VaM log only when Verbose is on.** With **Verbose log** off (tab Config), the plugin writes nothing to the in-game log: no Origin reset, Physics freeze, Frame stall, Mute, audio or Dollmaster lines. All of `Log.Info`, `Log.Warn`, `Log.Error` and `Log.Debug` go through one helper and are silent unless Verbose is on. Dollmaster's leftover `SuperController.Log*` / `Debug.Log` calls use the same helper. A test scans the compiled plugin for any direct log call outside that helper.
- **Verbose voice-path diagnostics.** With Verbose on, a `voice path` line in the companion turn trace names the Windows default output device, the TTS WAV (path, size, length) or, if `ai.driver` is `grok_bot`, that this app does not synthesize TTS for that turn, and the plugin's `speech_started` / `audio_failed` result. The in-game log has `[audio] ... received clip ...` (Speech volume and head-audio state) and then `playing` or the existing "did not start playing" error.

Everything else is unchanged from v69.

Test step: `docs/TEST_PROTOCOL.md` T128.
