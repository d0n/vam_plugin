// Dollmaster (VAMDeluxe, 2019; Don's copy of Dollmaster, upstream github.com/vamdeluxe/DeluxePlugin, MIT) ported into
// AIBody (22.11.2026, Don): same code, types prefixed Dm, namespace AIBody; changes only where the project rules need them
// (marked "AIBody port:").
using System;
using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using SimpleJSON;
using System.Linq;


namespace AIBody
{
    public class DmSFXController : DmBaseModule
    {
        Atom audioAtom;

        string atomPrefix = "Doll SFX";

        List<NamedAudioClip> skinContactSFX = new List<NamedAudioClip>();
        List<NamedAudioClip> insertionSFX = new List<NamedAudioClip>();

        float minDuration = 0.27f;
        float timeLastPlayed = 0;

        JSONStorableBool playSoundEffects;

        public DmSFXController(DmPlugin dm) : base(dm)
        {
            /* AIBody port: helper atom only while Dollmaster is active */ dm.MakeAtom(atomPrefix, () => CreateAtom("AudioSource", atomPrefix, (createdAtom) =>
            {
                audioAtom = createdAtom;

                FreeControllerV3 hipControl = dm.containingAtom.GetStorableByID("hipControl") as FreeControllerV3;
                audioAtom.mainController.transform.SetPositionAndRotation(hipControl.transform.position, hipControl.transform.rotation);
                audioAtom.mainController.transform.Translate(0, -0.1f, 0, Space.Self);

                audioAtom.mainController.currentPositionState = FreeControllerV3.PositionState.ParentLink;
                audioAtom.mainController.currentRotationState = FreeControllerV3.RotationState.ParentLink;
                audioAtom.mainController.canGrabPosition = false;
                audioAtom.mainController.canGrabRotation = false;
                Rigidbody rb = SuperController.singleton.RigidbodyNameToRigidbody(atom.name + ":hipControl");
                audioAtom.mainController.SelectLinkToRigidbody(rb, FreeControllerV3.SelectLinkState.PositionAndRotation);

                audioAtom.hidden = true;

            }));

            // AIBody port: the clip loading that stood here is LoadClips (below), run at each activation.
            playSoundEffects = new JSONStorableBool("playSoundEffects", true);
            dm.RegisterBool(playSoundEffects);
            UIDynamicToggle moduleEnableToggle = dm.CreateToggle(playSoundEffects);
            moduleEnableToggle.label = "Enable Sound Effects";
            moduleEnableToggle.backgroundColor = Color.green;

            dm.CreateSpacer();
        }

        /// <summary>
        /// AIBody port: the effect clips (formerly loaded in the constructor) are loaded at each activation
        /// (DmPlugin.OnActivated), because OnDestroy frees them when Activate is switched off.
        /// </summary>
        public void LoadClips()
        {
            skinContactSFX.Clear();
            insertionSFX.Clear();
            JSONClass sfxDefaults = dm.config.configJSON["sfxDefaults"].AsObject;
            JSONArray skinContacts = sfxDefaults["skinContact"].AsArray;
            JSONArray insertion = sfxDefaults["insertion"].AsArray;

            for(int i=0; i < skinContacts.Count; i++)
            {
                string path = DmPlugin.PLUGIN_PATH + "/" + skinContacts[i].Value;
                skinContactSFX.Add(DmPlugin.LoadAudio(path));
            }

            for (int i = 0; i < insertion.Count; i++)
            {
                string path = DmPlugin.PLUGIN_PATH + "/" + insertion[i].Value;
                insertionSFX.Add(DmPlugin.LoadAudio(path));
            }

        }   // AIBody port: end of LoadClips (the constructor's former clip loading)

        public NamedAudioClip GetRandomSkinClip()
        {
            int randomIndex = UnityEngine.Random.Range(0, skinContactSFX.Count);
            return skinContactSFX[randomIndex];
        }

        public NamedAudioClip GetRandomInsertionClip()
        {
            int randomIndex = UnityEngine.Random.Range(0, insertionSFX.Count);
            return insertionSFX[randomIndex];
        }

        public void Trigger()
        {
            if (playSoundEffects.val == false)
            {
                return;
            }

            if(dm.thrustController.sliderValue <= 0.2f)
            {
                return;
            }

            if (audioSource == null)
            {
                return;
            }

            audioSource.pitch = UnityEngine.Random.Range(0.9f, 1.1f);

            if ((Time.time - timeLastPlayed) < minDuration)
            {
                return;
            }

            Play();
        }

        public void Play()
        {
            timeLastPlayed = Time.time;

            if (dm.thrustController.sliderValue < dm.thrustController.slider.slider.maxValue * 0.6f)
            {
                audioSource.volume = 1.0f;
                audioSource.PlayNow(GetRandomInsertionClip());
            }
            else
            {
                audioSource.volume = 0.5f + ((dm.thrustController.sliderValue - 3.0f) / dm.thrustController.slider.slider.maxValue) * 0.5f;
                audioSource.PlayNow(GetRandomSkinClip());
            }
        }

        protected override void OnContainingAtomRenamed(string oldName, string newName)
        {
            if (audioAtom != null)
            {
                audioAtom.name = audioAtom.uid = GenerateAtomName(atomPrefix, newName);
            }
        }

        public AudioSourceControl audioSource
        {
            get {
                if (audioAtom == null)
                {
                    return null;
                }
                return audioAtom.GetStorableByID("AudioSource") as AudioSourceControl;
            }
        }

        public override void OnDestroy()
        {
            base.OnDestroy();
            skinContactSFX.ForEach((clip) =>
            {
                URLAudioClipManager.singleton.RemoveClip(clip);
            });

            insertionSFX.ForEach((clip) =>
            {
                URLAudioClipManager.singleton.RemoveClip(clip);
            });

            if (audioAtom != null)
            {
                SuperController.singleton.RemoveAtom(audioAtom);
            }
        }
    }
}
