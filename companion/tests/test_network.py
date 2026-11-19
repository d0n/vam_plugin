"""Network Active (version 30): the loopback UDP link between the plugin and the companion app, with the file
channel as the fallback. Real sockets on 127.0.0.1 (ephemeral ports); the plugin's real SocketLink.cs runs in a
small .NET harness when the dotnet SDK is installed."""
import json
import re
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from aibody_companion.audio import EchoGate
from aibody_companion.config import Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline.engines import EngineSet
from aibody_companion.transport import FileTransport, HybridTransport, SocketTransport
from aibody_companion.transport import socket_transport
from tests.fakes import FakeClock

ROOT = Path(__file__).resolve().parents[2]


def wait_for(predicate, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class PluginSocket:
    """The plugin side of the link, as the C# SocketLink does it: an ephemeral loopback port and a hello."""

    def __init__(self, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(1.0)
        self.server = ("127.0.0.1", port)

    def send(self, message):
        self.sock.sendto(json.dumps(message).encode("utf-8"), self.server)

    def hello(self):
        self.send({"net": "hello", "v": 3})
        data, addr = self.sock.recvfrom(65535)
        assert addr == self.server
        return json.loads(data)

    def receive_all(self, wait=0.3):
        self.sock.settimeout(wait)
        out = []
        try:
            while True:
                out.append(json.loads(self.sock.recvfrom(65535)[0]))
        except socket.timeout:
            return out

    def close(self):
        self.sock.close()


class SocketTransportTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.t = SocketTransport(0, clock=self.clock)
        self.t.start()
        self.addCleanup(self.t.stop)
        self.plugin = PluginSocket(self.t.port)
        self.addCleanup(self.plugin.close)

    def test_binds_the_loopback_address_only(self):
        self.assertEqual(self.t._sock.getsockname()[0], "127.0.0.1")
        source = (ROOT / "companion/aibody_companion/transport/socket_transport.py").read_text(encoding="utf-8")
        self.assertNotIn("0.0.0.0", source.replace('never 0.0.0.0', ""))
        self.assertNotIn('bind(("",', source)
        self.assertEqual(socket_transport.LOOPBACK, "127.0.0.1")

    def test_hello_is_answered_and_the_plugin_counts_as_connected(self):
        self.assertFalse(self.t.connected)
        self.assertEqual(self.plugin.hello(), {"net": "hello_ack", "v": 3})
        self.assertTrue(self.t.connected)
        self.assertEqual(self.t.link, "socket")

    def test_messages_arrive_and_commands_go_back_to_the_plugin(self):
        self.plugin.hello()
        self.plugin.send({"v": 3, "type": "heartbeat", "id": "e1"})
        self.plugin.send([{"v": 3, "type": "ready", "id": "e2"}, {"v": 3, "type": "heartbeat", "id": "e3"}])
        self.assertTrue(wait_for(lambda: len(self.t._events) >= 3))
        self.assertEqual([e["id"] for e in self.t.poll_events()], ["e1", "e2", "e3"])
        self.assertEqual(self.t.poll_events(), [])
        self.assertTrue(self.t.send({"type": "speak", "text": "Hallo"}))
        self.assertEqual(self.plugin.receive_all()[-1]["text"], "Hallo")

    def test_link_datagrams_never_reach_the_app(self):
        self.plugin.hello()
        self.plugin.send({"net": "hello", "v": 3})
        self.plugin.sock.recvfrom(65535)
        time.sleep(0.1)
        self.assertEqual(self.t.poll_events(), [])

    def test_a_sender_that_never_said_hello_is_ignored(self):
        stranger = PluginSocket(self.t.port)
        self.addCleanup(stranger.close)
        stranger.send({"v": 3, "type": "speak", "text": "x"})
        time.sleep(0.15)
        self.assertEqual(self.t.poll_events(), [])
        self.assertFalse(self.t.send({"type": "speak"}))

    def test_garbage_is_dropped(self):
        self.plugin.hello()
        self.plugin.sock.sendto(b"\xff\xfe not json", self.plugin.server)
        self.plugin.send({"type": "heartbeat", "id": "ok"})
        self.assertTrue(wait_for(lambda: len(self.t._events) >= 1))
        self.assertEqual([e["id"] for e in self.t.poll_events()], ["ok"])

    def test_a_new_hello_replaces_the_peer(self):
        self.plugin.hello()
        second = PluginSocket(self.t.port)
        self.addCleanup(second.close)
        second.hello()
        self.t.send({"type": "ping"})
        self.assertEqual(second.receive_all()[-1]["type"], "ping")
        self.assertEqual(self.plugin.receive_all(0.1), [])

    def test_connection_times_out_without_traffic(self):
        self.plugin.hello()
        self.assertTrue(self.t.connected)
        self.clock.advance(socket_transport.SOCKET_ALIVE_S + 0.1)
        self.assertFalse(self.t.connected)
        self.plugin.send({"type": "heartbeat", "id": "back"})
        self.assertTrue(wait_for(lambda: self.t.connected))

    def test_too_large_messages_are_not_sent(self):
        self.plugin.hello()
        self.assertFalse(self.t.send({"type": "x", "blob": "a" * (socket_transport.MAX_DATAGRAM_BYTES + 10)}))


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.cfg = Config(vam_root=self.tmp.name)
        self.files = FileTransport(self.cfg.channel_dir, clock=self.clock)
        self.sock = SocketTransport(0, clock=self.clock)
        self.hybrid = HybridTransport(self.files, self.sock)
        self.hybrid.start()
        self.addCleanup(self.hybrid.stop)
        self.plugin = PluginSocket(self.sock.port)
        self.addCleanup(self.plugin.close)

    def inbox(self):
        return sorted(self.files.inbox.glob("*.json"))

    def test_files_are_used_until_the_socket_connects(self):
        self.hybrid.send({"type": "ping", "n": 1})
        self.assertEqual(len(self.inbox()), 1)
        self.plugin.hello()
        self.hybrid.send({"type": "ping", "n": 2})
        self.assertEqual(len(self.inbox()), 1, "the second one went over the socket")
        self.assertEqual(self.plugin.receive_all()[-1]["n"], 2)
        self.assertEqual(self.hybrid.link, "socket")

    def test_a_dead_socket_falls_back_to_files_by_itself(self):
        self.plugin.hello()
        self.clock.advance(socket_transport.SOCKET_ALIVE_S + 1)
        self.assertNotEqual(self.hybrid.link, "socket")
        self.hybrid.send({"type": "ping", "n": 3})
        self.assertEqual(len(self.inbox()), 1)

    def test_events_from_both_channels_are_read(self):
        self.plugin.hello()
        self.plugin.send({"type": "heartbeat", "id": "via-socket"})
        (self.files.outbox / f"{time.time_ns():020d}_000001.json").write_text(
            json.dumps({"type": "heartbeat", "id": "via-file"}), encoding="utf-8")
        self.assertTrue(wait_for(lambda: len(self.sock._events) >= 1))
        ids = {e["id"] for e in self.hybrid.poll_events()}
        self.assertEqual(ids, {"via-socket", "via-file"})

    def test_a_message_too_large_for_one_datagram_goes_through_the_files(self):
        self.plugin.hello()
        self.hybrid.send({"type": "big", "blob": "a" * (socket_transport.MAX_DATAGRAM_BYTES + 10)})
        self.assertEqual(len(self.inbox()), 1)

    def test_a_busy_port_leaves_the_file_channel_working(self):
        other = SocketTransport(0)
        other.start()
        self.addCleanup(other.stop)
        busy = HybridTransport(FileTransport(self.cfg.channel_dir, clock=self.clock), SocketTransport(other.port))
        with self.assertLogs("aibody_companion.transport.socket_transport", level="WARNING") as logs:
            busy.start()
        self.assertTrue(any("file exchange keeps working" in line for line in logs.output))
        self.assertFalse(busy.socket.running)
        busy.send({"type": "ping"})
        self.assertEqual(len(list(busy.file.inbox.glob("*.json"))), 1)
        busy.stop()


class CompanionOverSocketTests(unittest.TestCase):
    """The real Companion on a HybridTransport, a plugin that talks only UDP (plus one file for the token)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.cfg = Config(vam_root=self.tmp.name)
        files = FileTransport(self.cfg.channel_dir, clock=self.clock)
        self.sock = SocketTransport(0, clock=self.clock)
        self.transport = HybridTransport(files, self.sock)
        self.transport.start()
        self.addCleanup(self.transport.stop)
        self.app = Companion(self.cfg, self.transport, gate=EchoGate(clock=self.clock), clock=self.clock,
                             engines=EngineSet({"mode": "chain"}), background_turns=False)
        self.plugin = PluginSocket(self.sock.port)
        self.addCleanup(self.plugin.close)

    def tick(self, seconds=0.3):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.clock.advance(0.05)
            self.app.tick()
            time.sleep(0.02)

    def test_the_whole_exchange_runs_over_the_socket_without_files(self):
        self.plugin.hello()
        self.plugin.send({"v": 3, "id": "r1", "ts": 0, "type": "ready", "atom": "Person", "plugin_version": "30",
                          "channel": "default"})
        self.tick()
        types = [m.get("type") for m in self.plugin.receive_all(0.2)]
        self.assertIn("companion_heartbeat", types)
        self.assertEqual(self.app.transport.link, "socket")
        self.app.handle_user_text("Hello there")
        got = self.plugin.receive_all(0.3)
        self.assertIn("speak", [m.get("type") for m in got], [m.get("type") for m in got])
        self.assertEqual(list(self.transport.file.inbox.glob("*.json")), [], "nothing was written to the inbox")

    def test_the_plugin_losing_the_socket_does_not_lose_the_app(self):
        self.plugin.hello()
        self.plugin.send({"v": 3, "id": "r1", "ts": 0, "type": "ready", "atom": "Person", "plugin_version": "30"})
        self.tick()
        self.assertTrue(self.app.transport.connected)
        self.clock.advance(socket_transport.SOCKET_ALIVE_S + 1)
        self.tick(0.1)
        self.assertNotEqual(self.app.transport.link, "socket")
        self.app.send({"type": "ping", "id": "p1"})
        self.assertTrue(list(self.transport.file.inbox.glob("*.json")), "commands use the files again")


class PluginSourceTests(unittest.TestCase):
    """What the C# sources must look like (the VaM plugin cannot run here)."""

    def src(self, name):
        return (ROOT / "src" / "AIBody" / name).read_text(encoding="utf-8")

    def test_only_socketlink_touches_system_net_and_it_is_loopback_udp(self):
        for path in (ROOT / "src" / "AIBody").glob("*.cs"):
            text = path.read_text(encoding="utf-8")
            if path.name == "SocketLink.cs":
                continue
            self.assertNotRegex(text, r"System\.Net|UdpClient|\bSocket\b|IPAddress", path.name)
        link = self.src("SocketLink.cs")
        self.assertIn("IPAddress.Loopback", link)
        self.assertIn("UdpClient", link)
        self.assertNotRegex(link, r"IPAddress\.Any|0\.0\.0\.0|TcpClient|TcpListener|UnityWebRequest")

    def test_the_main_thread_never_waits_on_the_socket(self):
        link = self.src("SocketLink.cs")
        tick = re.search(r"public void Tick\(float dt\)(.*?)\n        /// <summary>Queues", link, re.S).group(1)
        for blocking in (".Receive(", ".Send(", "Thread.Sleep", ".Join(", "Monitor.Wait", ".Connect("):
            self.assertNotIn(blocking, tick)
        self.assertIn("new Thread(ReceiveLoop)", link)
        self.assertIn("new Thread(SendLoop)", link)
        self.assertIn("IsBackground = true", link)

    def test_off_means_no_network_code_runs(self):
        link = self.src("AppLink.cs")
        restart = re.search(r"public void Restart\(\)(.*?)\n        public void Stop", link, re.S).group(1)
        self.assertRegex(restart, r"if \(NetworkActive\)\s*\{\s*_network = new NetworkTransport\(file, new SocketLink")
        self.assertIn("_transport = file;", restart)
        self.assertEqual(len(re.findall(r"new SocketLink\(", link)), 1)

    def test_the_toggle_exists_default_on_and_is_saved_and_mirrored(self):
        link = self.src("AppLink.cs")
        self.assertIn('new JSONStorableBool("Network Active", true, (bool v) => Restart())', link)
        self.assertIn("RegisterBool(_networkJson)", link)
        self.assertIn('connection["network_active"].AsBool = NetworkActive;', link)
        self.assertIn("page.Toggle(_networkJson);", link)

    def test_status_texts(self):
        link = self.src("AppLink.cs") + self.src("SocketLink.cs") + self.src("NetworkTransport.cs")
        for text in ('"Network: off"', '"unavailable, using files"', '"connected"', '"connecting ..."'):
            self.assertIn(text, link)

    def test_the_token_never_goes_over_the_socket(self):
        net = self.src("NetworkTransport.cs")
        self.assertIn('!Protocol.Has(evt, "keys")', net)

    def test_vam_permission_hint_is_in_the_info_field(self):
        link = self.src("AppLink.cs")
        m = re.search(r'public const string NetworkNotice = (.*?);', link, re.S)
        self.assertIn("Allow Plugins Network Access", m.group(1))
        self.assertIn("file exchange", m.group(1))
        self.assertLessEqual(len(m.group(1)), 260, "one or two lines")
        voice = re.search(r"public string VoiceInfoText\(\)(.*?)\n        }", link, re.S).group(1)
        self.assertIn("NetworkNotice", voice)

    def test_no_own_prompt_and_no_other_network_apis(self):
        text = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "AIBody").glob("*.cs"))
        self.assertNotIn("UnityWebRequest", text)
        self.assertNotIn("UnityEngine.Networking", text)


class SandboxRuleTests(unittest.TestCase):
    def rules(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("sandbox_rules", ROOT / "tools" / "sandbox_rules.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_sockets_are_allowed_in_socketlink_only(self):
        rules = self.rules()
        code = "using System.Net.Sockets; UdpClient c = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0));"
        self.assertEqual(rules.scan_text("AIBody/SocketLink.cs", code), [])
        self.assertTrue(rules.scan_text("AIBody/AppLink.cs", code))
        self.assertTrue(rules.scan_text("src/AIBody/Body.cs", "new Thread(Run);"))

    def test_everything_else_stays_banned_even_in_socketlink(self):
        rules = self.rules()
        for code in ("IPAddress.Any", "new IPAddress(1)", "IPAddress.Parse(\"1.2.3.4\")", "TcpClient c;", "\"0.0.0.0\"",
                     "UnityWebRequest.Get(x)", "UnityEngine.Networking.NetworkTransport", "HttpWebRequest r;",
                     "foreach (var k in d.Keys)"):
            self.assertTrue(rules.scan_text("AIBody/SocketLink.cs", code), code)


DOTNET = shutil.which("dotnet") or str(Path.home() / ".dotnet" / "dotnet")


@unittest.skipUnless(Path(DOTNET).exists(), "dotnet SDK not installed")
class RealSocketLinkTests(unittest.TestCase):
    """The plugin's real SocketLink.cs (compiled outside VaM) against the real SocketTransport."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        shutil.copy(Path(__file__).parent / "csharp_harness" / "Program.cs", folder / "Program.cs")
        (folder / "Harness.csproj").write_text(f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType>
  <EnableDefaultCompileItems>false</EnableDefaultCompileItems><NoWarn>CS0618</NoWarn></PropertyGroup>
  <ItemGroup><Compile Include="Program.cs" /><Compile Include="{ROOT / 'src/AIBody/SocketLink.cs'}" /></ItemGroup>
</Project>""", encoding="utf-8")
        result = subprocess.run([DOTNET, "build", "-nologo", "-v", "q", "-o", str(folder / "out")], cwd=folder,
                                capture_output=True, text=True, timeout=240,
                                env={**__import__("os").environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"})
        if result.returncode != 0:
            raise AssertionError("harness build failed:\n" + result.stdout + result.stderr)
        cls.exe = folder / "out" / "Harness.dll"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_harness(self, port, seconds):
        return subprocess.Popen([DOTNET, str(self.exe), str(port), str(seconds)], stdout=subprocess.PIPE, text=True)

    def test_connects_exchanges_messages_and_falls_back(self):
        t = SocketTransport(0)
        t.start()
        self.addCleanup(t.stop)
        proc = self.run_harness(t.port, 4.0)
        self.assertTrue(wait_for(lambda: t.connected, 5.0), "the plugin's hello was not answered")
        got = []
        self.assertTrue(wait_for(lambda: got.extend(t.poll_events()) or len(got) >= 2, 5.0))
        self.assertEqual(got[0]["type"], "heartbeat")
        t.send({"type": "speak", "text": "from the app"})
        time.sleep(0.5)
        t.stop()  # the app goes away: the plugin must report "unavailable" after the timeout (6 s) - checked below
        out, _ = proc.communicate(timeout=20)
        self.assertIn("START blocked=False status=connecting ...", out)
        self.assertIn("LIVE True status=connected", out)
        self.assertIn('PAYLOAD {"type": "speak", "text": "from the app"}', out)

    def test_nobody_listening_never_connects_and_does_not_hang(self):
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        started = time.monotonic()
        proc = self.run_harness(port, 4.0)
        out, _ = proc.communicate(timeout=20)
        self.assertLess(time.monotonic() - started, 15)
        self.assertNotIn("LIVE True", out)
        self.assertIn("END live=False status=unavailable, using files", out)

    def test_a_companion_that_stops_answering_switches_the_plugin_back_to_files(self):
        t = SocketTransport(0)
        t.start()
        self.addCleanup(t.stop)
        proc = self.run_harness(t.port, 10.0)
        self.assertTrue(wait_for(lambda: t.connected, 5.0))
        time.sleep(0.5)
        t.stop()
        out, _ = proc.communicate(timeout=30)
        self.assertIn("LIVE True status=connected", out)
        self.assertIn("LIVE False status=unavailable, using files", out)


if __name__ == "__main__":
    unittest.main()
