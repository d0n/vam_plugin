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
    public class DmExpressions : DmBaseModule
    {
        GenerateDAZMorphsControlUI morphControl;

        JSONClass manifest;

        public DmExpressionGroup mouthOpenGroup;
        public DmExpressionGroup mouthClosedGroup;
        public DmExpressionGroup eyesGroup;
        public DmExpressionGroup idleGroup;
        public DmExpressionGroup kissGroup;
        public DmExpressionGroup climaxGroup;

        public static string EXPRESSIONS_PATH;

        public DmExpressions(DmPlugin dm) : base(dm)
        {
            EXPRESSIONS_PATH = DmPlugin.ASSETS_PATH + "/Expressions";
            string MANIFEST_PATH = EXPRESSIONS_PATH + "/expression_manifest.json";
            Log.Debug(MANIFEST_PATH);   // AIBody port, version 70: in-game log only through Log, and only when Verbose is on
            manifest = JSON.Parse(/* AIBody port: FileManagerSecure */ FileManagerSecure.ReadAllText(MANIFEST_PATH)).AsObject;

            mouthOpenGroup = new DmExpressionGroup(manifest["mouth open"].AsObject, dm);
            mouthClosedGroup = new DmExpressionGroup(manifest["mouth closed"].AsObject, dm);
            eyesGroup = new DmExpressionGroup(manifest["eyes"].AsObject, dm);
            idleGroup = new DmExpressionGroup(manifest["idle"].AsObject, dm);
            kissGroup = new DmExpressionGroup(manifest["kiss"].AsObject, dm);
            climaxGroup = new DmExpressionGroup(manifest["climax"].AsObject, dm);

            JSONStorable geometry = atom.GetStorableByID("geometry");
            DAZCharacterSelector character = geometry as DAZCharacterSelector;
            morphControl = character.morphsControlUI;
        }

        public float GetStay(string category, string name, float defaultValue)
        {
            JSONClass node = manifest[category][name].AsObject;
            if (node == null)
            {
                return defaultValue;
            }
            else
            {
                return node["stay"].AsFloat;
            }
        }

        void ClearExpressionMorphs()
        {
            morphControl.GetMorphDisplayNames().ForEach((name) =>
            {
                DAZMorph morph = morphControl.GetMorphByDisplayName(name);
                if (morph.isPoseControl || morph.region.Contains("Expressions"))
                {
                    morph.SetValue(morph.startValue);
                    morph.SyncJSON();
                }
            });
        }

        void ApplyJSONMorphs(JSONClass node)
        {
            JSONArray morphs = node["morphs"].AsArray;
            for (int i = 0; i < morphs.Count; i++)
            {
                JSONClass morphNode = morphs[i].AsObject;
                string name = morphNode["name"].Value;
                float value = morphNode["value"].AsFloat;
                DAZMorph morph = morphControl.GetMorphByDisplayName(name);
                if (morph == null)
                {
                    Log.Error("No morph named " + name);   // AIBody port, version 70: in-game log only through Log, and only when Verbose is on
                    continue;
                }
                if (morph.isPoseControl || morph.region.Contains("Expressions"))
                {
                    morph.SetValue(value);
                    morph.SyncJSON();
                }
            }
        }

        public override void OnDestroy()
        {
            base.OnDestroy();
            ClearExpressionMorphs();
        }

    }
}
