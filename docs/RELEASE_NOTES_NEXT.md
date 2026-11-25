# Release notes of version 61 (25.11.2026)

This text is the GitHub release v61.

**AIBody v61**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.61.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.61.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v60. Remove older `d0n.AIBody.*.var` files from AddonPackages. MacGruber's **IdlePoser** (`MacGruber.IdlePoser.9`, free on the VaM Hub) is still used for the idle movement. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.61`.

**Comparison build against v60.** v60 can crash VaM while loading some scenes (access violation in VaM's `mono.dll`). v61 is meant to be loaded with the same scene to compare (test step T114).

**Fixed: IdlePoser attach during a scene load**
- v60 looked for its IdlePoser on every frame, also while VaM was still loading the scene, and could add a second IdlePoser to the AI character in the middle of the load (before the scene's own **AIBody Idle Movement** instance was restored). AIBody now waits until the scene has finished loading, plus 3 seconds, before it looks for or adds IdlePoser.
- A scene that was saved with more than one **AIBody Idle Movement** instance keeps working: the first one is used, the others are switched off and the log says so once (remove them in the Plugins tab and save the scene).
- Whether this was the cause of the crash is not proven yet: please report whether the scene loads with v61.

**New: Grok Bot bridge (optional, off by default)**
- A second way to drive the character, next to the direct method: with `config.json` `ai.driver` set to `grok_bot` (and the remote control on), the app hands what the user says and the scene events to Grok Bot through `GET /api/bridge/events` on 127.0.0.1 (token required), and Grok Bot answers with the existing remote calls (`/api/say`, `/api/expression`, `/api/gesture`, `/api/pose`, `/api/look`, `/api/stop`). Mute words and pose commands still work locally.
- The direct method is unchanged and stays the default (`ai.driver` `direct`). Without the remote control the bridge falls back to the direct method. Switching back is one key and a restart. Details: `docs/GROK_BOT_BRIDGE.md`.

**New: setup option for Grok Bot (opt-in)**
- The setup has a new task **Grok Bot (optional)**, unchecked by default. **Install Grok Bot on this computer** downloads the Grok Bot desktop app from its official release feed, installs it silently for the current user and switches AIBody to the bridge; **Grok's cloud only** installs nothing more and keeps the direct method.
- Signing in to Grok Bot and allowing local execution on this computer stay manual steps; the setup's last page names them. A failed Grok Bot step never fails the AIBody setup (log: `Saves/PluginData/AIBody/logs/grok_bot_setup.log`).

**New: expressions and gestures from the words**
- `ai.emotion.keywords`: your own words per emotion (`happy`, `sad`, `angry`, `surprised`, `thinking`), comma-separated, added to the built-in ones; a trailing `*` matches every word that starts like this.
- `ai.emotion.gestures` (off by default): a nod when an answer starts with a clear yes, a head shake on a clear no; once per answer and only when the AI chose no gesture itself.

Everything from v60 is included.

Test steps: `docs/TEST_PROTOCOL.md` T114 (scene load, comparison with v60), T115 (Grok Bot bridge), T116 (setup option, gestures and keywords).
