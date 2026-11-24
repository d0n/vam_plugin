// Dollmaster (VAMDeluxe, 2019; Don's copy of Dollmaster, upstream github.com/vamdeluxe/DeluxePlugin, MIT) ported into
// AIBody (22.11.2026, Don): same code, types prefixed Dm, namespace AIBody; changes only where the project rules need them
// (marked "AIBody port:").
using System;
using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using SimpleJSON;
using MVR.FileManagementSecure;   // AIBody port: file access only through FileManagerSecure
using System.Linq;

namespace AIBody
{
    public class DmConfig : DmBaseModule
    {
        public JSONClass configJSON;

        public DmConfig(DmPlugin dm) : base(dm)
        {
            // AIBody port: dollmaster_config.json (same content as the old config.json; no file named config.json ships in the .var)
            string CONFIG_PATH = DmPlugin.PLUGIN_PATH + "/dollmaster_config.json";
            configJSON = JSON.Parse(/* AIBody port: FileManagerSecure */ FileManagerSecure.ReadAllText(CONFIG_PATH)).AsObject;
            // AIBody port: Apply() runs at activation (DmPlugin.OnActivated), not while Dollmaster is off.
        }

        public void Apply()
        {
            if(configJSON == null)
            {
                return;
            }

            JSONClass personDefaults = configJSON["personDefaults"].AsObject;

            if (personDefaults["autoExpression"] != null)
            {
                atom.GetStorableByID("AutoExpressions").SetBoolParamValue("enabled", personDefaults["autoExpression"].AsBool);
            }

            if (personDefaults["lookMode"] != null)
            {
                atom.GetStorableByID("Eyes").SetStringChooserParamValue("lookMode", personDefaults["lookMode"].Value);
            }
        }
    }
}
