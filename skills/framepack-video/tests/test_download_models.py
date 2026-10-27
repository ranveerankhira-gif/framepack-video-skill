import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "download_models.py"
SPEC = importlib.util.spec_from_file_location("framepack_download_models", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def git_blob_digest(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


class DownloadModelsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="framepack-test-")
        self.root = Path(self.temporary.name) / "FramePack"
        (self.root / "webui").mkdir(parents=True)
        self.environment = mock.patch.dict(
            os.environ,
            {
                "FRAMEPACK_DOWNLOAD_APPROVED": "YES",
                "FRAMEPACK_ROOT": str(self.root),
                "FRAMEPACK_HF_ENDPOINT": "https://huggingface.example",
                "FRAMEPACK_MAX_DOWNLOAD_ATTEMPTS": "2",
            },
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.temporary.cleanup)
        self.sleep = mock.patch.object(MODULE.time, "sleep", return_value=None)
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def configure_manifest(self, data: bytes, algorithm: str = "sha256") -> None:
        repo = "owner/model"
        relative = "nested/model.bin"
        digest = hashlib.sha256(data).hexdigest() if algorithm == "sha256" else git_blob_digest(data)
        self.files = [(repo, "model", relative, len(data))]
        self.revisions = {repo: "a" * 40}
        self.identities = {(repo, relative): (algorithm, digest)}
        self.stack = mock.patch.multiple(
            MODULE,
            FILES=self.files,
            REVISIONS=self.revisions,
            IDENTITIES=self.identities,
        )
        self.stack.start()
        self.addCleanup(self.stack.stop)

    def destination(self) -> Path:
        return self.root / "webui" / "local_models" / "model" / "nested" / "model.bin"

    def test_unapproved_is_zero_write_and_zero_network(self):
        os.environ.pop("FRAMEPACK_DOWNLOAD_APPROVED", None)
        before = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        with mock.patch.object(MODULE, "curl_download") as download:
            self.assertEqual(MODULE.main(), 1)
        after = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        self.assertEqual(before, after)
        download.assert_not_called()

    def test_relative_root_is_rejected(self):
        os.environ["FRAMEPACK_ROOT"] = "relative-root"
        with self.assertRaisesRegex(RuntimeError, "absolute"):
            MODULE.load_runtime()

    def test_http_endpoint_and_credentials_are_rejected(self):
        for endpoint in ("http://example.test", "https://user:secret@example.test", "https://example.test/?x=1"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(RuntimeError):
                    MODULE.validate_endpoint(endpoint)

    def test_path_traversal_is_rejected(self):
        model_root = self.root / "webui" / "local_models"
        for candidate in ("../escape.bin", "..\\escape.bin", "C:payload.bin", "bad|name.bin"):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(RuntimeError, "Unsafe model path"):
                    MODULE.safe_destination(model_root, "model", candidate)

    def test_symlink_component_is_rejected(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        link = self.root / "webui" / "local_models"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symlink creation is unavailable: {error}")
        with self.assertRaisesRegex(RuntimeError, "Symlink or reparse point"):
            MODULE.safe_destination(link, "model", "file.bin")

    def test_mocked_windows_reparse_component_is_rejected(self):
        with mock.patch.object(
            MODULE,
            "is_reparse_point",
            side_effect=lambda path: path.name.casefold() == "webui",
        ):
            with self.assertRaisesRegex(RuntimeError, "Symlink or reparse point"):
                MODULE.load_runtime()

    def test_sha256_download_is_verified_and_atomically_finalized(self):
        data = b"verified sha256 payload"
        self.configure_manifest(data, "sha256")

        def fake_download(endpoint, repo, revision, relative, part):
            self.assertEqual(revision, "a" * 40)
            self.assertTrue(str(part).endswith(".part"))
            part.write_bytes(data)
            return 0

        with mock.patch.object(MODULE, "curl_download", side_effect=fake_download) as download:
            MODULE.run()
        self.assertEqual(self.destination().read_bytes(), data)
        self.assertFalse(self.destination().with_name("model.bin.part").exists())
        marker = json.loads((self.root / "framepack-model-download.complete").read_text(encoding="utf-8"))
        self.assertTrue(marker["modelsVerified"])
        self.assertEqual(marker["revisions"], self.revisions)
        self.assertRegex(marker["downloaderScriptSha256"], r"^[0-9a-f]{64}$")
        download.assert_called_once()

    def test_git_blob_sha1_download_is_verified(self):
        data = b"small git blob"
        self.configure_manifest(data, "git-blob-sha1")

        def fake_download(_endpoint, _repo, _revision, _relative, part):
            part.write_bytes(data)
            return 0

        with mock.patch.object(MODULE, "curl_download", side_effect=fake_download):
            MODULE.run()
        self.assertEqual(self.destination().read_bytes(), data)

    def test_corrupt_full_part_is_preserved(self):
        expected = b"expected payload"
        corrupt = b"corrupt!!payload"
        self.assertEqual(len(expected), len(corrupt))
        self.configure_manifest(expected)
        part = self.destination().with_name("model.bin.part")
        part.parent.mkdir(parents=True)
        part.write_bytes(corrupt)
        with mock.patch.object(MODULE, "curl_download") as download:
            with self.assertRaisesRegex(RuntimeError, "preserved"):
                MODULE.run()
        self.assertEqual(part.read_bytes(), corrupt)
        self.assertFalse(self.destination().exists())
        download.assert_not_called()

    def test_existing_different_final_is_not_overwritten(self):
        expected = b"expected payload"
        conflict = b"conflict payload"
        self.assertEqual(len(expected), len(conflict))
        self.configure_manifest(expected)
        self.destination().parent.mkdir(parents=True)
        self.destination().write_bytes(conflict)
        with mock.patch.object(MODULE, "curl_download") as download:
            with self.assertRaisesRegex(RuntimeError, "not overwritten"):
                MODULE.run()
        self.assertEqual(self.destination().read_bytes(), conflict)
        download.assert_not_called()

    def test_partial_file_resumes_and_attempts_are_bounded(self):
        data = b"resume me"
        self.configure_manifest(data)
        part = self.destination().with_name("model.bin.part")
        part.parent.mkdir(parents=True)
        part.write_bytes(data[:3])
        sizes = []

        def failed_download(_endpoint, _repo, _revision, _relative, target):
            sizes.append(target.stat().st_size)
            return 7

        with mock.patch.object(MODULE, "curl_download", side_effect=failed_download) as download:
            with self.assertRaisesRegex(RuntimeError, "attempts exhausted"):
                MODULE.run()
        self.assertEqual(download.call_count, 2)
        self.assertEqual(sizes, [3, 3])
        self.assertEqual(part.read_bytes(), data[:3])

    def test_existing_lock_blocks_second_downloader(self):
        self.configure_manifest(b"payload")
        lock = self.root / "framepack-model-download.lock"
        lock.write_text("{}", encoding="utf-8")
        with mock.patch.object(MODULE, "curl_download") as download:
            with self.assertRaisesRegex(RuntimeError, "lock already exists"):
                MODULE.run()
        download.assert_not_called()
        self.assertTrue(lock.exists())

    def test_repeated_run_is_idempotent_and_does_not_redownload(self):
        data = b"idempotent payload"
        self.configure_manifest(data)

        def fake_download(_endpoint, _repo, _revision, _relative, part):
            part.write_bytes(data)
            return 0

        with mock.patch.object(MODULE, "curl_download", side_effect=fake_download) as first:
            MODULE.run()
        with mock.patch.object(MODULE, "curl_download") as second:
            MODULE.run()
        first.assert_called_once()
        second.assert_not_called()
        self.assertEqual(self.destination().read_bytes(), data)

    def test_curl_uses_https_only_flags_and_pinned_revision(self):
        destination = self.root / "webui" / "file.part"
        with mock.patch.object(MODULE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as runner:
            MODULE.curl_download(
                "https://huggingface.example",
                "owner/model",
                "b" * 40,
                "dir/file.bin",
                destination,
            )
        command = runner.call_args.args[0]
        self.assertIn("=https", command)
        self.assertIn("/resolve/" + "b" * 40 + "/", command[-1])
        self.assertNotIn("/resolve/main/", command[-1])
        self.assertFalse(runner.call_args.kwargs["shell"])


if __name__ == "__main__":
    unittest.main()
