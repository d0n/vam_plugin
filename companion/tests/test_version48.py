"""Version 48 (Don, 22.11.2026 12:58-12:59): "Full volume distance (m)" back, EasyMoan's way - only minDistance (and
maxDistance 500), only from Body.Update, only when changed and idle, default 3 m; README/T77 output device note; the
companion logs the Windows default output device once; release notes in English (Don 13:03). Released as v48 (22.11.2026)."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from unittest import TestCase, mock

from aibody_companion import __version__, settings_file
from aibody_companion import setup as first_start
from aibody_companion.audio import capture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def method(src: str, signature: str) -> str:
    """The body of one C# member: from its signature to the matching closing brace."""
    start = src.index(signature)
    i = src.index("{", start)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    raise AssertionError(signature)


class VersionTests(TestCase):
    def test_version_48_is_historical(self):
        """Historical: version 48 sources are gone after the v49 bump; consistency is test_version49."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version49.py").is_file())


class DistanceTests(TestCase):
    def test_defaults_3_m(self):
        sp = source("SpeechPlayer.cs")
        self.assertIn("DefaultFullVolumeDistance = 3f", sp)
        self.assertIn("MinFullVolumeDistance = 0.3f", sp)
        self.assertIn("MaxFullVolumeDistance = 10f", sp)
        self.assertIn("FarDistance = 500f", sp)
        self.assertEqual(settings_file.DEFAULTS["body"]["full_volume_distance"], 3.0)
        self.assertEqual(settings_file.RANGES[("body", "full_volume_distance")], (0.3, 10.0))
        self.assertNotIn(("body", "full_volume_distance"), settings_file.LEGACY_KEYS)
        self.assertEqual(json.loads((ROOT / "examples" / "config.json").read_text(encoding="utf-8"))["body"]["full_volume_distance"], 3.0)
        schema = json.loads((ROOT / "protocol" / "schema" / "config.schema.json").read_text(encoding="utf-8"))
        self.assertIn("full_volume_distance", json.dumps(schema))

    def test_playback_path_writes_no_params(self):
        sp = source("SpeechPlayer.cs")
        for sig in ("private bool Resolve()", "public float Volume", "private void Play(Utterance u)",
                    "private void PlayNow(Utterance u)", "public void Update(float deltaTime)"):
            body = method(sp, sig)
            self.assertNotIn("SetFloatParamValue", body, sig)
            self.assertNotIn("UpdateDistance", body, sig)
            for p in ('"minDistance"', '"maxDistance"', '"volume"'):
                self.assertNotIn(p, body, sig)
        # the only writes in the whole player: minDistance and maxDistance, never the volume param
        writes = re.findall(r'SetFloatParamValue\("(\w+)"', sp)
        self.assertEqual(set(writes), {"minDistance", "maxDistance"})
        self.assertNotIn('SetFloatParamValue("volume"', sp)

    def test_update_distance_is_deferred_while_speaking(self):
        sp = source("SpeechPlayer.cs")
        self.assertIn("public bool Idle { get { return _current == null && _queue.Count == 0; } }", sp)
        body = method(sp, "public void UpdateDistance(float wanted)")
        order = [body.index(x) for x in ("if (_storable == null || _audio == null) return;",
                                         "if (!DistancePending(d)) return;", "if (!Idle) return;",
                                         "_appliedDistance = d;", 'SetFloatParamValue("minDistance", d)')]
        self.assertEqual(order, sorted(order))
        self.assertIn('if (far != null && far.val < FarDistance) _storable.SetFloatParamValue("maxDistance", FarDistance);', body)
        restore = method(sp, "public void RestoreDistance()")
        self.assertIn("_savedMinDistance", restore)
        self.assertIn("_appliedDistance = -1f;", restore)

    def test_body_applies_only_from_update_and_restores_on_removal(self):
        body = source("Body.cs")
        self.assertEqual(body.count("UpdateDistance("), 1)
        self.assertIn("UpdateDistance(", method(body, "public void Update("))
        self.assertIn('new JSONStorableFloat("Full volume distance (m)", SpeechPlayer.DefaultFullVolumeDistance,', body)
        self.assertIn("page.Slider(_distanceJson);", body)
        self.assertIn('body["full_volume_distance"].AsFloat = _distanceJson.val;', body)
        self.assertIn('Protocol.GetFloat(body, "full_volume_distance", _distanceJson.val)', body)
        self.assertIn("_speech.RestoreDistance();", method(body, "public void Restore()"))
        self.assertIn("<b>Full volume distance (m)</b>", source("AppLink.cs"))

    def test_scene_keeps_0_04(self):
        scene = (ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8")
        self.assertIn('"minDistance": "0.04"', scene)


class OutputDeviceLogTests(TestCase):
    def test_default_output_device_name(self):
        fake = mock.Mock()
        fake.query_devices.return_value = {"name": "Headset (Oculus Virtual Audio Device)"}
        with mock.patch.object(capture, "_sounddevice", return_value=fake):
            self.assertEqual(capture.default_output_device(), "Headset (Oculus Virtual Audio Device)")
        fake.query_devices.assert_called_once_with(kind="output")

    def test_never_raises(self):
        fake = mock.Mock()
        fake.query_devices.side_effect = RuntimeError("no device")
        with mock.patch.object(capture, "_sounddevice", return_value=fake):
            self.assertIn("unknown", capture.default_output_device())
        with mock.patch.object(capture, "_sounddevice", return_value=None):
            self.assertIn("unknown", capture.default_output_device())

    def test_cli_logs_it_once(self):
        cli = (ROOT / "companion" / "aibody_companion" / "cli.py").read_text(encoding="utf-8")
        self.assertEqual(cli.count("Windows default output device: %s"), 1)
