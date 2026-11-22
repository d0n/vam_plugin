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
    public class DmDressController : DmBaseModule
    {
        List<bool> priorClothes = new List<bool>();
        bool dressed = true;
        DAZCharacterSelector geometry;

        public DmDressController(DmPlugin dm) : base(dm)
        {
            JSONStorable geometryStorable = atom.GetStorableByID("geometry");
            geometry = geometryStorable as DAZCharacterSelector;

            priorClothes = geometry.clothingItems.ToList().Select((clothing) =>
            {
                return clothing.active;
            }).ToList();
            dressed = true;
        }

        public void ToggleDressed()
        {
            dressed = !dressed;

            if (!dressed)
            {
                int index = 0;
                geometry.clothingItems.ToList().ForEach((clothing) =>
                {
                    geometry.SetActiveClothingItem(clothing, active: false);
                    index++;
                });
            }
            else
            {
                List<DAZClothingItem> clothes = geometry.clothingItems.ToList();
                for (int i = 0; i < priorClothes.Count; i++)
                {
                    geometry.SetActiveClothingItem(clothes[i], priorClothes[i]);
                }
            }
        }

        public void OnRestore()
        {
            priorClothes = geometry.clothingItems.ToList().Select((clothing) =>
            {
                return clothing.active;
            }).ToList();
            dressed = true;
        }

        public void CycleDressExposed()
        {
            CycleDressProgression(GetWrapProgression());
        }

        void CycleDressProgression(Dictionary<DAZSkinWrapSwitcher, List<string>> wrapProgression)
        {
            DmKeys.Of(wrapProgression).ForEach((switcher) =>   // AIBody port: no Keys property (CS584)
            {
                if (switcher.enabled == false)
                {
                    return;
                }

                //Debug.Log(wrap.wrapName + " " + wrap.wrapProgress);
                List<string> progressNames = wrapProgression[switcher];
                int current = progressNames.FindIndex((s) =>
                {
                    return s == switcher.currentWrapName;
                });

                int next = current + 1;
                if (next >= progressNames.Count)
                {
                    next = 0;
                }

                string nextName = progressNames[next];
                if (nextName != null)
                {
                    //Debug.Log(switcher.currentWrapName + " switching to " + nextName);
                    switcher.SetCurrentWrapName(nextName);
                }

            });
        }


        Dictionary<DAZSkinWrapSwitcher, List<string>> GetWrapProgression()
        {
            JSONStorable geometryStorable = atom.GetStorableByID("geometry");
            DAZCharacterSelector geometry = geometryStorable as DAZCharacterSelector;
            Dictionary<DAZSkinWrapSwitcher, List<string>> wrapToProgressList = new Dictionary<DAZSkinWrapSwitcher, List<string>>();

            atom.GetStorableIDs().ForEach((s) =>
            {
                JSONStorable store = atom.GetStorableByID(s);
                store.GetComponents<DAZSkinWrap>().ToList().ForEach((wrap) =>
                {
                    DAZSkinWrapSwitcher switcher = store.GetComponent<DAZSkinWrapSwitcher>();
                    if (switcher == null)
                    {
                        return;
                    }

                    if (wrap.enabled == false)
                    {
                        return;
                    }

                    if (s.Contains("Style") == false)
                    {
                        return;
                    }

                    if (wrapToProgressList.ContainsKey(switcher) == false)
                    {
                        wrapToProgressList[switcher] = new List<string>();
                    }

                    wrapToProgressList[switcher].Add(wrap.wrapName);
                });
            });

            return wrapToProgressList;
        }

    }
}
