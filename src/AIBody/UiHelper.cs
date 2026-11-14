// Small UI helpers shared by the plugin's components.
using UnityEngine.UI;

namespace AIBody
{
    public static class UiHelper
    {
        public static void Header(MVRScript plugin, string text, bool rightSide)
        {
            UIDynamicTextField field = plugin.CreateTextField(new JSONStorableString("header " + text, text), rightSide);
            field.height = 40f;
        }

        // TODO(verify): editable text field pattern (InputField bound via storable.inputField).
        public static void TextInput(MVRScript plugin, JSONStorableString storable, bool rightSide)
        {
            UIDynamicTextField field = plugin.CreateTextField(storable, rightSide);
            field.height = 40f;
            InputField input = field.gameObject.AddComponent<InputField>();
            input.textComponent = field.UItext;
            input.lineType = InputField.LineType.SingleLine;
            storable.inputField = input;
        }
    }
}
