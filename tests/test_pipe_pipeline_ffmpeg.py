"""The in-memory pipe pipeline must resolve ffmpeg via utilities.get_ffmpeg.

Frozen desktop builds ship ffmpeg inside the bundle; a bare 'ffmpeg' only
works when it happens to be on PATH.
"""
import importlib
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PipePipelineFfmpegTests(unittest.TestCase):
    def test_reader_and_writer_use_resolved_ffmpeg(self):
        stubs = {
            "cv2": sys.modules.get("cv2") or types.SimpleNamespace(IMREAD_COLOR=1),
            "numpy": types.SimpleNamespace(),
            "tqdm": types.SimpleNamespace(tqdm=object),
            "modules.face_analyser": types.SimpleNamespace(get_one_face=None),
            "modules.utilities": types.SimpleNamespace(
                get_ffmpeg=lambda: "/bundle/ffmpeg-bin/ffmpeg"
            ),
        }
        commands = []

        def fake_popen(cmd, **_kwargs):
            commands.append(cmd)
            if len(commands) == 2:
                raise OSError("stop after both commands are built")
            return types.SimpleNamespace(kill=lambda: None)

        with patch.dict(sys.modules, stubs):
            sys.modules.pop("modules.processors.frame.core", None)
            core = importlib.import_module("modules.processors.frame.core")
            try:
                with patch.object(core.subprocess, "Popen", side_effect=fake_popen):
                    ok = core._run_pipe_pipeline(
                        "in.mp4", "out.mp4", 30.0, None, [], 16, 16,
                        16 * 16 * 3, 1, "libx264", [],
                    )
            finally:
                sys.modules.pop("modules.processors.frame.core", None)

        self.assertFalse(ok)
        self.assertEqual([cmd[0] for cmd in commands], ["/bundle/ffmpeg-bin/ffmpeg"] * 2)


if __name__ == "__main__":
    unittest.main()
