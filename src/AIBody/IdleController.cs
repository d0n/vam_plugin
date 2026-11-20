// Idle motion and procedural head gestures, AIBody's own (version 35: no other idle / breathing plugin needed, no code
// taken from other plugins).
//
// Applies small additive rotations:
//   - head controller: slow Perlin noise sway while idle (more while speaking), the breath rise, and short
//     procedural gestures (nod, shake, tilt);
//   - chest controller (version 35): a slow weight shift from side to side every few seconds, a little sway and the
//     breath rise of the chest, so the upper body never stands still.
// The offset of the previous frame is removed before the new one is applied, so user posing, Timeline animations or
// other plugins moving the controllers are preserved instead of overwritten. After a pose is loaded the offsets are
// forgotten (Rebase), because the pose set the controllers anew.
//
// For full body idle animation other plugins on the same atom (Timeline idle loops, ...) still work and can be started
// via "trigger" / "gesture"; AIBody does not depend on them.
using System;
using UnityEngine;

namespace AIBody
{
    public class IdleController
    {
        private readonly Atom _atom;
        private FreeControllerV3 _head;   // looked up lazily, retried every 5 s
        private FreeControllerV3 _chest;  // TODO(verify): storable id "chestControl" (same pattern as headControl, E6)
        private float _retryIn;
        private Quaternion _lastOffset = Quaternion.identity;
        private Quaternion _lastChestOffset = Quaternion.identity;
        private float _time;
        private readonly float _seed;

        private string _gesture;
        private float _gestureTime;
        private float _gestureDuration;
        private float _gestureAmplitude;

        // weight shift: the side changes every ShiftMin..ShiftMax seconds, blended smoothly
        private float _shiftTarget;
        private float _shift;
        private float _shiftIn;
        private const float ShiftMin = 5f;
        private const float ShiftMax = 11f;

        public bool Enabled = true;

        /// <summary>0..1 overall amount of idle sway.</summary>
        public float Intensity = 0.5f;

        /// <summary>Maximum sway angle in degrees at intensity 1.</summary>
        public float MaxAngle = 4f;

        /// <summary>Maximum weight-shift lean of the chest in degrees at intensity 1.</summary>
        public float MaxChestAngle = 2.5f;

        /// <summary>Extra multiplier while the character is speaking (people move more when talking).</summary>
        public float SpeakingBoost = 1.6f;

        public IdleController(Atom atom)
        {
            _atom = atom;
            Resolve();
            if (_head == null) Log.Error("No headControl on atom " + atom.uid + " yet; idle head motion waits for it.");
            _seed = UnityEngine.Random.Range(0f, 100f);
            _shiftIn = UnityEngine.Random.Range(ShiftMin, ShiftMax);
        }

        public bool Available { get { return _head != null; } }

        /// <summary>True when the chest controller was found (weight shift and chest breathing work).</summary>
        public bool ChestAvailable { get { return _chest != null; } }

        private void Resolve()
        {
            try { _head = _atom.GetStorableByID("headControl") as FreeControllerV3; }
            catch (Exception) { _head = null; }
            try { _chest = _atom.GetStorableByID("chestControl") as FreeControllerV3; }
            catch (Exception) { _chest = null; }
        }

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
            if (_head == null)
            {
                _retryIn -= deltaTime;
                if (_retryIn > 0f) return null;
                _retryIn = 5f;
                Resolve();
                if (_head == null) return null;
                Log.Info("headControl found; idle head motion enabled" + (_chest != null ? " (with chest weight shift)." : "."));
            }
            _time += deltaTime;
            string finished = null;

            // --- idle sway (degrees) ---
            float amount = Enabled ? Intensity * MaxAngle * (speaking ? SpeakingBoost : 1f) : 0f;
            float pitch = (Mathf.PerlinNoise(_seed, _time * 0.15f) - 0.5f) * 2f * amount;
            float yaw = (Mathf.PerlinNoise(_seed + 10f, _time * 0.11f) - 0.5f) * 2f * amount;
            float roll = (Mathf.PerlinNoise(_seed + 20f, _time * 0.09f) - 0.5f) * amount;

            // Breathing makes the head rise a tiny bit; express it as a small pitch.
            pitch -= breathCycle * breathDepth * 1.5f;

            // --- weight shift (chest), the head leans back against it a little ---
            _shiftIn -= deltaTime;
            if (_shiftIn <= 0f)
            {
                _shiftIn = UnityEngine.Random.Range(ShiftMin, ShiftMax);
                _shiftTarget = _shiftTarget > 0f ? -UnityEngine.Random.Range(0.5f, 1f) : UnityEngine.Random.Range(0.5f, 1f);
            }
            _shift += ((Enabled ? _shiftTarget : 0f) - _shift) * Mathf.Clamp01(deltaTime * 0.6f);
            float chestAmount = Enabled ? Intensity * MaxChestAngle : 0f;
            float chestRoll = _shift * chestAmount + (Mathf.PerlinNoise(_seed + 30f, _time * 0.07f) - 0.5f) * chestAmount * 0.5f;
            float chestYaw = (Mathf.PerlinNoise(_seed + 40f, _time * 0.05f) - 0.5f) * chestAmount;
            float chestPitch = -breathCycle * breathDepth * 2f;   // the chest rises with each breath
            roll -= chestRoll * 0.5f;

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

            _lastOffset = ApplyOffset(_head, _lastOffset, Quaternion.Euler(pitch, yaw, roll));
            if (_chest != null) _lastChestOffset = ApplyOffset(_chest, _lastChestOffset, Quaternion.Euler(chestPitch, chestYaw, chestRoll));
            return finished;
        }

        /// <summary>Replaces last frame's offset on the controller with the new one; returns the offset now applied.</summary>
        private static Quaternion ApplyOffset(FreeControllerV3 controller, Quaternion last, Quaternion offset)
        {
            // Only meaningful while the controller drives rotation.
            if (controller.currentRotationState == FreeControllerV3.RotationState.Off) return Quaternion.identity;
            Transform t = controller.transform;
            Quaternion baseRot = t.rotation * Quaternion.Inverse(last);
            t.rotation = baseRot * offset;
            return offset;
        }

        /// <summary>A pose was just loaded: it set the controllers anew, so the old offsets are not removed again.</summary>
        public void Rebase()
        {
            _lastOffset = Quaternion.identity;
            _lastChestOffset = Quaternion.identity;
        }

        /// <summary>Removes any offset still applied (call on disable/destroy).</summary>
        public void RestoreNow()
        {
            if (_head != null) _head.transform.rotation = _head.transform.rotation * Quaternion.Inverse(_lastOffset);
            if (_chest != null) _chest.transform.rotation = _chest.transform.rotation * Quaternion.Inverse(_lastChestOffset);
            _lastOffset = Quaternion.identity;
            _lastChestOffset = Quaternion.identity;
            _gesture = null;
        }
    }
}
