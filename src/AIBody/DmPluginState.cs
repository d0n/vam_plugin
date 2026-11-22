// Dollmaster (VAMDeluxe, 2019; Leon's copy of Dollmaster, upstream github.com/vamdeluxe/DeluxePlugin, MIT) ported into
// AIBody (22.11.2026, Leon): same code, types prefixed Dm, namespace AIBody; changes only where the project rules need them
// (marked "AIBody port:").
using System;
using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using SimpleJSON;
using System.Linq;

namespace AIBody
{
    public class DmPluginState
    {
        public JSONStorableStringChooser personalityChoice;
        public string defaultPersonalityName = "Celeste";

        public DmPluginState(DmPlugin dm)
        {
            personalityChoice = new JSONStorableStringChooser("personality", dm.personas.personalityNames, defaultPersonalityName, "Personality", (string choice)=>
            {
                dm.SetPersonality(choice);
            });

            dm.SetPersonality(personalityChoice.val);

            dm.RegisterStringChooser(personalityChoice);

            UIPopup popup = dm.ui.CreatePopup("Personality", 300, 80);
            popup.transform.Translate(0.7f, 0.065f, 0, Space.Self);
            popup.showSlider = true;
            personalityChoice.popup = popup;

            //UIDynamicPopup personalityPopup = dm.CreatePopup(personalityChoice);
            //personalityPopup.popup.topButton.image.color = new Color(0.8f, 0.65f, 0.13f);
            //dm.CreateSpacer();
        }
    }
}
