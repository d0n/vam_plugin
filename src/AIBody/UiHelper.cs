// Small UI helpers shared by the plugin's components, and UiPage: the controls of one settings
// tab. Switching tabs removes the controls of the old tab with the standard MVRScript
// Remove* methods and creates the new ones, the pattern of vam-embody's CollapsibleSection and
// VamHeightPlugin (docs/API_AUDIT.md, E17/E18).
using System;
using System.Collections.Generic;
using UnityEngine.UI;

namespace AIBody
{
    public static class UiHelper
    {
        public static UIDynamicTextField Header(MVRScript plugin, string text, bool rightSide)
        {
            UIDynamicTextField field = plugin.CreateTextField(new JSONStorableString("header " + text, text), rightSide);
            field.height = 40f;
            return field;
        }

        /// <summary>
        /// Makes a text field editable. The InputField bound via storable.inputField (the
        /// ToySerialController pattern) is guarded: if it fails, the field stays visible but
        /// read-only and the reason goes to the log. Returns the InputField, or null then.
        /// TODO(verify): editable text field pattern on CreateTextField in VaM 1.22.
        /// </summary>
        public static InputField MakeEditable(UIDynamicTextField field, JSONStorableString storable)
        {
            try
            {
                InputField input = field.gameObject.AddComponent<InputField>();
                input.textComponent = field.UItext;
                input.lineType = InputField.LineType.SingleLine;
                storable.inputField = input;
                return input;
            }
            catch (Exception e)
            {
                Log.Error("Text field '" + storable.name + "' is read-only (InputField failed): " + Diag.Describe(e));
                return null;
            }
        }
    }

    /// <summary>The controls of one tab; Clear() removes all of them again.</summary>
    public class UiPage
    {
        private readonly MVRScript _plugin;
        private readonly bool _right;
        private readonly List<UIDynamicToggle> _toggles = new List<UIDynamicToggle>();
        private readonly List<UIDynamicSlider> _sliders = new List<UIDynamicSlider>();
        private readonly List<UIDynamicPopup> _popups = new List<UIDynamicPopup>();
        private readonly List<UIDynamicButton> _buttons = new List<UIDynamicButton>();
        private readonly List<UIDynamicTextField> _texts = new List<UIDynamicTextField>();
        private readonly List<JSONStorableString> _inputs = new List<JSONStorableString>();
        private readonly List<UIDynamicColorPicker> _colors = new List<UIDynamicColorPicker>();

        public UiPage(MVRScript plugin, bool rightSide)
        {
            _plugin = plugin;
            _right = rightSide;
        }

        public void Header(string text)
        {
            _texts.Add(UiHelper.Header(_plugin, text, _right));
        }

        public void Toggle(JSONStorableBool p) { if (p != null) _toggles.Add(_plugin.CreateToggle(p, _right)); }
        public void Slider(JSONStorableFloat p) { if (p != null) _sliders.Add(_plugin.CreateSlider(p, _right)); }

        /// <summary>
        /// Slider with a shown label that differs from the storable name (the stored name stays, so
        /// saved scenes keep working). Setting UIDynamicSlider.label after CreateSlider: E26.
        /// </summary>
        public void Slider(JSONStorableFloat p, string label)
        {
            if (p == null) return;
            UIDynamicSlider slider = _plugin.CreateSlider(p, _right);
            if (slider != null && !string.IsNullOrEmpty(label)) slider.label = label;
            _sliders.Add(slider);
        }
        /// <summary>VaM's colour picker (H / S / V sliders and a colour swatch): E32, E18.</summary>
        public void ColorPicker(JSONStorableColor p) { if (p != null) _colors.Add(_plugin.CreateColorPicker(p, _right)); }

        /// <summary>One short line of help directly below a control (a small text field, like Header).</summary>
        public void Note(string text)
        {
            UIDynamicTextField f = UiHelper.Header(_plugin, text, _right);
            _texts.Add(f);
        }

        public void Popup(JSONStorableStringChooser p) { Chooser(p, false); }

        /// <summary>Popup with a scrolling list (long device lists), as Collider Editor uses it.</summary>
        public void ScrollablePopup(JSONStorableStringChooser p) { Chooser(p, true); }

        /// <summary>Version 65: a chooser with fewer than two entries is a short read-only line (the label and the value),
        /// not a dropdown; with two or more it is a popup (or a scrolling popup). The JSONStorableStringChooser itself is
        /// unchanged (name, value, choices), so saved scenes and config.json still load.</summary>
        private void Chooser(JSONStorableStringChooser p, bool scrollable)
        {
            if (p == null) return;
            if (UiChooser.ShowsDropdown(p))
            {
                if (scrollable) _popups.Add(_plugin.CreateScrollablePopup(p, _right));
                else _popups.Add(_plugin.CreatePopup(p, _right));
                return;
            }
            _texts.Add(UiHelper.Header(_plugin, UiChooser.Line(p), _right));
        }

        /// <summary>Like Button, but returns the control (its label can change later: buttonText.text).</summary>
        public UIDynamicButton ButtonRef(string label, UnityEngine.Events.UnityAction onClick)
        {
            UIDynamicButton b = _plugin.CreateButton(label, _right);
            _buttons.Add(b);
            b.button.onClick.AddListener(onClick);
            return b;
        }

        public void Button(string label, UnityEngine.Events.UnityAction onClick)
        {
            UIDynamicButton b = _plugin.CreateButton(label, _right);
            _buttons.Add(b);
            b.button.onClick.AddListener(onClick);
        }

        /// <summary>
        /// Button with a multi-line label ("\n"), text centered, taller than the standard button.
        /// UIDynamicButton.buttonText.alignment: E27; UIDynamic.height (as on spacers): E12.
        /// </summary>
        public void Button(string label, float height, UnityEngine.Events.UnityAction onClick)
        {
            UIDynamicButton b = _plugin.CreateButton(label, _right);
            _buttons.Add(b);
            b.button.onClick.AddListener(onClick);
            try
            {
                b.buttonText.alignment = UnityEngine.TextAnchor.MiddleCenter;
                b.height = height;
            }
            catch (Exception e)
            {
                Log.Error("Button '" + label + "': centering / height failed: " + Diag.Describe(e));
            }
        }

        public UIDynamicTextField Text(JSONStorableString p, float height)
        {
            UIDynamicTextField f = _plugin.CreateTextField(p, _right);
            f.height = height;
            _texts.Add(f);
            return f;
        }

        /// <summary>Editable one-line text field; false if it could only be shown read-only.</summary>
        public bool TextInput(JSONStorableString p)
        {
            return TextInputField(p) != null;
        }

        /// <summary>Like TextInput, but returns the field's InputField (null if it could only be shown read-only).</summary>
        public InputField TextInputField(JSONStorableString p)
        {
            UIDynamicTextField f = Text(p, 40f);
            InputField input = UiHelper.MakeEditable(f, p);
            if (input == null) return null;
            _inputs.Add(p);
            return input;
        }

        public void Clear()
        {
            // Unbind the InputFields first, so no storable keeps a reference to a removed control.
            foreach (JSONStorableString s in _inputs) s.inputField = null;
            _inputs.Clear();
            foreach (UIDynamicToggle c in _toggles) _plugin.RemoveToggle(c);
            foreach (UIDynamicSlider c in _sliders) _plugin.RemoveSlider(c);
            foreach (UIDynamicPopup c in _popups) _plugin.RemovePopup(c);
            foreach (UIDynamicButton c in _buttons) _plugin.RemoveButton(c);
            foreach (UIDynamicTextField c in _texts) _plugin.RemoveTextField(c);
            foreach (UIDynamicColorPicker c in _colors) _plugin.RemoveColorPicker(c);
            _toggles.Clear();
            _sliders.Clear();
            _popups.Clear();
            _buttons.Clear();
            _texts.Clear();
            _colors.Clear();
        }
    }

    /// <summary>
    /// Version 65: helpers for JSONStorableStringChooser menus. A list with fewer than two entries is shown as a
    /// read-only line, not as a dropdown (UiPage.Popup / ScrollablePopup). A saved value of "0" or empty is a
    /// placeholder, not a real choice: it is not added to the list and the default stays. "None", "Not set", "null"
    /// and "Off" are real choices in some menus and are left alone.
    /// </summary>
    public static class UiChooser
    {
        public const int DropdownMin = 2;
        /// <summary>A saved value that is not a real choice: empty, or "0" (often written for an unset number).</summary>
        public static bool IsPlaceholder(string value)
        {
            return string.IsNullOrEmpty(value) || value == "0";
        }

        public static int Count(JSONStorableStringChooser p)
        {
            return p != null && p.choices != null ? p.choices.Count : 0;
        }

        public static bool ShowsDropdown(JSONStorableStringChooser p)
        {
            return Count(p) >= DropdownMin;
        }

        /// <summary>The read-only line when the menu has fewer than two entries (Header text, includes the control name).</summary>
        public static string Line(JSONStorableStringChooser p)
        {
            string name = p != null && !string.IsNullOrEmpty(p.name) ? p.name : "Choice";
            string value = p != null ? p.val : null;
            if (IsPlaceholder(value) && Count(p) == 1) value = p.choices[0];
            if (IsPlaceholder(value)) return "<b>" + name + "</b>: (none)";
            return "<b>" + name + "</b>: " + value;
        }

        /// <summary>Drops placeholder entries from a choice list (in place).</summary>
        public static void DropPlaceholders(List<string> names)
        {
            if (names == null) return;
            for (int i = names.Count - 1; i >= 0; i--)
                if (IsPlaceholder(names[i])) names.RemoveAt(i);
        }

        /// <summary>Apply a saved or reported choice. A placeholder is ignored (the current / default value stays).
        /// A real unknown value is added to the list (a custom voice, persona or language).</summary>
        public static void ApplyValue(JSONStorableStringChooser chooser, string value)
        {
            if (chooser == null || IsPlaceholder(value)) return;
            List<string> choices = chooser.choices != null ? new List<string>(chooser.choices) : new List<string>();
            DropPlaceholders(choices);
            if (!choices.Contains(value)) choices.Add(value);
            chooser.choices = choices;   // E9, E24, E25
            chooser.val = value;
        }

        /// <summary>Remove placeholder entries from the menu; if the current value is a placeholder, use fallback (or
        /// the first remaining entry). A real custom value that is not in the list yet is kept and added.</summary>
        public static void Sanitize(JSONStorableStringChooser chooser, string fallback)
        {
            if (chooser == null) return;
            List<string> choices = chooser.choices != null ? new List<string>(chooser.choices) : new List<string>();
            DropPlaceholders(choices);
            string value = chooser.val;
            if (IsPlaceholder(value))
            {
                value = !IsPlaceholder(fallback) ? fallback : (choices.Count > 0 ? choices[0] : "");
                if (!IsPlaceholder(value) && !choices.Contains(value)) choices.Add(value);
                if (!IsPlaceholder(value)) chooser.val = value;
            }
            else if (!choices.Contains(value)) choices.Add(value);
            chooser.choices = choices;
        }
    }

    /// <summary>
    /// 'Reset to Default' (Config > Reset, Don 21.11.2026 17:01): every saved plugin setting is registered through these
    /// helpers, which remember the value the storable was created with (its default) before VaM restores the scene's saved
    /// values. ResetAll sets each one back with .val (as everywhere in the plugin), so its own callback runs (restart of the
    /// link, config.json write-back, the wizard's tab rebuild). Not registered here on purpose, so never reset:
    /// "Settings initialized", the xAI / ElevenLabs key file paths and the scene hooks (AI speaking, ...), which are not saved.
    /// Plain lists and for loops only (sandbox rules: no dictionaries iterated, no reflection).
    /// </summary>
    public class SettingsDefaults
    {
        private readonly List<JSONStorableBool> _bools = new List<JSONStorableBool>();
        private readonly List<bool> _boolDefaults = new List<bool>();
        private readonly List<JSONStorableFloat> _floats = new List<JSONStorableFloat>();
        private readonly List<float> _floatDefaults = new List<float>();
        private readonly List<JSONStorableString> _strings = new List<JSONStorableString>();
        private readonly List<string> _stringDefaults = new List<string>();
        private readonly List<JSONStorableStringChooser> _choosers = new List<JSONStorableStringChooser>();
        private readonly List<string> _chooserDefaults = new List<string>();
        private readonly List<string> _colorNames = new List<string>();
        private readonly List<HSVColor> _colorDefaults = new List<HSVColor>();

        public int Count
        {
            get { return _bools.Count + _floats.Count + _strings.Count + _choosers.Count + _colorNames.Count; }
        }

        private static SettingsDefaults Of(MVRScript plugin)
        {
            AIBodyPlugin owner = plugin as AIBodyPlugin;
            return owner != null ? owner.Defaults : null;
        }

        public static JSONStorableBool Bool(MVRScript plugin, JSONStorableBool p)
        {
            plugin.RegisterBool(p);
            SettingsDefaults d = Of(plugin);
            if (d != null) { d._bools.Add(p); d._boolDefaults.Add(p.val); }
            return p;
        }

        public static JSONStorableFloat Float(MVRScript plugin, JSONStorableFloat p)
        {
            plugin.RegisterFloat(p);
            SettingsDefaults d = Of(plugin);
            if (d != null) { d._floats.Add(p); d._floatDefaults.Add(p.val); }
            return p;
        }

        public static JSONStorableString Text(MVRScript plugin, JSONStorableString p)
        {
            plugin.RegisterString(p);
            SettingsDefaults d = Of(plugin);
            if (d != null) { d._strings.Add(p); d._stringDefaults.Add(p.val); }
            return p;
        }

        public static JSONStorableStringChooser Chooser(MVRScript plugin, JSONStorableStringChooser p)
        {
            plugin.RegisterStringChooser(p);
            SettingsDefaults d = Of(plugin);
            if (d != null) { d._choosers.Add(p); d._chooserDefaults.Add(p.val); }
            return p;
        }

        /// <summary>A colour is reset with SetColorParamValue (E32), by its storable name.</summary>
        public void TrackColor(string name, HSVColor value)
        {
            _colorNames.Add(name);
            _colorDefaults.Add(value);
        }

        /// <summary>Sets every tracked setting back to its default; returns how many settings were changed.</summary>
        public int ResetAll(MVRScript plugin)
        {
            int changed = 0;
            for (int i = 0; i < _bools.Count; i++)
            {
                if (_bools[i].val == _boolDefaults[i]) continue;
                _bools[i].val = _boolDefaults[i];
                changed++;
            }
            for (int i = 0; i < _floats.Count; i++)
            {
                if (_floats[i].val == _floatDefaults[i]) continue;
                _floats[i].val = _floatDefaults[i];
                changed++;
            }
            for (int i = 0; i < _strings.Count; i++)
            {
                if (_strings[i].val == _stringDefaults[i]) continue;
                _strings[i].val = _stringDefaults[i];
                changed++;
            }
            for (int i = 0; i < _choosers.Count; i++)
            {
                // Version 51: the default is always one of the menu's entries (a menu is never left without its value).
                List<string> choices = _choosers[i].choices;
                if (!string.IsNullOrEmpty(_chooserDefaults[i]) && (choices == null || !choices.Contains(_chooserDefaults[i])))
                {
                    List<string> withDefault = choices != null ? new List<string>(choices) : new List<string>();
                    withDefault.Insert(0, _chooserDefaults[i]);
                    _choosers[i].choices = withDefault;   // E9, E24, E25
                }
                if (_choosers[i].val == _chooserDefaults[i]) continue;
                _choosers[i].val = _chooserDefaults[i];
                changed++;
            }
            for (int i = 0; i < _colorNames.Count; i++)
            {
                plugin.SetColorParamValue(_colorNames[i], _colorDefaults[i]);
                changed++;
            }
            return changed;
        }
    }
}
