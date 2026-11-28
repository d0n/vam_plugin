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
    public class DmMontage
    {
        Atom atom;
        public string name;
        public JSONClass montageJSON;
        public List<Pose> poses = new List<Pose>();
        int currentPoseIndex = 0;

        public DmMontage(Atom atom, string filePath)
        {
            this.atom = atom;
            montageJSON = JSON.Parse(FileManagerSecure.ReadAllText(filePath)) as JSONClass;   // AIBody port: FileManagerSecure
            poses.Add(ExtractPersonPose(montageJSON));

            string fileName = DmPathExt.GetFileName(filePath);
            string folder = filePath.Replace(fileName, "");
            string montageName = DmPathExt.GetFileNameWithoutExtension(filePath);

            name = montageName;

            List<string> poseFiles = FileManagerSecure.GetFiles(folder, "*.json").ToList().Where(path =>   // AIBody port: FileManagerSecure
            {
                if (path.Contains(montageName) == false)
                {
                    return false;
                }
                int periodCount = path.Count(f => f == '.');
                if (periodCount <= 1)
                {
                    return false;
                }
                return true;
            }).ToList();

            poseFiles.ForEach(poseFilePath =>
            {
                //Debug.Log("pose file found" + poseFilePath);
                var poseMontageJSON = JSON.Parse(FileManagerSecure.ReadAllText(poseFilePath)) as JSONClass;   // AIBody port: FileManagerSecure

                poses.Add(ExtractPersonPose(poseMontageJSON));
            });

            //Debug.Log("montage " + filePath + " has " + poses.Count() + " poses");
        }

        public Pose ExtractPersonPose(JSONClass json)
        {
            JSONArray atoms = json["atoms"].AsArray;

            JSONClass person1JSON = null;
            JSONClass person2JSON = null;
            for (int i = 0; i < atoms.Count; i++)
            {
                JSONClass atomObj = atoms[i].AsObject;
                string id = atomObj["id"].Value;
                if (id == "Person")
                {
                    person1JSON = atomObj;
                }
                if (id == "Person#2")
                {
                    person2JSON = atomObj;
                }
            }
            if (person1JSON == null)
            {
                Log.Error("Expected at least one person named Person in montage");   // AIBody port, version 70: in-game log only through Log, and only when Verbose is on
                return null;
            }

            return new Pose(atom, person1JSON);
        }

        public void Activate(DmPlugin dm)
        {
            DmMontageController.BeginMontage(dm, montageJSON);
        }

        public Pose SelectRandomPose()
        {
            if (poses.Count <= 0)
            {
                return null;
            }
            if (poses.Count == 1)
            {
                return poses[0];
            }

            int index = UnityEngine.Random.Range(0, poses.Count);
            while (currentPoseIndex == index)
            {
                index = UnityEngine.Random.Range(0, poses.Count);
            }

            currentPoseIndex = index;
            return poses[index];
        }
    }
}
