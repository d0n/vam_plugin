# Release notes of version 54 (22.11.2026)

This text is the GitHub release v54.

**AIBody v54**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.54.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.54.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v53. **Please remove the old `d0n.AIBody.*.var` files (47-53) from AddonPackages and clear VaM's cache** (see 2). Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.54`.

**1. Freeze Motion/Sound in the scene**
The shipped AI-Buddy scene does not store Freeze Motion/Sound (checked: its only global settings are player height, monitor camera rotation, use scene load position, global lighting and the scene triggers). Freeze Motion/Sound is a VaM setting that stays as you left it, so please switch it off in VaM's top bar once. The build now removes any freeze setting from the shipped scene and refuses to build a scene that has one.

**2. Scene thumbnail**
Every build ships `Saves/scene/AIBody/AI-Buddy.json` and `Saves/scene/AIBody/AI-Buddy.jpg` with the same fixed name in the same folder (also the attached `AI-Buddy.json` + `AI-Buddy.jpg`), and a build check refuses a package where the picture is missing, renamed, differently cased, not listed or different. The v47-v53 packages already had the picture next to the scene, so it vanished on the VaM side: several AIBody packages (or a loose copy) offer the same scene path and VaM's cached picture can belong to another copy. Remove the old AIBody packages and clear the cache, then the picture shows.

**3. Body position works and stays put**
The Body position sliders (forward / back, right / left, turn) and **Reset body position** now move the whole character as one piece. Two causes: the sliders moved every body part one after another although the parts ride on the main controller (so parts moved twice), and pose files that store the root position pulled her back to where the pose was saved on every idle pose switch and pose command. Now she is moved rigidly, and after every pose load she is put back to her place (including your Body position offset or where you dragged her); a brief flicker is possible. The pose files are not changed.

**4. Missing character and sound backlog**
- Idle poses now come only from the AIBody pose folder (`Custom/Atom/Person/Pose/AIBody`) plus the poses linked in your pose commands. New toggle **Idle poses from all pose files** (off by default) brings back all pose files. A pose file that is missing or fails is left out from now on.
- A sound that is loaded but does not play within 3 s is given up (was 15 s; the message mentions Freeze Motion/Sound). Answers waiting longer than 8 s are dropped instead of played late.
- The companion no longer queues new answers behind answers the plugin has not started; after VaM was frozen or away for 5 s or more it stops the old speech, clears the backlog and answers only the newest thing you said. Sentences said while she is still thinking are merged into one turn. The backlog is logged.
- The plugin menu text refreshes every 2 s and on tab change (less work per frame).

Test steps: `docs/TEST_PROTOCOL.md` T89 (body position), T90 (idle poses), T91 (thumbnail, Freeze), T92 (stall test).
