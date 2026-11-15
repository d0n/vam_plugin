// Small UI helpers shared by the plugin's components.
using System;
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

        /// <summary>
        /// A text field the user can edit. The editable part (an InputField bound via
        /// storable.inputField, the ToySerialController pattern) is guarded: if it fails, the
        /// field stays visible but read-only and the reason goes to the log. Returns false then.
        /// TODO(verify): editable text field pattern on CreateTextField in VaM 1.22.
        /// </summary>
        public static bool TextInput(MVRScript plugin, JSONStorableString storable, bool rightSide)
        {
            UIDynamicTextField field = plugin.CreateTextField(storable, rightSide);
            field.height = 40f;
            try
            {
                InputField input = field.gameObject.AddComponent<InputField>();
                input.textComponent = field.UItext;
                input.lineType = InputField.LineType.SingleLine;
                storable.inputField = input;
                return true;
            }
            catch (Exception e)
            {
                Log.Error("Text field '" + storable.name + "' is read-only (InputField failed): " + Diag.Describe(e));
                return false;
            }
        }
    }
}
