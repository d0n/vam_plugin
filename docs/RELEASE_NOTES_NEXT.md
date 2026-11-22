# Release notes of version 52 (22.11.2026)

This text is the GitHub release v52.

**AIBody v52**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.52.var` (the plugin, the AI-Buddy scene and the Dollmaster assets, about 98 MB) into your VaM folder. `d0n.AIBody.52.var` is attached too, for installing it by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v51, no uninstall needed. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.52` (or re-add AIBody from `d0n.AIBody.52` in your own scene and save it).

**Fixed: pose commands, Apply Pose and the twitching (Leon's test)**
1. **A pose is loaded once.** AIBody set the pose file while VaM's "Load On Select" was on, so VaM loaded the pose as soon as the path was set and then a second time for the load action. Now Load On Select is off for that moment (and put back), and the pose is loaded exactly once.
2. **No more twitching: one system writes the body at a time.** The idle head and chest motion kept moving those controllers while VaM applied the pose. Now it takes its small offsets off before the load, holds still for one second and then starts again from the new pose. While **Dollmaster** is active it poses the body itself, so the pose buttons say so instead of fighting it.
3. **Body control stayed off after Dollmaster.** While Dollmaster was active, AIBody saved Body control as off in config.json and read it back later; after that, spoken pose commands went to the conversation and idle poses stopped. Now your own Body control setting is saved.
4. **Pose command menu (decision):** choosing an entry now only selects it, and **Apply Pose** applies it, as often as you press it. Before, choosing applied it, but choosing the same entry again does nothing in VaM, so it worked once and then seemed broken. **Idle default pose** works the same way: choosing only stores it (the idle poses use it), **Apply idle default pose** applies it.
5. Only pose presets (`.vap`) are listed; a `.json` file is refused with a clear message (VaM's pose presets cannot load it).
6. The info field shows the result of the last pose load ("N controllers moved"); the log warns if a pose moved nothing.

Not changed (by design): a spoken or typed pose command must be the whole sentence ("Sit down."), and a starter command needs a pose file with the same name or a link made with **Add Pose** (the info field lists unavailable commands).

Test steps: `docs/TEST_PROTOCOL.md` T87.
