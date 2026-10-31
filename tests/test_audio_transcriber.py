# SPDX-License-Identifier: Apache-2.0
"""Test per il modulo di trascrizione audio (shared/audio_transcriber.py)."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from shared.audio_transcriber import is_stt_available, transcribe_audio


class AudioTranscriberTests(unittest.TestCase):
    def test_availability(self):
        self.assertTrue(is_stt_available())

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            transcribe_audio("percorso_inesistente_12345.ogg")

    @patch("subprocess.run")
    def test_transcribe_audio_mock(self, mock_run):
        # Simula esito positivo di ffmpeg e whisper
        def fake_run(cmd, *args, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if "--output_format" in cmd:
                # Trova output_dir
                out_dir_idx = cmd.index("--output_dir") + 1
                out_dir = Path(cmd[out_dir_idx])
                (out_dir / "audio_16k.json").write_text('{"text": "Buongiorno vorrei un preventivo"}', encoding="utf-8")
            return m

        mock_run.side_effect = fake_run

        test_file = Path("data/documents/test_dummy_audio.wav")
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"dummy")
        try:
            res = transcribe_audio(test_file)
            self.assertEqual(res, "Buongiorno vorrei un preventivo")
        finally:
            if test_file.exists():
                test_file.unlink()


if __name__ == "__main__":
    unittest.main()
