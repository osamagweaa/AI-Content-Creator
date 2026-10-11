import contextlib
import importlib
import io
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class _FakeTqdm(contextlib.AbstractContextManager):
    def __init__(self, *args, **kwargs):
        pass

    def __exit__(self, *exc):
        return False

    def update(self, n):
        pass


class _FakeResponse(io.BytesIO):
    """urlopen() result: a byte stream with headers, optionally cut short."""

    def __init__(self, payload: bytes, content_length=None, fail_after=None):
        super().__init__(payload)
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self._fail_after = fail_after

    def read(self, size=-1):
        if self._fail_after is not None and self.tell() >= self._fail_after:
            raise ConnectionResetError("connection dropped")
        return super().read(size)


URL = "https://example.invalid/models/model.onnx"
PAYLOAD = os.urandom(3 * 1024 * 1024 + 17)


class ConditionalDownloadTests(unittest.TestCase):
    def setUp(self):
        # Import the real module even if another test stubbed it out, and
        # restore sys.modules afterwards.
        self._modules = patch.dict(sys.modules)
        self._modules.start()
        self.addCleanup(self._modules.stop)
        sys.modules.pop("modules.utilities", None)
        # The `modules` package imports cv2/numpy at init; stub them only when
        # absent so the test needs no heavy deps.
        stubs = {
            "cv2": types.SimpleNamespace(IMREAD_COLOR=1),
            "numpy": types.SimpleNamespace(uint8=object),
            "tqdm": types.SimpleNamespace(tqdm=_FakeTqdm),
        }
        for name, stub in stubs.items():
            try:
                importlib.import_module(name)
            except ImportError:
                sys.modules[name] = stub
        self.utilities = importlib.import_module("modules.utilities")
        # Another test may have left a non-context-manager tqdm stub behind.
        if not hasattr(self.utilities.tqdm, "__enter__"):
            self.utilities.tqdm = _FakeTqdm
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.target = os.path.join(self.tmp, "model.onnx")

    def _urlopen(self, response):
        return patch.object(
            self.utilities.urllib.request, "urlopen", return_value=response
        )

    def test_complete_download_lands_at_final_path(self):
        with self._urlopen(_FakeResponse(PAYLOAD, content_length=len(PAYLOAD))):
            self.utilities.conditional_download(self.tmp, [URL])
        with open(self.target, "rb") as f:
            self.assertEqual(f.read(), PAYLOAD)
        self.assertFalse(os.path.exists(self.target + ".part"))

    def test_interrupted_download_leaves_no_file(self):
        response = _FakeResponse(
            PAYLOAD, content_length=len(PAYLOAD), fail_after=1024 * 1024
        )
        with self._urlopen(response), self.assertRaises(ConnectionResetError):
            self.utilities.conditional_download(self.tmp, [URL])
        self.assertEqual(os.listdir(self.tmp), [])

    def test_short_body_is_rejected(self):
        response = _FakeResponse(PAYLOAD[:1000], content_length=len(PAYLOAD))
        with self._urlopen(response), self.assertRaises(IOError):
            self.utilities.conditional_download(self.tmp, [URL])
        self.assertEqual(os.listdir(self.tmp), [])

    def test_existing_file_is_not_redownloaded(self):
        with open(self.target, "wb") as f:
            f.write(b"existing")
        with self._urlopen(_FakeResponse(PAYLOAD)) as urlopen:
            self.utilities.conditional_download(self.tmp, [URL])
        urlopen.assert_not_called()

    def test_tls_verification_is_enabled(self):
        with self._urlopen(_FakeResponse(PAYLOAD)) as urlopen:
            self.utilities.conditional_download(self.tmp, [URL])
        ctx = urlopen.call_args.kwargs["context"]
        self.assertTrue(ctx.check_hostname)
        self.assertNotEqual(ctx.verify_mode, 0)  # ssl.CERT_NONE

    def test_progress_hook_reports_bytes(self):
        calls = []
        self.utilities.set_download_progress_hook(
            lambda name, done, total: calls.append((name, done, total))
        )
        self.addCleanup(self.utilities.set_download_progress_hook, None)
        with self._urlopen(_FakeResponse(PAYLOAD, content_length=len(PAYLOAD))):
            self.utilities.conditional_download(self.tmp, [URL])
        self.assertEqual(calls[0], ("model.onnx", 0, len(PAYLOAD)))
        self.assertEqual(calls[-1], ("model.onnx", len(PAYLOAD), len(PAYLOAD)))


if __name__ == "__main__":
    unittest.main()
