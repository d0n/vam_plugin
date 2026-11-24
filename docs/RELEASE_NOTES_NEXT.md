# Release notes of version 60 (25.11.2026)

This text is the GitHub release v60.

**AIBody v60**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.60.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.60.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v59. Remove older `d0n.AIBody.*.var` files from AddonPackages. Get MacGruber's **IdlePoser** (`MacGruber.IdlePoser.9`, free on the VaM Hub; VaM's Package Manager > **Scan Hub For Missing Packages** offers it, because AIBody now lists it as a dependency). Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.60`.

**New: idle movement**
- While nobody moves or poses her, the AI character moves by herself like someone who waits: the weight goes from one leg to the other, the hips and chest turn a little, the free heel lifts, the arms stay relaxed, with pauses in between.
- It runs in MacGruber's IdlePoser (`MacGruber.IdlePoser.9`, CC BY-SA). AIBody adds one instance labelled **AIBody Idle Movement** to the AI character only, never to your own character (`Client`), and builds its states from her current standing pose, so it fits any body and any scene. IdlePoser itself is not changed or shipped; the weight-shift values follow MacGruber's IdlePoser demo scene (credited in `docs/CREDITS.md`).
- It stops at once when you take over, exactly like the idle poses: when you grab or move one of her controllers, load a pose on her from outside, or give a pose command; then it waits the idle poses' cooldown (120 s) and starts again from her new pose. It also pauses while a pose is applied, while the scene loads, with **Body control** off and while Dollmaster is active.
- Standing poses only: sitting, kneeling and lying poses get no weight shift.
- Settings (tab AI Character > *Idle movement*): **Idle movement** (on / off, default on) and **Idle movement liveliness** (0 = calm, 1 = restless, default 0.5). Both are saved with the scene, reset by **Reset to Default** and stored in `config.json` as `body.idle_movement` / `body.idle_movement_liveliness`.
- Without IdlePoser installed nothing breaks: the info field says the package is missing.

**Changed**
- While the idle movement runs, AIBody's own idle motion leaves the chest to IdlePoser; head motion, gaze and breathing keep running.

Everything from v59 is included.

Test steps: `docs/TEST_PROTOCOL.md` T111 (starts after idle, AI character only), T112 (stops when you take over, Dollmaster, pose commands), T113 (toggle, liveliness, Reset to Default).
