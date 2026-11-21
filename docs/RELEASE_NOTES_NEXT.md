# Release notes of version 42 (21.11.2026)

This text is the GitHub release v42.

**AIBody v42**: two downloads, `d0n.AIBody.42.var` (the plugin and the AI-Buddy scene) and `AIBody Companion Setup.exe` (the background app that does the voice and the AI).

**1. Install the package:** put `d0n.AIBody.42.var` in `<VaM main folder>/AddonPackages/` and delete the old `d0n.AIBody.*.var` files.

**2. Install AIBody Companion:** double-click `AIBody Companion Setup.exe` (for your Windows user, no admin). If Windows SmartScreen says "Windows protected your PC": **More info** > **Run anyway**. Choose the optional desktop shortcut and **Start with Windows**, then on the page **Your VaM folder** check the folder the setup found for you, or click **Browse** and choose the folder with `VaM.exe`.

**3. Use it:** start **AIBody Companion** from the Start menu, then start VaM as usual. It listens only on 127.0.0.1, connects out only to xAI and contains no key; enter your key in the plugin (tab Voice, **XAI API Token**).

**Scene:** **Open Scene / Load Scene** > package `d0n.AIBody.42` > folder `AIBody` > **AI-Buddy**. This is now Leon's scene with the two people `AI` and `Client`. AIBody sits on `Client` (your own figure, with the green background on) and gives the voice, poses, expressions and idle motion to `AI`. The info field says "AIBody 42 on 'Client', AI person 'AI'".

**Important: a saved scene keeps its plugin version.** A scene names the exact package of its plugin (for example `d0n.AIBody.40`), and VaM loads that one, even when a newer package is installed. In the v41 test every companion log line said `plugin=40`, so the v41 plugin and its speech audio fix never ran. Load AI-Buddy from `d0n.AIBody.42`, or in your own scene remove AIBody and add it again from `d0n.AIBody.42`, then save. AIBody Companion now warns about this in its log and the plugin's status line.

**Changed**
- **Pose command:** choosing an entry applies its pose at once. The old **Pose** dropdown, **Apply pose** and **Apply pose command** are gone.
- **Add Pose** opens VaM's file browser. Choose a pose file, type the spoken command in **New pose command** and press **Save pose command** (or **Cancel Add Pose**).
- **Delete Pose** removes the chosen command. Added and deleted commands are now saved in `config.json` right away. Before, they were lost.
- **Reset poses** (new): `AI` goes back to where the scene placed it, then `Client` half a second later, so they do not collide.
- **Voice** is a scrollable menu, so all 28 xAI voices can be reached. The list comes from xAI (`GET /v1/tts/voices`) when AIBody Companion has your key, otherwise from the 28 voices on docs.x.ai.
- **Realtime voice:** when the AI only made a gesture and said nothing, AIBody Companion now asks it once for its spoken answer.

**Speech audio:** the play sequence is the one from v41, taken from Dollmaster, MacGruber and Timeline. It is not verified yet, because it never ran in VaM (see above). Please test with the v42 scene and send the `AIBody: [audio]` lines from VaM's log (test step T63).

Test steps: `docs/TEST_PROTOCOL.md` T59 to T64.
