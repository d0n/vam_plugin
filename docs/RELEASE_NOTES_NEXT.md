# Release notes of version 58 (24.11.2026)

This text is the GitHub release v58.

**AIBody v58**: download `AIBody Companion Setup.exe`; it installs AIBody Companion and the package `d0n.AIBody.58.var` (the plugin, the AI-Buddy scene with its thumbnail and the Dollmaster assets) into your VaM folder. `d0n.AIBody.58.var`, `AI-Buddy.json` and `AI-Buddy.jpg` are attached too, for installing by hand.

**Install:** double-click `AIBody Companion Setup.exe` (SmartScreen: **More info** > **Run anyway**); it runs over v57. Remove older `d0n.AIBody.*.var` files from AddonPackages. Start **AIBody Companion** first, then VaM, and load **AI-Buddy** from `d0n.AIBody.58`.

**New: pose commands inside a sentence**
- A pose command now also works inside a longer sentence: "please sit down now", "could you stand up?", spoken or typed, in every AI mode. Case and punctuation do not matter.
- The built-in commands also understand a few German phrases, for example "kannst du dich hinsetzen" or "setz dich" (Sit Down), "leg dich hin" (Lay Down), "steh auf" (Stand Up), "dreh dich um" (Turn Around), "leg dich auf den bauch" (Prone).
- Only whole words count ("sitting down" is not "sit down"), and a negated command does nothing: "don't sit down", "never stand up", "setz dich nicht hin".
- With two commands in one sentence the longer one wins, then the later one.
- If the sentence has more to say ("sit down and tell me about your day"), she takes the pose first and then the AI answers. A sentence that is just the command (plus words like please / now / bitte) gets no spoken answer, as before.

**New: substitute pose for built-in commands**
- A built-in command (Sit Down, Lay Down, ...) whose pose file the character does not have is no longer "unavailable": she takes another pose of the idle pool instead (random, never the current one; else the Idle default pose). The status line and the log say which pose was used. Commands you added yourself still need their pose.

**Fixed: no empty dropdowns**
- After Reset to Default (and in general) no dropdown is empty: **Pose command** shows the first command (choosing still only selects; Apply Pose applies), the gender dropdowns show **Not set**, Dollmaster's **Thrust Control** shows **None**.

Everything from v57 is included.

Test steps: `docs/TEST_PROTOCOL.md` T103 (commands inside a sentence), T104 (substitute pose), T105 (no empty dropdown after Reset to Default, all tabs including Dollmaster), T106 (Not set / None values).
