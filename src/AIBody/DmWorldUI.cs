// Dollmaster (VAMDeluxe, 2019; Leon's copy of Dollmaster, upstream github.com/vamdeluxe/DeluxePlugin, MIT) ported into
// AIBody (22.11.2026, Leon): same code, types prefixed Dm, namespace AIBody; changes only where the project rules need them
// (marked "AIBody port:").
using System;
using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using SimpleJSON;

namespace AIBody
{
    public class DmWorldUI : DmBaseModule
    {
        Atom UIAtom;

        string atomPrefix = "Doll Control";

        public DmWorldUI(DmPlugin dm) : base(dm)
        {
            /* AIBody port: helper atom only while Dollmaster is active */ dm.MakeAtom(atomPrefix, () => CreateAtom("Empty", atomPrefix, (atom)=>
            {
                UIAtom = atom;

                FreeControllerV3 headControl = dm.containingAtom.GetStorableByID("headControl") as FreeControllerV3;
                Vector3 headPosition = headControl.transform.position;
                UIAtom.mainController.transform.position = headPosition;
                UIAtom.mainController.transform.Translate(new Vector3(-0.5f, 0, 0), Space.Self);
                ui.canvas.transform.SetParent(UIAtom.mainController.transform, false);
            }));
        }

        protected override void OnContainingAtomRenamed(string oldName, string newName)
        {
            if (UIAtom != null)
            {
                UIAtom.name = UIAtom.uid = GenerateAtomName(atomPrefix, newName);
            }
        }
    }
}
