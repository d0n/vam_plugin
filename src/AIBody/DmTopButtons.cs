// Dollmaster (VAMDeluxe, 2019; Don's copy of Dollmaster, upstream github.com/vamdeluxe/DeluxePlugin, MIT) ported into
// AIBody (22.11.2026, Don): same code, types prefixed Dm, namespace AIBody; changes only where the project rules need them
// (marked "AIBody port:").
using System;
using UnityEngine;
using UnityEngine.Events;
using System.Collections;
using System.Collections.Generic;
using SimpleJSON;
using MVR.FileManagementSecure;   // AIBody port: file access only through FileManagerSecure
using System.Linq;
using MeshVR;

namespace AIBody
{
    public class DmTopButtons : DmBaseModule
    {
        int column = 0;
        int row = 0;

        public DmTopButtons(DmPlugin dm) : base(dm)
        {
            AddButton("Select Person", () =>
            {
                SuperController.singleton.editModeToggle.isOn = true;
                SuperController.singleton.ShowMainHUDAuto();
                SuperController.singleton.ClearSelection();
                SuperController.singleton.SelectController(atom.mainController);
            });

            AddButton("Undress", () =>
            {
                dm.dressController.ToggleDressed();
            });

            AddButton("VAMasutra", () =>
            {
                SuperController.singleton.ShowMainHUDAuto();
                string sutraPath = DmPlugin.ASSETS_PATH + "/VAMasutra";
                SuperController.singleton.fileBrowserUI.defaultPath = sutraPath;
                SuperController.singleton.fileBrowserUI.SetTextEntry(b: false);
                SuperController.singleton.fileBrowserUI.Show((path) => {
                    var montageJSON = JSON.Parse(/* AIBody port: FileManagerSecure */ FileManagerSecure.ReadAllText(path)) as JSONClass;
                    dm.montageController.currentMontage = null;
                    DmMontageController.BeginMontage(dm, montageJSON);
                });
            });

            AddButton("Next Thruster", () =>
            {
                dm.montageController.NextThruster();
            });

            bool minimized = false;

            UIDynamicButton minimizeUIButton = ui.CreateButton("Minimize UI", 100, 40);
            minimizeUIButton.transform.Translate(0.1f, -0.1f, 0, Space.Self);
            DmUI.ColorButton(minimizeUIButton, Color.white, Color.black);

            Dictionary<GameObject, bool> priorActive = new Dictionary<GameObject, bool>();
            minimizeUIButton.button.onClick.AddListener(() =>
            {
                minimized = !minimized;

                Transform t = ui.canvas.transform;
                for(int i=0; i < t.childCount; i++)
                {
                    GameObject child = t.GetChild(i).gameObject;
                    if (minimized)
                    {
                        priorActive[child] = child.activeSelf;
                        child.SetActive(false);
                    }
                    else
                    {
                        child.SetActive(priorActive[child]);
                    }
                }

                minimizeUIButton.gameObject.SetActive(true);

                minimizeUIButton.label = minimized ? "Max UI" : "Minimize UI";
            });
        }

        public void AddButton(string name, UnityAction callback)
        {
            Color accessButtonColor = new Color(0.05f, 0.15f, 0.08f);
            Color accessTextColor = new Color(0.4f, 0.6f, 0.45f);
            float xSpacing = 0.22f;
            float ySpacing = 0.05f;

            UIDynamicButton button = ui.CreateButton(name, 100, 40);
            button.button.onClick.AddListener(callback);
            button.transform.Translate(column * xSpacing, 0.45f - row * ySpacing, 0, Space.Self);
            DmUI.ColorButton(button, accessTextColor, accessButtonColor);

            column++;
            if(column >= 2)
            {
                column = 0;
                row++;
            }
        }

    }
}
