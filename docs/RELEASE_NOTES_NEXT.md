# Release notes of version 44 (21.11.2026)

This text is the GitHub release v44.

**AIBody v44**: download `AIBody Companion Setup.exe`; it now also installs the package `d0n.AIBody.44.var` (the plugin and the AI-Buddy scene) into your VaM folder. `d0n.AIBody.44.var` is attached too, for installing it by hand.

**1. Install:** double-click `AIBody Companion Setup.exe` (for your Windows user, no admin). If Windows SmartScreen says "Windows protected your PC": **More info** > **Run anyway**. You can run it over an older version, no uninstall needed; a running AIBody Companion is closed by the setup. Keep **Remove older AIBody packages** checked, and on the page **Your VaM folder** check the folder (the one with `VaM.exe`).

**2. Use it:** start **AIBody Companion** from the Start menu, then start VaM as usual. Load **AI-Buddy** from the package `d0n.AIBody.44`, or re-add AIBody from `d0n.AIBody.44` in your own scene and save it (a saved scene keeps loading the plugin version it names).

**Changed**
- **The setup installs the package:** it copies `d0n.AIBody.44.var` to `<VaM>\AddonPackages` and removes the older `d0n.AIBody.<number>.var` there (also on a first install). Nothing else is removed; settings and logs stay. No setup before v44 copied the package; you had to copy it yourself.
- **Already installed / update:** the setup says when this version is already installed (**OK** reinstalls / repairs, **Cancel** stops) or shows "Update from AIBody <old> to <new>".
- **Setup over a running AIBody Companion works:** v41 to v43 could not close it, and the "close applications" dialog came back again and again. The setup now closes it, and AIBody Companion accepts Windows' close request (also when you sign out).
- **Setup log:** every setup run writes `%TEMP%\Setup Log <date> #<n>.txt`; send it if anything goes wrong.
- **Louder speech possible:** **Speech volume** (tab Voice) now goes up to 3. Above 1 the companion makes the voice and **Test tone via companion** louder, with a limiter against crackling, and **Play test tone** uses a louder copy. The default stays 1.

Test steps: `docs/TEST_PROTOCOL.md` T70 to T73.
