# SPDX-License-Identifier: Apache-2.0
"""Client Voicebox: risoluzione profilo/motore e ciclo generate -> history -> audio, contro un server finto."""
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "moneyprinter"))
from shared import voicebox_client as vb  # noqa: E402
import mpt_bridge  # noqa: E402

PROFILES = [{"id": "p1", "name": "Albi ita", "language": "it", "default_engine": "chatterbox"},
            {"id": "p2", "name": "Albi", "language": "xx", "default_engine": None}]


class Fake(BaseHTTPRequestHandler):
    seen: list = []
    polls = 0

    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/profiles":
            return self._send(PROFILES)
        if self.path == "/history/g1":
            Fake.polls += 1
            return self._send({"status": "generating" if Fake.polls < 2 else "completed"})
        if self.path == "/history/g1/export-audio":
            return self._send(b"RIFFwav", "audio/wav")
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        Fake.seen.append((self.path, body))
        self._send({"id": "g1", "status": "generating"})


class VoiceboxClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        Fake.seen, Fake.polls = [], 0

    def test_parse_voice(self):
        self.assertEqual(vb.parse_voice("voicebox:Albi ita@qwen"), ("Albi ita", "qwen"))
        self.assertEqual(vb.parse_voice("voicebox:Albi ita"), ("Albi ita", None))
        self.assertEqual(vb.parse_voice("voicebox:a@b.it"), ("a@b.it", None))

    def test_synthesize_uses_profile_default_engine(self):
        self.assertEqual(vb.synthesize("voicebox:albi ITA", "ciao", base=self.base), b"RIFFwav")
        path, body = Fake.seen[0]
        self.assertEqual((path, body["profile_id"], body["engine"], body["language"]),
                         ("/generate", "p1", "chatterbox", "it"))

    def test_explicit_engine_and_unknown_language_fallback(self):
        vb.synthesize("voicebox:Albi@qwen", "hi", base=self.base)
        body = Fake.seen[0][1]
        self.assertEqual((body["engine"], body["language"]), ("qwen", "en"))

    def test_unknown_profile_lists_available(self):
        with self.assertRaisesRegex(vb.VoiceboxError, "Albi ita"):
            vb.synthesize("voicebox:nessuno", "x", base=self.base)

    def test_unreachable(self):
        with self.assertRaises(vb.VoiceboxError):
            vb.profiles(base="http://127.0.0.1:9")
        self.assertEqual(vb.voice_listing(base="http://127.0.0.1:9"), [])

    def test_bridge_maps_voice_for_mpt(self):
        self.assertEqual(mpt_bridge.mpt_voice("voicebox:Albi@qwen"), "kokoro:voicebox:Albi@qwen")
        self.assertEqual(mpt_bridge.mpt_voice("kokoro:if_sara"), "kokoro:if_sara")


if __name__ == "__main__":
    unittest.main()
