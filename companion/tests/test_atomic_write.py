"""The plugin starts loading a WAV when `speak` arrives, so: WAV complete under its final name FIRST
(temp name in the same folder, flush + fsync, close, os.replace), then the speak command, itself
written atomically. No sleeping, no guessed wait times: the files' existence is the signal."""
import json
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

from aibody_companion import atomicfile
from aibody_companion.config import Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline import EchoLlm, NullStt, ToneTts
from aibody_companion.pipeline import tts as tts_module
from aibody_companion.transport import FileTransport

ROOT = Path(__file__).resolve().parents[2]


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "audio"

    def tearDown(self):
        self.tmp.cleanup()

    def test_order_is_temp_write_fsync_close_replace(self):
        final = self.dir / "a.wav"
        events = []
        real_replace, real_fsync = os.replace, os.fsync

        def replace(src, dst):
            events.append(("replace", Path(src).parent == final.parent, final.exists(), Path(src).read_bytes()))
            real_replace(src, dst)

        def fsync(fd):
            events.append(("fsync",))
            real_fsync(fd)

        with mock.patch("os.replace", replace), mock.patch("os.fsync", fsync):
            atomicfile.atomic_write_bytes(final, b"RIFFdata")
        self.assertEqual(events[0], ("fsync",), "bytes are on disk before the rename")
        kind, same_folder, existed, content = events[1]
        self.assertEqual(kind, "replace")
        self.assertTrue(same_folder, "temp file in the SAME folder (rename stays on one volume)")
        self.assertFalse(existed, "the final name does not exist before the replace")
        self.assertEqual(content, b"RIFFdata", "the temp file was complete when it was renamed")
        self.assertEqual(final.read_bytes(), b"RIFFdata")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["a.wav"], "no temp file left")

    def test_speech_files_skip_fsync_but_stay_atomic(self):
        """Version 36 (latency): WAVs and command files need the rename, not the fsync (crash safety only)."""
        final = self.dir / "s.wav"
        with mock.patch("os.fsync") as fsync:
            atomicfile.atomic_write_bytes(final, b"RIFFx", durable=False)
            tts_module.write_pcm_wav(bytes(200), 16000, self.dir / "p.wav")
        fsync.assert_not_called()
        self.assertEqual(final.read_bytes(), b"RIFFx")
        self.assertEqual(sorted(p.suffix for p in self.dir.iterdir()), [".wav", ".wav"], "no temp file left")
        ft = (ROOT / "companion/aibody_companion/transport/file_transport.py").read_text(encoding="utf-8")
        self.assertIn("durable=False", ft)

    def test_failure_leaves_neither_final_nor_temp_file(self):
        final = self.dir / "b.wav"
        with mock.patch("os.replace", side_effect=OSError("disk")), self.assertRaises(OSError):
            atomicfile.atomic_write_bytes(final, b"x")
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_temp_names_never_look_like_wav_or_json(self):
        for name in ("u.wav", "0001_000001.json"):
            tmp = atomicfile._temp_path(self.dir / name)
            self.assertTrue(tmp.name.endswith(".part"), tmp.name)
            self.assertEqual(tmp.parent, self.dir)

    def test_copy_is_atomic_too(self):
        src = Path(self.tmp.name) / "src.wav"
        src.write_bytes(b"RIFF1234")
        final = self.dir / "c.wav"
        with mock.patch("os.fsync") as fsync:
            atomicfile.atomic_copy(src, final)
        fsync.assert_called()
        self.assertEqual(final.read_bytes(), b"RIFF1234")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["c.wav"])

    def test_every_wav_writer_goes_through_the_atomic_helper(self):
        pcm = bytes(2 * 1000)
        with mock.patch.object(tts_module, "atomic_write_bytes", wraps=atomicfile.atomic_write_bytes) as w:
            tts_module.write_pcm_wav(pcm, 16000, self.dir / "p.wav")
            tts_module.write_audio(tts_module.pcm_to_wav_bytes(pcm, 16000), 16000, self.dir / "q.wav")
            ToneTts().synthesize("Hallo", self.dir / "t.wav")
        self.assertEqual(w.call_count, 3)
        for name in ("p.wav", "q.wav", "t.wav"):
            with wave.open(str(self.dir / name)) as f:
                self.assertGreater(f.getnframes(), 0)
        self.assertEqual(sorted(p.suffix for p in self.dir.iterdir()), [".wav"] * 3)
        text = (ROOT / "companion/aibody_companion/pipeline/tts.py").read_text(encoding="utf-8")
        self.assertNotIn('wave.open(str(out_path), "wb")', text, "ToneTts used to write in place")
        self.assertNotIn(".replace(out_path)", text)
        orch = (ROOT / "companion/aibody_companion/orchestrator.py").read_text(encoding="utf-8")
        self.assertIn("atomic_copy(path, new_path, durable=False)", orch)
        self.assertNotIn("shutil.copyfile", orch)


class OrderingTests(unittest.TestCase):
    """At the moment a speak command is written, its WAV is complete, valid and the only trace of it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(vam_root=self.tmp.name, channel="Person")
        self.checked = []
        test = self

        class CheckingTransport(FileTransport):
            def send(self, command):
                if command.get("type") == "speak":
                    path = Path(test.tmp.name) / command["audio"]
                    test.assertTrue(path.is_file(), f"WAV must exist before its speak command: {path}")
                    size = path.stat().st_size
                    with wave.open(str(path)) as w:
                        data = w.getnframes() * w.getsampwidth() * w.getnchannels()
                    test.assertEqual(size, 44 + data, "file size matches the RIFF header: complete, not half written")
                    test.assertEqual([p.name for p in path.parent.glob("*.part")], [], "no temp file left behind")
                    test.checked.append(command["audio"])
                super().send(command)

        self.t = CheckingTransport(self.cfg.channel_dir)
        self.t.start()
        self.c = Companion(self.cfg, self.t, NullStt(), EchoLlm(), ToneTts())

    def tearDown(self):
        self.tmp.cleanup()

    def test_say_test_tone_and_resend_write_the_wav_before_the_command(self):
        self.c.say("Hallo Welt")
        self.c.play_test_tone()
        self.assertEqual(len(self.checked), 2)
        # audio_failed: the copy into the other folder is complete before the second speak
        uid = next(iter(self.c._recent_speech))
        self.c._audio_failed(uid, "boom")
        self.assertGreaterEqual(len(self.checked), 3)

    def test_speak_command_file_appears_complete(self):
        self.c.say("Hallo")
        files = sorted(self.t.inbox.glob("*.json"))
        self.assertTrue(files)
        for f in files:
            self.assertEqual(json.loads(f.read_text(encoding="utf-8"))["v"], 3)
        self.assertEqual(list(self.t.inbox.glob("*.part")), [])
        self.assertEqual(list(self.t.inbox.glob("*.tmp")), [])


class PluginWaitsForTheFileTests(unittest.TestCase):
    """SpeechPlayer: a file that is not visible yet stays queued and is re-checked from Update."""

    def setUp(self):
        self.src = (ROOT / "src/AIBody/SpeechPlayer.cs").read_text(encoding="utf-8")

    def test_missing_file_is_polled_not_failed_at_once(self):
        enqueue = self.method("public string Enqueue(string id, string path, bool interrupt)")
        self.assertIn("WaitingForFile = missing", enqueue)
        self.assertNotIn('return "audio file not found', enqueue, "no instant failure any more")
        self.assertNotIn("Audio file not found", enqueue)
        update = self.method("public void Update(float deltaTime)")
        self.assertIn("FileReady(u, deltaTime)", update)
        ready = self.method("private bool FileReady(Utterance u, float deltaTime)")
        for part in ("u.CheckTimer >= FileCheckInterval", "FileManagerSecure.FileExists(u.Path)",
                     "u.WaitTime > StartTimeout", "after waiting", "--vam-root"):
            self.assertIn(part, ready)

    def test_no_sleeping_or_threads(self):
        for banned in ("Thread.Sleep", "System.Threading", "WaitForSeconds", "StartCoroutine", "Invoke("):
            self.assertNotIn(banned, self.src)

    def method(self, signature):
        start = self.src.index(signature)
        i = self.src.index("{", start)
        depth = 0
        for j in range(i, len(self.src)):
            depth += (self.src[j] == "{") - (self.src[j] == "}")
            if depth == 0:
                return self.src[start:j + 1]
        raise AssertionError(signature)


if __name__ == "__main__":
    unittest.main()
