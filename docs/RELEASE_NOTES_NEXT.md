# Release notes of version 53 (22.11.2026)

This text is the GitHub release v53.

**AIBody v53**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.53.var` (the plugin, the AI-Buddy scene and the Dollmaster assets, about 98 MB) into your VaM folder. `d0n.AIBody.53.var` is attached too, for installing it by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v52, no uninstall needed. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.53` (or re-add AIBody from `d0n.AIBody.53` in your own scene and save it).

**Fixed: expressions not working / not visible (Leon's test)**
Not the same cause as the pose problem fixed in v52, but the same pattern: two systems writing the same thing.
1. **VaM's own Auto Expressions covered AIBody's expressions.** They animate the face morphs every frame. Now they pause while an AIBody expression shows and come back as they were afterwards (Dollmaster does the same).
2. **Show expression works.** The Expression menu used to start on "neutral", an empty expression that shows nothing. Now it starts with happy, smile, sad, angry, surprised and thinking, with listening and neutral last. The button also works without opening the menu first, and the note says how many of the expression's morphs your character has (red if none was found).
3. A morph name that your character only has as a Left and a Right morph is now set on both sides.

**Buttons**
4. **Reset expression** stays. The separate **Reload expressions (expressions.json)** button is gone: **Reload Config JSON** (tab Config) now also reloads expressions.json and refreshes the Expression menu, and says so in its status line. The trigger action **Reload config files** still works.

Test steps: `docs/TEST_PROTOCOL.md` T88.
