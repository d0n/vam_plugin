# Release notes of version 56 (24.11.2026)

This text is the GitHub release v56.

**AIBody v56**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.56.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.56.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v55. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.56`.

**Fixed: a pose change no longer moves her away**
- Many pose files also store where the character stood when they were saved, so loading one used to put her back at that spot. Now every pose change keeps her where she is, position AND facing direction: Apply Pose and the pose dropdown, Apply idle default pose, idle poses, pose commands (voice, typed, realtime) and Dollmaster montages (the partner moves with her, so the two keep their arrangement).
- How: her place is taken right before the pose loads and she is put back right after it, and again on every frame while VaM settles the pose (at least 1.5 s, until she is still for 0.5 s, at most 5 s). The pose files are never changed. Moving her yourself (dragging, Body position, Reset body position) is respected.

**Pose commands by voice use the same path as Apply Pose**
- A pose command recognised by the companion (spoken, typed or from realtime) now goes through the same pose loading as Apply Pose, keeps her place, is refused while Dollmaster poses her, and shows "Pose command (voice) applied" in the status line. Only a pose that was really applied restarts the idle pose timer. Say the command exactly as it is written in tab Commands.

**Fixed: idle poses stopping**
- One error while switching idle poses stopped them for the rest of the session without a message. Now they pause 30 s, write a warning to the log and go on; a broken pose file is left out.

**Reset to Default and Dollmaster**
- Reset to Default also resets Dollmaster's settings (no dropdown is left empty) and switches Dollmaster Activate off.
- Switching Dollmaster off restores VaM's Auto Expressions as it was before.

**No realtime credits without VaM**
- The companion closes the xAI realtime session about 10 s after VaM disconnects, and does not open it when VaM has not connected within a minute of the start. It opens again when VaM is back.

Test steps: `docs/TEST_PROTOCOL.md` T97 (poses keep her place), T98 (pose commands by voice), T99 (idle poses keep running), T100 (Reset to Default with Dollmaster, Auto Expressions, montage), T101 (realtime without VaM).
