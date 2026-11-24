# Release notes of version 59 (24.11.2026)

This text is the GitHub release v59.

**AIBody v59**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.59.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.59.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v58. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.59`.

**New: one idle pose interval**
- The two sliders "Idle pose min wait (s)" and "Idle pose max wait (s)" are replaced by one slider **Idle pose interval (s)** (default 165 s, range 30-18000 s). Each wait is the interval plus or minus 25 % at random.
- Saved min / max values (scenes and config.json from v51-v58) become their mean, e.g. 60 / 120 s -> 90 s.

**New: fixed English built-in pose commands**
- Sit Down, Lay Down (also "lie down"), Turn Around, Stand Up, Prone, Crawl, Get On Your Knees (also "kneel down"), Handstand, Headstand, Stand On Your Right Leg, Stand On Your Left Leg.
- They still work inside a sentence ("please stand on your left leg now"); whole words only, negated commands ("don't lie down") are ignored, the longest command wins.
- An old list is updated: the former starters Spread Your Legs, Ankle Your Knees, Ankle Your Elbows, Crawl on all fours and Bend Over are removed unless you linked them to another pose; your own commands stay.

**New: one failover for every pose command**
- If a command's pose file is missing or broken, she takes a random pose of the idle pool instead (broken files and the current pose are skipped); if none is usable, the Idle default pose. This works the same for built-in commands and your own, spoken, typed or with **Apply Pose**. No command is "unavailable" any more; the status line names the pose that was used.
- A pose file that fails to load is also left out of the idle poses for the rest of the session.

**Changed**
- The German phrases for the built-in commands (v58) are removed; pose commands are English only.

Everything from v58 is included.

Test steps: `docs/TEST_PROTOCOL.md` T107 (idle pose interval and migration), T108 (built-in commands and the two second wordings), T109 (failover for missing and broken pose files), T110 (remote control and status).
