// Dollmaster (VAMDeluxe, 2019; Don's copy of Dollmaster, upstream github.com/vamdeluxe/DeluxePlugin, MIT) ported into
// AIBody (22.11.2026, Don): same code, types prefixed Dm, namespace AIBody; changes only where the project rules need them
// (marked "AIBody port:").
using System;
using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using SimpleJSON;
using System.Linq;   // AIBody port: the LINQ calls below need it in the stub compile
using MVR.FileManagementSecure;   // AIBody port: file access only through FileManagerSecure


namespace AIBody
{
    public class DmPersonas : DmBaseModule
    {
        public static string PERSONA_PATH;

        Dictionary<string, DmPersonality> nameToPersonality = new Dictionary<string, DmPersonality>();

        public DmPersonas(DmPlugin dm) : base(dm)
        {
            PERSONA_PATH = DmPlugin.ASSETS_PATH + "/Personas";
            /* AIBody port: FileManagerSecure */ FileManagerSecure.GetDirectories(PERSONA_PATH).ToList().ForEach((string path)=>
            {
                path = SuperController.singleton.NormalizePath(path);
                string name = DmPathExt.GetFileName(path);
                nameToPersonality[name] = new DmPersonality(path, name);
            });
        }

        public DmPersonality GetPersonality(string name)
        {
            return nameToPersonality[name];
        }

        public DmPersonality GetRandomPersonality()
        {
            int randomIndex = Mathf.Clamp(UnityEngine.Random.Range(0, personalities.Count), 0, personalities.Count-1);
            return personalities[randomIndex];
        }

        public List<string> personalityNames
        {
            get
            {
                List<string> names = new List<string>();   // AIBody port: no Keys property (CS584)
                foreach (KeyValuePair<string, DmPersonality> kv in nameToPersonality) names.Add(kv.Key);
                return names;
            }
        }

        public List<DmPersonality> personalities
        {
            get
            {
                List<DmPersonality> list = new List<DmPersonality>();   // AIBody port: no Values property (CS584)
                foreach (KeyValuePair<string, DmPersonality> kv in nameToPersonality) list.Add(kv.Value);
                return list;
            }
        }
    }
}
