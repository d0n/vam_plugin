# Release notes of version 43 (21.11.2026)

This text is the GitHub release v43.

**AIBody v43**: two downloads, `d0n.AIBody.43.var` (the plugin and the AI-Buddy scene) and `AIBody Companion Setup.exe` (the background app that does the voice and the AI).

**1. Install the package:** put `d0n.AIBody.43.var` in `<VaM main folder>/AddonPackages/` and delete the old `d0n.AIBody.*.var` files.

**2. Install AIBody Companion:** double-click `AIBody Companion Setup.exe` (for your Windows user, no admin). If Windows SmartScreen says "Windows protected your PC": **More info** > **Run anyway**. Choose the optional desktop shortcut and **Start with Windows**, then on the page **Your VaM folder** check the folder the setup found for you, or click **Browse** and choose the folder with `VaM.exe`.

**3. Use it:** start **AIBody Companion** from the Start menu, then start VaM as usual. Load **AI-Buddy** from the package `d0n.AIBody.43`, or re-add AIBody from `d0n.AIBody.43` in your own scene and save it (a saved scene keeps loading the plugin version it names).

**Changed**
- **Test tone louder:** **Play test tone** and **Test tone via companion** are about twice as loud as before (+6 dB) and still clean. Speech volume is unchanged.
- **Update notice:** at start, AIBody Companion asks GitHub once whether a newer AIBody release exists. If there is one, it offers to open the release page. Nothing is downloaded, and offline nothing happens. To switch it off, put `"update_check": false` in `%LOCALAPPDATA%\AIBody Companion\launcher.json`.
- **Uninstall:** uninstalling AIBody Companion now also deletes the AIBody packages `d0n.AIBody.<number>.var` from `<VaM>\AddonPackages`. Only those files are deleted, nothing else. Close VaM first.
- **Speech end reported correctly:** a sentence that played to its end is now reported as `completed`. v42 reported every sentence as `interrupted`. A real barge-in or **Stop speaking** still says so.

**Installer:** "the v42 installer no longer works" could not be traced to a change. The installer and its build are the same as in v41, and the automatic install, self-test and uninstall passed. If v43's installer also fails, please write down what you see (each page, any message) and send the newest `%TEMP%\Setup Log *.txt` (test step T69).

Test steps: `docs/TEST_PROTOCOL.md` T65 to T69.
