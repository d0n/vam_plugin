// Dollmaster (VAMDeluxe, 2019; Leon's copy of Dollmaster, upstream github.com/vamdeluxe/DeluxePlugin, MIT) ported into
// AIBody (22.11.2026, Leon): same code, types prefixed Dm, namespace AIBody; changes only where the project rules need them
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
    public class DmMontageController : DmBaseModule
    {
        public List<DmMontage> montages = new List<DmMontage>();

        DmPoseController poseController;

        public DmMontage currentMontage;

        public JSONStorableUrl montagePath;
        UIDynamicButton poseButton;

        Color accessButtonColor = new Color(0.05f, 0.35f, 0.08f);
        Color accessButtonColorDisabled = new Color(0.25f, 0.25f, 0.25f);
        Color accessTextColor = new Color(1, 1, 1);
        Color accessTextColorDisabled = new Color(0.5f, 0.5f, 0.5f);

        public DmMontageController(DmPlugin dm, DmPoseController poseController) : base(dm)
        {
            montagePath = new JSONStorableUrl("montagePath", DmPlugin.VAMASUTRA_PATH);
            dm.RegisterUrl(montagePath);
            UIDynamicButton selectMontageFolderButton = dm.CreateButton("Select Montage Folder", true);
            selectMontageFolderButton.button.onClick.AddListener(() =>
            {
                SuperController.singleton.directoryBrowserUI.defaultPath = SuperController.singleton.savesDir;
                SuperController.singleton.directoryBrowserUI.showDirs = true;
                SuperController.singleton.directoryBrowserUI.showFiles = false;
                SuperController.singleton.directoryBrowserUI.selectDirectory = true;
                SuperController.singleton.directoryBrowserUI.SetTextEntry(true);
                SuperController.singleton.directoryBrowserUI.Show((path) => {
                    montagePath.SetVal(path);
                    LoadMontagesFromPath(path);
                });
            });

            UIDynamicButton montageButton = ui.CreateButton("Random Montage", 200, 50);
            montageButton.button.onClick.AddListener(RandomMontage);
            montageButton.transform.Translate(0, 0.3f, 0, Space.Self);
            DmUI.ColorButton(montageButton, accessTextColor, accessButtonColor);

            poseButton = ui.CreateButton("Random Pose", 200, 50);
            poseButton.button.onClick.AddListener(RandomPose);
            poseButton.transform.Translate(0.3f, 0.3f, 0, Space.Self);
            DmUI.ColorButton(poseButton, accessTextColor, accessButtonColor);
        }

        public override void Update()
        {
            if (currentMontage!=null && currentMontage.poses.Count>1)
            {
                poseButton.button.enabled = true;
                poseButton.buttonColor = accessButtonColor;
                poseButton.textColor = accessTextColor;
            }
            else
            {
                poseButton.button.enabled = false;
                poseButton.buttonColor = accessButtonColorDisabled;
                poseButton.textColor = accessTextColorDisabled;
            }
        }

        public void LoadMontagesFromPath(string path)
        {
            montages = new List<DmMontage>();
            List<string> files = /* AIBody port: FileManagerSecure */ FileManagerSecure.GetFiles(path, "*.json").ToList();
            files.ForEach(fileName =>
            {
                int periodCount = fileName.Count(f => f == '.');
                if (periodCount == 1)
                {
                    montages.Add(new DmMontage(atom, fileName));
                }
            });
        }

        public void RandomMontage()
        {
            currentMontage = SelectRandomMontage();
            if (currentMontage != null)
            {
                //SuperController.LogMessage("selected montage " + currentMontage.name);
                //SuperController.LogMessage(currentMontage.poses.Count().ToString());
                currentMontage.Activate(dm);
            }
        }

        public DmMontage SelectRandomMontage()
        {
            if (montages.Count <= 0)
            {
                return null;
            }

            if (montages.Count == 1)
            {
                return montages[0];
            }

            if (currentMontage == null)
            {
                int randomIndex = UnityEngine.Random.Range(0, montages.Count);
                return montages[randomIndex];
            }

            int currentMontageIndex = montages.FindIndex((montage=>montage==currentMontage));

            int index = UnityEngine.Random.Range(0, montages.Count);
            while (index == currentMontageIndex)
            {
                index = UnityEngine.Random.Range(0, montages.Count);
            }

            return montages[index];
        }

        public void RandomPose()
        {
            if (currentMontage == null)
            {
                return;
            }

            Pose pose = currentMontage.SelectRandomPose();
            if (pose != null)
            {
                dm.poseController.AnimateToPose(pose);
            }
        }

        public void NextThruster()
        {
            AnimationPattern ap = dm.thrustController.ap;
            if (ap == null)
            {
                return;
            }

            Atom apAtom = ap.containingAtom;
            MoveProducer mp = apAtom.GetStorableByID("AnimatedObject") as MoveProducer;

            Atom otherPerson = DmPlugin.GetSomeoneElse(mp.receiver.containingAtom);
            if (otherPerson == null)
            {
                return;
            }

            Atom otherOtherPerson = DmPlugin.GetSomeoneElse(otherPerson);
            if (otherOtherPerson == null)
            {
                return;
            }

            dm.thrustController.ConfigureAPSteps(otherPerson, otherOtherPerson);

        }

        public static void BeginMontage(DmPlugin dm, JSONNode montageJSON)
        {
            dm.poseController.StopCurrentAnimation();

            JSONArray atoms = montageJSON["atoms"].AsArray;

            JSONClass person1Pose = null;
            JSONClass person2Pose = null;
            for (int i = 0; i < atoms.Count; i++)
            {
                JSONClass atomObj = atoms[i].AsObject;
                string id = atomObj["id"].Value;
                if (id == "Person")
                {
                    person1Pose = atomObj;
                }
                if (id == "Person#2")
                {
                    person2Pose = atomObj;
                }
            }

            Atom atom = dm.containingAtom;
            Atom otherPerson = DmPlugin.GetSomeoneElse(atom);

            // AIBody port, version 56 (Leon 24.11.2026 15:27): a montage stores both people's world placement; the shared
            // pose wrapper keeps the AI at her place and moves the other person by the same correction (the couple's
            // arrangement stays). Without the wrapper (not set) it behaves as the old plugin.
            PoseGuard guard = dm.PlaceGuard != null ? dm.PlaceGuard() : null;
            Func<string> load = () => // AIBody port, version 56: the old restores, unchanged, run inside the wrapper
            {
                if (person1Pose != null)
                {
                    atom.PreRestore();
                    atom.RestoreTransform(person1Pose);
                    atom.Restore(person1Pose, restorePhysical: true, restoreAppearance: false, restoreCore: false);
                    atom.LateRestore(person1Pose, restorePhysical: true, restoreAppearance: false, restoreCore: false);
                    atom.PostRestore();
                }
                if (person2Pose != null && otherPerson != null)
                {
                    otherPerson.PreRestore();
                    otherPerson.RestoreTransform(person2Pose);
                    otherPerson.Restore(person2Pose, restorePhysical: true, restoreAppearance: false, restoreCore: false);
                    otherPerson.LateRestore(person2Pose, restorePhysical: true, restoreAppearance: false, restoreCore: false);
                    otherPerson.PostRestore();
                }
                return null;
            };
            // AIBody port, version 56: through the shared pose wrapper when it is set
            if (guard != null) guard.Around("Dollmaster montage", load, person2Pose != null ? otherPerson : null);
            else load();

            SuperController.singleton.PauseSimulation(5, "Loading Sutra");

            dm.thrustController.Clear();
            dm.thrustController.GenerateThrustAtoms();

            DmExpressionController.ZeroPoseMorphs(atom);
            DmExpressionController.ZeroPoseMorphs(otherPerson);
        }

    }
}
