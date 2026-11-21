# Release notes of version 41 (21.11.2026)

This text is the GitHub release v41.

**AIBody v41**: two downloads, `d0n.AIBody.41.var` (the plugin and the AI-Buddy scene) and `AIBody Companion Setup.exe` (the background app that does the voice and the AI).

**1. Install the package:** put `d0n.AIBody.41.var` in `<VaM main folder>/AddonPackages/` and delete the old `d0n.AIBody.*.var` files.

**2. Install AIBody Companion:** double-click `AIBody Companion Setup.exe` (for your Windows user, no admin). If Windows SmartScreen says "Windows protected your PC": **More info** > **Run anyway**. Choose the optional desktop shortcut and **Start with Windows**, then on the page **Your VaM folder** check the folder the setup found for you, or click **Browse** and choose the folder with `VaM.exe`. AIBody Companion uses that folder from then on; run the setup again to change it.

**3. Use it:** start **AIBody Companion** from the Start menu, then start VaM as usual. It listens only on 127.0.0.1, connects out only to xAI and contains no key; enter your key in the plugin (tab Voice, **XAI API Token**).

**Scene:** **Open Scene / Load Scene** > package `d0n.AIBody.41` > folder `AIBody` > **AI-Buddy**. AIBody now sits on the male `BryanGosling` (with the green background on); the female `Person` has no plugin.

**Fixed**
- **Speech audio never played.** The plugin started the sound before Unity had loaded its audio data, so nothing was heard ("did not start playing within 15 s"). It now waits until the sound is loaded and plays it the way known working VaM plugins do. With tab Config > **Verbose log** on, VaM's log shows every step as `AIBody: [audio]` lines; please send them if you still hear nothing (test step T55).
- **Pose command did nothing.** Choosing an entry in **Pose command** only selected it and there was no button to apply it. New button **Apply pose command**; results and errors appear in the left field and in VaM's log. **Add Pose** without typed text now uses the pose name and selects the new entry.
- The AI sometimes spoke its own expression command ("tool call ...") aloud; that text is now carried out, never spoken.
- Setup messages ("running in the background", "already running") are now message boxes that wait for **OK**.

- **Your VaM folder** in the setup: found automatically, only a folder with `VaM.exe` is accepted; the app's own folder picker is only the fallback. Silent setup: `/VAMDIR="D:\VaM"`.
- **Reset to Default** in tab Config > Reset, with **Confirm Reset to Default** / **Cancel**: all AIBody settings of the scene back to their defaults, including the character wizard, which asks its question again. Your XAI API Token, the key file paths, pose commands and personas are kept.
- AI-Buddy: AIBody moved from the female to the male character.
- **Voice** lists all 28 built-in xAI voices; with your key, AIBody Companion fetches xAI's current list and the menu shows it.
- **Persona** lists every persona in the personas folder (also loose `<name>.json` files); the starters Anna and Marc are added next to your own. Only these two starters exist, so with no own persona you see three entries: (none), Anna, Marc.
- Tab AI Character: the label above the breath morph field is just **Breath morph**.

Test steps: `docs/TEST_PROTOCOL.md` T52 to T58.
