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
    public class DmExpressionGroup
    {
        Dictionary<string, JSONClass> nameToJSON = new Dictionary<string, JSONClass>();
        DmPlugin dm;

        Dictionary<string, NamedAudioClip> audioClips = new Dictionary<string, NamedAudioClip>();

        public DmExpressionGroup(JSONClass groupJSON, DmPlugin dm)
        {
            this.dm = dm;
            // AIBody port: the pairs of the JSONClass instead of the Keys property (VaM's compiler, CS584)
            foreach (KeyValuePair<string, JSONNode> kv in groupJSON)
            {
                 string key = kv.Key;
                 string name = DmPathExt.GetFileNameWithoutExtension(key);
                 JSONClass node = KeyToJSON(key, groupJSON[key]);
                 nameToJSON[name] = node;
            }   // AIBody port: end of the foreach
        }

        JSONClass KeyToJSON(string key, JSONNode expressionNode)
        {
            if (key.ToLower().Contains(".json"))
            {
                string expressionPath = DmExpressions.EXPRESSIONS_PATH + "/" + key;
                //Debug.Log(expressionPath);
                JSONClass expression = JSON.Parse(/* AIBody port: FileManagerSecure */ FileManagerSecure.ReadAllText(expressionPath)).AsObject;
                if (expression["audio"] != null)
                {
                    NamedAudioClip clip = DmPlugin.LoadAudio(DmPlugin.PLUGIN_PATH +"/"+ expression["audio"]);
                    audioClips[expression["audio"]] = clip;
                }

                return expression;
            }
            else
            {
                JSONClass node = new JSONClass();
                node["morphs"] = new JSONArray();
                JSONClass morphNode = new JSONClass();
                morphNode["name"] = key;
                morphNode["value"] = expressionNode;
                node["morphs"].Add(morphNode);
                return node;
            }
        }

        public JSONNode SelectRandomExpression()
        {
            if (nameToJSON.Count == 0)
            {
                return null;
            }
            int index = Mathf.Clamp(UnityEngine.Random.Range(0, nameToJSON.Count), 0, nameToJSON.Count - 1);
            // AIBody port: the index-th value by walking the pairs (no Values property, CS584)
            JSONClass expression = null;
            int at = 0;
            foreach (KeyValuePair<string, JSONClass> kv in nameToJSON)
            {
                if (at == index) { expression = kv.Value; break; }
                at++;
            }

            if (expression["audio"] != null)
            {
                dm.PlayAudio(audioClips[expression["audio"]]);
            }

            return expression;
        }
    }
}
