# Release notes of version 57 (24.11.2026)

This text is the GitHub release v57.

**AIBody v57**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.57.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.57.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v56. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.57`.

**Changed: idle poses skip a broken pose file at once**
- When an idle pose fails to load, that pose file is dropped from the idle pool immediately (on its first failure, for the rest of the session) and the next idle pose is picked and loaded right away. There is no 30 s pause any more (v56) and no wait for the next idle timer.
- The log names the dropped pose and its file: "Idle pose 'x' (file) failed and is dropped from the idle pool for this session; next pose now".
- Idle poses are never switched off for the session. If every pose of the pool fails, the log says so once ("no pose left in the idle pool") and the plugin simply waits; there is no loop and no log flood.
- The next pose still waits while someone is speaking, and does not come with Body control or Idle poses off.

Everything from v56 is included (poses keep her place, voice pose commands, Reset to Default with Dollmaster, no realtime session without VaM).

Test steps: `docs/TEST_PROTOCOL.md` T102 (a broken idle pose is dropped and the next comes at once); T97-T101 from v56 still apply.
