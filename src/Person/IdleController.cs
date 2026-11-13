// Idle motion and procedural head gestures.
//
// Applies a small additive rotation to the head controller: slow Perlin noise sway while
// idle, plus short procedural gestures (nod, shake, tilt). The offset of the previous frame
// is removed before the new one is applied, so user posing, Timeline animations or other
// plugins moving the head are preserved instead of overwritten.
//
// For full body idle animation prefer dedicated plugins on the same atom (E-Motion,
// Naturalis, Timeline idle loops, Glance for eyes) and start them via "trigger"/"gesture".
using System;
using UnityEngine;

namespace AIBody
{
    public class IdleController
    {
        private readonly FreeControllerV3 _head;
        private Quaternion _lastOffset = Quaternion.identity;
        private float _time;
        private readonly float _seed;

        private string _gesture;
        private float _gestureTime;
        private float _gestureDuration;
        private float _gestureAmplitude;

        public bool Enabled = true;

        /// <summary>0..1 overall amount of idle sway.</summary>
        public float Intensity = 0.5f;

        /// <summary>Maximum sway angle in degrees at intensity 1.</summary>
        public float MaxAngle = 4f;

        /// <summary>Extra multiplier while the character is speaking (people move more when talking).</summary>
        public float SpeakingBoost = 1.6f;

        public IdleController(Atom atom)
        {
            _head = atom.GetStorableByID("headControl") as FreeControllerV3;
            if (_head == null) Log.Error("No headControl on atom " + atom.uid + "; idle head motion disabled.");
            _seed = UnityEngine.Random.Range(0f, 100f);
        }

        public bool Available { get { return _head != null; } }

        public bool IsGesturing { get { return _gesture != null; } }

        /// <summary>Starts a built in head gesture. Returns false for unknown names.</summary>
        public bool PlayHeadGesture(string name, float duration, float amplitude)
        {
            if (name != "nod" && name != "shake" && name != "tilt") return false;
            _gesture = name;
            _gestureTime = 0f;
            _gestureDuration = duration > 0f ? duration : 1.2f;
            _gestureAmplitude = amplitude > 0f ? amplitude : 1f;
            return true;
        }

        /// <summary>Returns the gesture name when it just finished this frame, else null.</summary>
        public string Update(float deltaTime, bool speaking, float breathCycle, float breathDepth)
        {
            if (_head == null) return null;
            _time += deltaTime;
            string finished = null;

            // --- idle sway (degrees) ---
            float amount = Enabled ? Intensity * MaxAngle * (speaking ? SpeakingBoost : 1f) : 0f;
            float pitch = (Mathf.PerlinNoise(_seed, _time * 0.15f) - 0.5f) * 2f * amount;
            float yaw = (Mathf.PerlinNoise(_seed + 10f, _time * 0.11f) - 0.5f) * 2f * amount;
            float roll = (Mathf.PerlinNoise(_seed + 20f, _time * 0.09f) - 0.5f) * amount;

            // Breathing makes the head rise a tiny bit; express it as a small pitch.
            pitch -= breathCycle * breathDepth * 1.5f;

            // --- procedural gestures ---
            if (_gesture != null)
            {
                _gestureTime += deltaTime;
                float t = Mathf.Clamp01(_gestureTime / _gestureDuration);
                float envelope = Mathf.Sin(t * Mathf.PI); // fade in/out
                float wave = Mathf.Sin(t * Mathf.PI * 4f) * envelope * _gestureAmplitude;
                if (_gesture == "nod") pitch += wave * 12f;
                else if (_gesture == "shake") yaw += wave * 15f;
                else if (_gesture == "tilt") roll += envelope * 10f * _gestureAmplitude;
                if (t >= 1f)
                {
                    finished = _gesture;
                    _gesture = null;
                }
            }

            ApplyOffset(Quaternion.Euler(pitch, yaw, roll));
            return finished;
        }

        private void ApplyOffset(Quaternion offset)
        {
            // Only meaningful while the head controller drives rotation.
            if (_head.currentRotationState == FreeControllerV3.RotationState.Off)
            {
                _lastOffset = Quaternion.identity;
                return;
            }
            Transform t = _head.transform;
            Quaternion baseRot = t.rotation * Quaternion.Inverse(_lastOffset);
            t.rotation = baseRot * offset;
            _lastOffset = offset;
        }

        /// <summary>Removes any offset still applied (call on disable/destroy).</summary>
        public void RestoreNow()
        {
            if (_head == null) return;
            _head.transform.rotation = _head.transform.rotation * Quaternion.Inverse(_lastOffset);
            _lastOffset = Quaternion.identity;
            _gesture = null;
        }
    }
}
