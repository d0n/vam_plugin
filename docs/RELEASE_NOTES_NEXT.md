# Release notes draft for the next version (not released yet)

On main after v40 (21.11.2026). No version number, tag or release until Leon announces it; then the number below becomes the next one and this text goes into the GitHub release.

**AIBody v<next>**: two downloads, `d0n.AIBody.<next>.var` (the plugin and the AI-Buddy scene) and `AIBody Companion Setup.exe` (the background app that does the voice and the AI).

**1. Install the package:** put `d0n.AIBody.<next>.var` in `<VaM main folder>/AddonPackages/` and delete the old `d0n.AIBody.*.var` files.

**2. Install AIBody Companion:** double-click `AIBody Companion Setup.exe` (for your Windows user, no admin). If Windows SmartScreen says "Windows protected your PC": **More info** > **Run anyway**. Choose the optional desktop shortcut and **Start with Windows**, then on the page **Your VaM folder** check the folder the setup found for you, or click **Browse** and choose the folder with `VaM.exe`. AIBody Companion uses that folder from then on; run the setup again to change it.

**3. Use it:** start **AIBody Companion** from the Start menu, then start VaM as usual. It listens only on 127.0.0.1, connects out only to xAI and contains no key; enter your key in the plugin (tab Voice, **XAI API Token**).

**Scene:** **Open Scene / Load Scene** > package `d0n.AIBody.<next>` > folder `AIBody` > **AI-Buddy**. AIBody now sits on the male `BryanGosling` (with the green background on); the female `Person` has no plugin.

**New**
- **Your VaM folder** in the setup: found automatically, only a folder with `VaM.exe` is accepted; the app's own folder picker is only the fallback. Silent setup: `/VAMDIR="D:\VaM"`.
- **Reset to Default** in tab Config > Reset, with **Confirm Reset to Default** / **Cancel**: all AIBody settings of the scene back to their defaults, including the character wizard, which asks its question again. Your XAI API Token, the key file paths, pose commands and personas are kept.
- AI-Buddy: AIBody moved from the female to the male character.

Test steps: `docs/TEST_PROTOCOL.md` T52 to T54.
