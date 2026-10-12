"""model_downloader must download through the atomic utilities.conditional_download."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_TESTS_DIR, os.path.dirname(_TESTS_DIR)]

from test_download_ssl_verification import (  # noqa: E402
    _FakeResponse,
    _load_model_downloader,
    _load_utilities,
)


class _TruncatedResponse(_FakeResponse):
    """Advertises more bytes than it delivers, like a dropped connection."""

    def __init__(self, payload):
        super().__init__(payload)
        self.headers._values["Content-Length"] = str(len(payload) + 10)


class AtomicModelDownloadTests(unittest.TestCase):
    def setUp(self):
        _load_utilities()
        self.md = _load_model_downloader()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = os.path.join(self.tmp.name, "x.onnx")

    def _download(self, response, size=None):
        with patch("urllib.request.urlopen", return_value=response):
            return self.md._download("x.onnx", "https://example.com/x.onnx", self.target, size)

    def test_goes_through_conditional_download(self):
        with patch("modules.utilities.conditional_download") as cd:
            cd.side_effect = lambda d, urls: open(self.target, "wb").write(b"abc")
            self.assertTrue(self.md._download("x.onnx", "https://example.com/x.onnx", self.target, None))
        cd.assert_called_once_with(self.tmp.name, ["https://example.com/x.onnx"])

    def test_truncated_download_leaves_nothing_behind(self):
        self.assertFalse(self._download(_TruncatedResponse(b"partial")))
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_size_mismatch_is_discarded(self):
        self.assertFalse(self._download(_FakeResponse(b"wrong-file"), size=999))
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_expected_size_is_kept(self):
        self.assertTrue(self._download(_FakeResponse(b"model"), size=5))
        self.assertEqual(os.listdir(self.tmp.name), ["x.onnx"])

    def test_empty_file_is_replaced(self):
        open(self.target, "wb").close()
        self.assertTrue(self._download(_FakeResponse(b"model")))
        self.assertEqual(os.path.getsize(self.target), 5)


if __name__ == "__main__":
    unittest.main()
