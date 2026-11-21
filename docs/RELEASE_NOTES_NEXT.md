# Release notes of version 45 (21.11.2026)

This text is the GitHub release v45.

**AIBody v45**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.45.var` (the plugin and the AI-Buddy scene) into your VaM folder. `d0n.AIBody.45.var` is attached too, for installing it by hand.

**1. Install:** double-click `AIBody Companion Setup.exe` (for your Windows user, no admin). If Windows SmartScreen says "Windows protected your PC": **More info** > **Run anyway**. You can run it over an older version, no uninstall needed; a running AIBody Companion is closed by the setup. On the page **Your VaM folder** check the folder (the one with `VaM.exe`).

**2. Use it:** start **AIBody Companion** from the Start menu, then start VaM as usual. Load **AI-Buddy** from the package `d0n.AIBody.45`, or re-add AIBody from `d0n.AIBody.45` in your own scene and save it (a saved scene keeps loading the plugin version it names).

**Fixed**
- **The package is no longer lost:** with v44, when the setup failed or was cancelled after it had started copying (for example because a companion file was still in use), the old `d0n.AIBody.<number>.var` was already deleted and the new one was taken back, so no AIBody package was left in AddonPackages. Now the older packages are removed only after the install succeeded and `d0n.AIBody.45.var` is in place (checked against the bundled file). If it is not, the older ones stay and the setup says so.
- **Older packages are always removed:** the option "Remove older AIBody packages" is gone; every install leaves exactly `d0n.AIBody.45.var` (other packages are not touched).
- **AIBody Companion that cannot be closed:** if the setup cannot end it (for example when it was started as administrator), the setup now says so on **Preparing to Install** and stops before changing anything. Quit it from the tray icon and run the setup again.

Test steps: `docs/TEST_PROTOCOL.md` T74.
