# Release notes of version 49 (22.11.2026)

This text is the GitHub release v49.

**AIBody v49**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.49.var` (the plugin, the AI-Buddy scene and the Dollmaster assets) into your VaM folder. `d0n.AIBody.49.var` is attached too, for installing it by hand. The package is now about **98 MB** (it carries the Dollmaster personas, sounds, expressions and VAMasutra poses).

**1. Install:** double-click `AIBody Companion Setup.exe` (for your Windows user, no admin). If Windows SmartScreen says "Windows protected your PC": **More info** > **Run anyway**. You can run it over an older version, no uninstall needed; a running AIBody Companion is closed by the setup. On the page **Your VaM folder** check the folder (the one with `VaM.exe`).

**2. Use it:** start **AIBody Companion** from the Start menu first, then start VaM as usual. Load **AI-Buddy** from the package `d0n.AIBody.49`, or re-add AIBody from `d0n.AIBody.49` in your own scene and save it (a saved scene keeps loading the plugin version it names).

**New**
1. **Voice barge-in is on by default** (tab Client Character, **Voice barge-in (headphones)**), in chain and realtime mode. Echo protection is always on: while the AI speaks the mic stays closed for the AI; talking clearly louder than her echo stops her, cancels the running answer (realtime too) and your words are answered.
2. **Language** chooser (tab Voice, AI section, under Persona): Auto or one of the 20 xAI voice languages, default **German (de)**. It sets the language for speech to text, the answers and the voice.
3. **Setup notice:** the "already installed / update" box of the setup no longer names the buttons in English (Windows labels them in its own language); it just says what OK and Cancel do. Buttons and behaviour unchanged.
4. **Apply Pose** button (tab AI Character > Poses, under Pose command): applies the chosen pose command now, also the same one again.
5. **Apply idle default pose** button (tab AI Character > Idle poses): applies the idle default pose now and restarts the idle wait.
6. **Body position** (tab AI Character, section *Body position*): **Move forward / back**, **Move right / left** (along the way she faces), **Turn**, and **Reset body position**. VaM saves the moved body with the scene.
7. **Tab Dollmaster:** the old Dollmaster plugin (VAMDeluxe, 2019) ported in full into AIBody: the whole old Dollmaster menu, with an **Activate** checkbox at the top (off by default, saved with the scene; off = Dollmaster does nothing). Its assets ship inside the package.

**Dollmaster notes**
- While **Activate** is on, Dollmaster takes over the body: expressions, breathing, idle motion and idle poses come from Dollmaster, and AIBody's own ones pause. **AIBody keeps speech**: Dollmaster's voice lines are skipped while the AI speaks or has speech queued. Turning Activate off gives the body back to AIBody.
- Credit: Dollmaster code by VAMDeluxe, MIT license (`third_party/dollmaster/LICENSE`, see `docs/CREDITS.md`).
- The package is about 98 MB because of the Dollmaster assets.

Test steps: `docs/TEST_PROTOCOL.md` T78-T84.
