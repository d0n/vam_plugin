// Character configuration wizard (after version 37, Leon).
//
// Lives in the plugin UI, tab AI Character, first section "Characters". It is not part of the
// companion console setup (setup.py): that asks only the two independent first-start points
// (background color, then Scene / Plugin). Character appearance is chosen in VaM while looking
// at the figures, and the answers are saved with the scene like the other plugin settings.
//
// Gate: "Do you want to configure your characters?" Yes shows the steps; No skips them and
// does not ask again until the user presses "Configure characters".
//
// The steps only RECORD settings used as AI context (persona / prompt: the AI character's
// gender/body and the user's character gender). Changing a Person's gender or body, or opening
// VaM's Clothing tab, is not evidenced in docs/API_AUDIT.md, so this wizard does not do either.
// Clothing is a free choice: the left info field points to VaM's own Clothing tab; there is no
// clothing list and no invented clothing id. AIBody still drives only this Person (the AI
// character); the user's character is a separate atom and is not driven from here.
using System;
using System.Collections.Generic;
using SimpleJSON;

namespace AIBody
{
    public class CharacterWizard
    {
        public const string SectionHeader = "Characters";
        public const string GateQuestion = "Do you want to configure your characters?";
        public const string YesLabel = "Yes";
        public const string NoLabel = "No";
        public const string ReopenLabel = "Configure characters";
        public const string AiGenderLabel = "AI gender/body";
        public const string UserGenderLabel = "Your character gender";
        public const string ClothingHeader = "Clothing";
        public const string Female = "Female";
        public const string Male = "Male";
        public const string AskedName = "Character setup answered";
        public const string WantedName = "Character setup wanted";

        private readonly MVRScript _plugin;
        private readonly Action _onChanged;
        private JSONStorableBool _askedJson;
        private JSONStorableBool _wantedJson;
        private JSONStorableStringChooser _aiGenderJson;
        private JSONStorableStringChooser _userGenderJson;

        /// <summary>Set when Yes / No / Configure characters was pressed; the plugin rebuilds the tab next frame.</summary>
        public Action RequestRebuild;

        public CharacterWizard(MVRScript plugin, Action onChanged)
        {
            _plugin = plugin;
            _onChanged = onChanged;
        }

        public void CreateStorables()
        {
            // Version 40: the two answers rebuild the section when they change from OUTSIDE the buttons too (VaM restoring
            // the scene's saved values after Init, Reload Config JSON, the config.json seed of a new scene). Before, the
            // callbacks were empty, so a tab built before that kept showing the old step (e.g. the gate although answered).
            _askedJson = new JSONStorableBool(AskedName, false, (bool v) => RequestTabRebuild());
            _plugin.RegisterBool(_askedJson);
            _wantedJson = new JSONStorableBool(WantedName, false, (bool v) => RequestTabRebuild());
            _plugin.RegisterBool(_wantedJson);
            List<string> genders = new List<string>();
            genders.Add("");
            genders.Add(Female);
            genders.Add(Male);
            _aiGenderJson = new JSONStorableStringChooser(AiGenderLabel, genders, "", AiGenderLabel,
                (string v) => NotifyChanged());
            _plugin.RegisterStringChooser(_aiGenderJson);
            _userGenderJson = new JSONStorableStringChooser(UserGenderLabel, genders, "", UserGenderLabel,
                (string v) => NotifyChanged());
            _plugin.RegisterStringChooser(_userGenderJson);
        }

        private void NotifyChanged()
        {
            if (_onChanged != null) _onChanged();
        }

        private void RequestTabRebuild()
        {
            if (RequestRebuild != null) RequestRebuild();
        }

        /// <summary>Which part of the section is shown: 0 = gate (Yes / No), 1 = skipped (Configure characters), 2 = steps.</summary>
        public static int Stage(bool answered, bool wanted)
        {
            if (!answered) return 0;
            return wanted ? 2 : 1;
        }

        private void Rebuild()
        {
            if (RequestRebuild != null) RequestRebuild();
            NotifyChanged();
        }

        /// <summary>First section of the tab AI Character: the gate, or the skip button, or the steps.</summary>
        public void Build(UiPage page)
        {
            page.Header("<b>Characters</b>");
            int stage = Stage(_askedJson != null && _askedJson.val, _wantedJson != null && _wantedJson.val);
            if (stage == 0)
            {
                // Version 40: the question stands right above its two buttons as their label (before, it was only in the
                // long left info field, so the right column showed a bare Yes / No under "Characters").
                page.Header(GateQuestion);
                page.Button("Yes", OnYes);
                page.Button("No", OnNo);
                return;
            }
            if (stage == 1)
            {
                page.Button("Configure characters", OnReopen);
                return;
            }
            page.Popup(_aiGenderJson);
            page.Popup(_userGenderJson);
            page.Header("<b>Clothing</b>");
        }

        private void OnYes()
        {
            _askedJson.val = true;
            _wantedJson.val = true;
            Rebuild();
        }

        private void OnNo()
        {
            _askedJson.val = true;
            _wantedJson.val = false;
            Rebuild();
        }

        /// <summary>Shows the gate question again; previous gender answers are kept.</summary>
        private void OnReopen()
        {
            _askedJson.val = false;
            Rebuild();
        }

        /// <summary>Left info field: the gate question, the skip path, and what each step actually does.</summary>
        public string InfoText()
        {
            if (_askedJson == null || !_askedJson.val)
            {
                return GateQuestion + " <b>Yes</b> opens the next steps, where you record the gender and body of the AI "
                    + "character and the gender of your own character. <b>No</b> skips this setup and does not ask again "
                    + "until you press <b>Configure characters</b>. AIBody still drives only this Person; your own "
                    + "character stays a separate atom.\n";
            }
            if (!_wantedJson.val)
            {
                return "Character setup was skipped. Press <b>Configure characters</b> if you want to set it up later. "
                    + "AIBody still drives only this Person.\n";
            }
            return "<b>AI gender/body</b> records whether the AI character is Female or Male ("
                + Describe(_aiGenderJson) + ") and <b>Your character gender</b> records the same for your own character ("
                + Describe(_userGenderJson) + "). These choices are saved with the scene and given to the AI as context; "
                + "they do not change the Person's body in VaM, so switch gender or body on the Person itself if you want "
                + "a different figure. <b>Clothing</b> is a free choice with nothing predefined: use VaM's own Clothing tab "
                + "on each Person; AIBody has no clothing list and does not change what anyone wears.\n";
        }

        private static string Describe(JSONStorableStringChooser chooser)
        {
            if (chooser == null || string.IsNullOrEmpty(chooser.val)) return "not set yet";
            return "currently " + chooser.val;
        }

        public void WriteSettings(JSONClass root)
        {
            if (root == null) return;
            JSONClass characters = new JSONClass();
            characters["setup_answered"].AsBool = _askedJson != null && _askedJson.val;
            characters["setup_wanted"].AsBool = _wantedJson != null && _wantedJson.val;
            characters["ai_gender"] = GenderValue(_aiGenderJson);
            characters["user_gender"] = GenderValue(_userGenderJson);
            root["characters"] = characters;
        }

        public void ApplySettings(JSONClass root)
        {
            if (root == null) return;
            JSONClass characters = root["characters"] as JSONClass;
            if (characters == null) return;
            // Version 40 (root cause of "the wizard shows no question at all", Leon 21.11.2026): the gate answer was also
            // read from the ONE global config.json. A scene without saved AIBody values (e.g. AI-Buddy) is seeded from
            // that file, so one Yes / No in any scene marked every later scene as answered and the question never came.
            // The answer now belongs to the scene only (storables "Character setup answered" / "... wanted");
            // config.json still gets it written for the companion, but it is never read back. The genders are kept.
            ApplyRecordedGender(_aiGenderJson, Protocol.GetString(characters, "ai_gender", GenderValue(_aiGenderJson)));
            ApplyRecordedGender(_userGenderJson, Protocol.GetString(characters, "user_gender", GenderValue(_userGenderJson)));
        }

        private static string GenderValue(JSONStorableStringChooser chooser)
        {
            if (chooser == null) return "";
            string value = chooser.val ?? "";
            if (value == Female || value == Male) return value;
            return "";
        }

        private static void ApplyRecordedGender(JSONStorableStringChooser chooser, string value)
        {
            if (chooser == null) return;
            if (value != Female && value != Male) value = "";
            chooser.val = value;
        }
    }
}
