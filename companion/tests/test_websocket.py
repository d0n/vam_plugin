"""The standard-library WebSocket client against a local fake server."""
from __future__ import annotations

import json
import unittest

from aibody_companion.pipeline.websocket import OP_CONT, OP_PING, OP_TEXT, WebSocket, WebSocketError
from tests.fake_ws import FakeRealtimeServer


class WebSocketClientTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeRealtimeServer()

    def tearDown(self):
        self.server.stop()

    def test_handshake_headers_and_masked_text_frames(self):
        ws = WebSocket.connect(self.server.url, {"Authorization": "Bearer test-key"}, timeout=2)
        self.assertTrue(self.server.wait_connections(1))
        conn = self.server.conn
        self.assertEqual(conn.headers.get("authorization"), "Bearer test-key")
        self.assertEqual(conn.path, "/v1/realtime?model=grok-voice-latest")
        first = json.loads(ws.recv(timeout=2))
        self.assertEqual(first["type"], "conversation.created")
        ws.send_text(json.dumps({"type": "session.update", "session": {"voice": "eve"}}))
        self.assertTrue(self.server.wait_type("session.update"))
        self.assertTrue(conn.masked_ok)
        types = []
        while True:
            msg = ws.recv(timeout=1)
            if msg is None:
                break
            types.append(json.loads(msg)["type"])
            if types[-1] == "session.updated":
                break
        self.assertIn("session.updated", types)
        ws.close()

    def test_large_message_fragments_and_ping(self):
        ws = WebSocket.connect(self.server.url, timeout=2)
        self.assertTrue(self.server.wait_connections(1))
        ws.recv(timeout=1)
        ws.recv(timeout=1)
        big = "x" * 70000  # 64-bit length form
        self.server.conn.send({"type": "big", "data": big})
        self.assertEqual(len(json.loads(ws.recv(timeout=2))["data"]), 70000)
        self.server.conn.send_raw(OP_PING, b"hi")
        self.server.conn.send_raw(OP_TEXT, b'{"a":', fin=False)
        self.server.conn.send_raw(OP_CONT, b'1}', fin=True)
        self.assertEqual(json.loads(ws.recv(timeout=2)), {"a": 1})
        ws.close()

    def test_recv_timeout_returns_none(self):
        ws = WebSocket.connect(self.server.url, timeout=2)
        ws.recv(timeout=1)
        ws.recv(timeout=1)
        self.assertIsNone(ws.recv(timeout=0.05))
        ws.close()

    def test_refused_handshake_reports_status(self):
        refusing = FakeRealtimeServer(refuse_status=401)
        try:
            with self.assertRaises(WebSocketError) as ctx:
                WebSocket.connect(refusing.url, timeout=2)
            self.assertEqual(ctx.exception.status, 401)
        finally:
            refusing.stop()

    def test_dropped_connection_raises(self):
        ws = WebSocket.connect(self.server.url, timeout=2)
        self.assertTrue(self.server.wait_connections(1))
        ws.recv(timeout=1)
        ws.recv(timeout=1)
        self.server.conn.drop()
        with self.assertRaises(WebSocketError):
            for _ in range(5):
                ws.recv(timeout=1)
        self.assertTrue(ws.closed)

    def test_unreachable_host(self):
        self.server.stop()
        with self.assertRaises(WebSocketError):
            WebSocket.connect(self.server.url, timeout=1)


if __name__ == "__main__":
    unittest.main()
