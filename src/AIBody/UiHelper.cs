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
        public void Popup(JSONStorableStringChooser p) { if (p != null) _popups.Add(_plugin.CreatePopup(p, _right)); }

        /// <summary>Popup with a scrolling list (long device lists), as Collider Editor uses it.</summary>
        public void ScrollablePopup(JSONStorableStringChooser p) { if (p != null) _popups.Add(_plugin.CreateScrollablePopup(p, _right)); }

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
            _toggles.Clear();
            _sliders.Clear();
            _popups.Clear();
            _buttons.Clear();
            _texts.Clear();
        }
    }
}
