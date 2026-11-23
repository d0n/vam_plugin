# Release notes of version 55 (23.11.2026)

This text is the GitHub release v55.

**AIBody v55**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.55.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.55.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v54. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.55`.

**New: mute the AI by voice or with a switch**
- **Mute by voice:** say **"shut up"**, **"halt's Maul"** (also "halts Maul", "halt das Maul"), **"halt die Klappe"** or **"sei still"**. She stops talking at once, everything queued is dropped, and from then on she ignores what she hears: no answer, no AI request, no pose or gesture from speech, no proactive talking.
- **Unmute by voice:** say **"sprich mit mir"**, **"speak again"** or **"go ahead talking"**. She listens and answers again (the command itself gets no answer).
- The phrases work with any character name, in any upper/lower case, with or without punctuation, and also in the middle of a longer sentence (for example when another person talks on the same headset). They are recognised by the companion app itself, before anything goes to the AI.
- **Menu switch:** tab **Config**, first control on the right: **Mute AI (stop talking and listening)**. It does the same as the voice commands and follows them: a voice mute switches it on, a voice unmute switches it off. The left info field of the tab explains it.
- It is off on every start and is not saved in the scene. **Reset to Default** switches it off.

Test steps: `docs/TEST_PROTOCOL.md` T93 (voice mute / unmute), T94 (phrases inside longer sentences), T95 (menu switch both ways), T96 (Reset to Default, restart, realtime mode).
