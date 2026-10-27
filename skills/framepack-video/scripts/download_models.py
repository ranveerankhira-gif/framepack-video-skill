import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlparse

APPROVAL_ENV = "FRAMEPACK_DOWNLOAD_APPROVED"
DEFAULT_ENDPOINT = "https://huggingface.co"
DEFAULT_MAX_ATTEMPTS = 3
REPARSE_POINT_ATTRIBUTE = 0x400

FILES = [
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "text_encoder/config.json", 766),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "text_encoder/model-00001-of-00004.safetensors", 4977222384),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "text_encoder/model-00002-of-00004.safetensors", 4999801992),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "text_encoder/model-00003-of-00004.safetensors", 4915915480),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "text_encoder/model-00004-of-00004.safetensors", 117465520),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "text_encoder/model.safetensors.index.json", 22152),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "text_encoder_2/config.json", 646),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "text_encoder_2/model.safetensors", 246144152),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "tokenizer/special_tokens_map.json", 577),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "tokenizer/tokenizer.json", 17210098),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "tokenizer/tokenizer_config.json", 51729),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "tokenizer_2/merges.txt", 524619),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "tokenizer_2/special_tokens_map.json", 588),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "tokenizer_2/tokenizer_config.json", 736),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "tokenizer_2/vocab.json", 1059962),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "vae/config.json", 718),
    ("hunyuanvideo-community/HunyuanVideo", "HunyuanVideo", "vae/diffusion_pytorch_model.safetensors", 985943868),
    ("lllyasviel/flux_redux_bfl", "flux_redux_bfl", "feature_extractor/preprocessor_config.json", 394),
    ("lllyasviel/flux_redux_bfl", "flux_redux_bfl", "image_encoder/config.json", 585),
    ("lllyasviel/flux_redux_bfl", "flux_redux_bfl", "image_encoder/model.safetensors", 856506120),
    ("lllyasviel/FramePackI2V_HY", "FramePackI2V_HY", "config.json", 658),
    ("lllyasviel/FramePackI2V_HY", "FramePackI2V_HY", "diffusion_pytorch_model-00001-of-00003.safetensors", 9972080992),
    ("lllyasviel/FramePackI2V_HY", "FramePackI2V_HY", "diffusion_pytorch_model-00002-of-00003.safetensors", 9987115584),
    ("lllyasviel/FramePackI2V_HY", "FramePackI2V_HY", "diffusion_pytorch_model-00003-of-00003.safetensors", 5789584816),
    ("lllyasviel/FramePackI2V_HY", "FramePackI2V_HY", "diffusion_pytorch_model.safetensors.index.json", 134006),
]

REVISIONS = {
    "hunyuanvideo-community/HunyuanVideo": "e8c2aaa66fe3742a32c11a6766aecbf07c56e773",
    "lllyasviel/flux_redux_bfl": "45b801affc54ff2af4e5daf1b282e0921901db87",
    "lllyasviel/FramePackI2V_HY": "86cef4396041b6002c957852daac4c91aaa47c79",
}

IDENTITIES = {
    ("hunyuanvideo-community/HunyuanVideo", "text_encoder/config.json"): ("git-blob-sha1", "f5f2205251eb0b863c5b0f9a60cd9fad069c5872"),
    ("hunyuanvideo-community/HunyuanVideo", "text_encoder/model-00001-of-00004.safetensors"): ("sha256", "f5ad57d3eda300a3195bc9c0bb36ab76ebe88831f128e9851e63440aff4a6741"),
    ("hunyuanvideo-community/HunyuanVideo", "text_encoder/model-00002-of-00004.safetensors"): ("sha256", "54accb98811931fca7598da4f7239b03b912eaa2bd5fe639f2da00923374f4a0"),
    ("hunyuanvideo-community/HunyuanVideo", "text_encoder/model-00003-of-00004.safetensors"): ("sha256", "d67c77f57cab4c9bf7f4420c256aed684c8ac7b49c6ab72cff9924e9513db9f1"),
    ("hunyuanvideo-community/HunyuanVideo", "text_encoder/model-00004-of-00004.safetensors"): ("sha256", "c93f133c65ab1aeaa9ed1e998901a306636375b2f57fa53cd279241147a9a0e9"),
    ("hunyuanvideo-community/HunyuanVideo", "text_encoder/model.safetensors.index.json"): ("git-blob-sha1", "b6e7a9e010002205834fd4f2808ca042bad4a246"),
    ("hunyuanvideo-community/HunyuanVideo", "text_encoder_2/config.json"): ("git-blob-sha1", "715167338723844a8b46281e6dedaf9e2000f771"),
    ("hunyuanvideo-community/HunyuanVideo", "text_encoder_2/model.safetensors"): ("sha256", "660c6f5b1abae9dc498ac2d21e1347d2abdb0cf6c0c0c8576cd796491d9a6cdd"),
    ("hunyuanvideo-community/HunyuanVideo", "tokenizer/special_tokens_map.json"): ("git-blob-sha1", "7c6fa7065265909bd500cafb38cc939b81b1b018"),
    ("hunyuanvideo-community/HunyuanVideo", "tokenizer/tokenizer.json"): ("sha256", "d2c593db4aa75b17a42c1f74d7cc38e257eaeed222e6a52674c65544165dcbaa"),
    ("hunyuanvideo-community/HunyuanVideo", "tokenizer/tokenizer_config.json"): ("git-blob-sha1", "747d2159aaebc628e8105b91c2ab77d50a289f17"),
    ("hunyuanvideo-community/HunyuanVideo", "tokenizer_2/merges.txt"): ("git-blob-sha1", "76e821f1b6f0a9709293c3b6b51ed90980b3166b"),
    ("hunyuanvideo-community/HunyuanVideo", "tokenizer_2/special_tokens_map.json"): ("git-blob-sha1", "cf0682d6de72c1547f41b4f6d7c59f62deffef94"),
    ("hunyuanvideo-community/HunyuanVideo", "tokenizer_2/tokenizer_config.json"): ("git-blob-sha1", "22f91ac3aeb401be0a10d294e00bb1d6293bc4c5"),
    ("hunyuanvideo-community/HunyuanVideo", "tokenizer_2/vocab.json"): ("git-blob-sha1", "469be27c5c010538f845f518c4f5e8574c78f7c8"),
    ("hunyuanvideo-community/HunyuanVideo", "vae/config.json"): ("git-blob-sha1", "b70acd51d20aeee27af7a81cea7d68f5288b8f4b"),
    ("hunyuanvideo-community/HunyuanVideo", "vae/diffusion_pytorch_model.safetensors"): ("sha256", "7c68a6295f9034a88225fbafb1f3258291a08d57a1fdb938233fa57b1b8f4883"),
    ("lllyasviel/flux_redux_bfl", "feature_extractor/preprocessor_config.json"): ("git-blob-sha1", "0c32f3fbba3be05b4cb9f590c2a9e5e38f58b0ea"),
    ("lllyasviel/flux_redux_bfl", "image_encoder/config.json"): ("git-blob-sha1", "7eb7dd280c41ef511994bfe7e9272c6204e3db67"),
    ("lllyasviel/flux_redux_bfl", "image_encoder/model.safetensors"): ("sha256", "d769e3a32a6a9bac72d4d93b989e44491f71b50f02bfa14cd9187758d4a68ff1"),
    ("lllyasviel/FramePackI2V_HY", "config.json"): ("git-blob-sha1", "844039fbfc65b3b0dae43292098b0edd08f6e587"),
    ("lllyasviel/FramePackI2V_HY", "diffusion_pytorch_model-00001-of-00003.safetensors"): ("sha256", "500e9aee172a1065b1807f3850c040fec88d6ab8aefeb15e601e23d8b936a441"),
    ("lllyasviel/FramePackI2V_HY", "diffusion_pytorch_model-00002-of-00003.safetensors"): ("sha256", "c142e6953620890e7e855854b5fb0fda144608a24478cf7d41507b869ce3d723"),
    ("lllyasviel/FramePackI2V_HY", "diffusion_pytorch_model-00003-of-00003.safetensors"): ("sha256", "ece170207d3d1a6f05af5f12eaf1662c87d4384920f3f618ec462194046d1e19"),
    ("lllyasviel/FramePackI2V_HY", "diffusion_pytorch_model.safetensors.index.json"): ("git-blob-sha1", "84a6a8e83fec2649f39443780a188a4bce2c469b"),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(path.lstat().st_file_attributes & REPARSE_POINT_ATTRIBUTE)
    except AttributeError:
        return False


def assert_no_reparse_components(path: Path) -> None:
    """Reject an existing symlink/junction anywhere in an absolute path."""
    if not path.is_absolute():
        raise RuntimeError(f"Path must be absolute: {path}")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if os.path.lexists(current):
            if is_reparse_point(current):
                raise RuntimeError(f"Symlink or reparse point is not allowed: {current}")


def validate_endpoint(value: str) -> str:
    endpoint = value.strip().rstrip("/")
    parsed = urlparse(endpoint)
    if (
        any(ord(character) < 32 for character in endpoint)
        or "\\" in endpoint
        or "?" in endpoint
        or "#" in endpoint
        or parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            "FRAMEPACK_HF_ENDPOINT must be an HTTPS URL without credentials, query, or fragment"
        )
    return endpoint


def validate_relative_path(value: str) -> PurePosixPath:
    candidate = PurePosixPath(value)
    windows_forbidden = '<>:"\\|?*'
    if (
        candidate.is_absolute()
        or not candidate.parts
        or any(character in windows_forbidden or ord(character) < 32 for character in value)
        or any(part in {"", ".", ".."} or part.endswith((" ", ".")) for part in candidate.parts)
    ):
        raise RuntimeError(f"Unsafe model path: {value!r}")
    return candidate


def load_runtime() -> dict[str, object]:
    # This gate deliberately precedes all path creation and network activity.
    if os.environ.get(APPROVAL_ENV, "") != "YES":
        raise RuntimeError(f"Model download requires {APPROVAL_ENV}=YES")

    root_value = os.environ.get("FRAMEPACK_ROOT", "").strip()
    if not root_value:
        raise RuntimeError("FRAMEPACK_ROOT is required")
    root_input = Path(root_value).expanduser()
    if not root_input.is_absolute():
        raise RuntimeError("FRAMEPACK_ROOT must be an absolute path")
    assert_no_reparse_components(root_input)
    if not root_input.is_dir():
        raise RuntimeError(f"FramePack root does not exist: {root_input}")
    root = root_input.resolve(strict=True)
    webui = root / "webui"
    assert_no_reparse_components(webui)
    if not webui.is_dir():
        raise RuntimeError(f"FramePack webui directory does not exist: {webui}")

    try:
        max_attempts = int(os.environ.get("FRAMEPACK_MAX_DOWNLOAD_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS)))
    except ValueError as error:
        raise RuntimeError("FRAMEPACK_MAX_DOWNLOAD_ATTEMPTS must be an integer from 1 to 10") from error
    if not 1 <= max_attempts <= 10:
        raise RuntimeError("FRAMEPACK_MAX_DOWNLOAD_ATTEMPTS must be from 1 to 10")

    return {
        "root": root,
        "webui": webui,
        "model_root": webui / "local_models",
        "status": root / "framepack-model-download.status.json",
        "complete": root / "framepack-model-download.complete",
        "lock": root / "framepack-model-download.lock",
        "endpoint": validate_endpoint(os.environ.get("FRAMEPACK_HF_ENDPOINT", DEFAULT_ENDPOINT)),
        "max_attempts": max_attempts,
    }


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_status(status_path: Path, **data: object) -> None:
    atomic_write_json(status_path, {"updatedAt": now(), **data})


def hash_file(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    digest.update(f"blob {path.stat().st_size}\0".encode("ascii"))
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, expected_size: int, identity: tuple[str, str]) -> tuple[bool, str]:
    if not path.is_file():
        return False, "missing"
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        return False, f"size {actual_size}/{expected_size}"
    algorithm, expected_digest = identity
    if algorithm == "sha256":
        actual_digest = hash_file(path, "sha256")
    elif algorithm == "git-blob-sha1":
        actual_digest = git_blob_sha1(path)
    else:
        raise RuntimeError(f"Unsupported identity algorithm: {algorithm}")
    if actual_digest.lower() != expected_digest.lower():
        return False, f"{algorithm} mismatch"
    return True, "verified"


def safe_destination(model_root: Path, folder: str, relative: str) -> Path:
    folder_path = validate_relative_path(folder)
    relative_path = validate_relative_path(relative)
    destination = model_root.joinpath(*folder_path.parts, *relative_path.parts)
    if os.path.commonpath((str(model_root), str(destination))) != str(model_root):
        raise RuntimeError(f"Model path escapes local_models: {folder}/{relative}")
    assert_no_reparse_components(destination.parent)
    if os.path.lexists(destination) and is_reparse_point(destination):
        raise RuntimeError(f"Symlink or reparse point is not allowed: {destination}")
    return destination


def curl_download(endpoint: str, repo: str, revision: str, relative: str, destination: Path) -> int:
    encoded_repo = "/".join(quote(part, safe="") for part in repo.split("/"))
    encoded_path = "/".join(quote(part, safe="") for part in validate_relative_path(relative).parts)
    url = f"{endpoint}/{encoded_repo}/resolve/{revision}/{encoded_path}?download=true"
    command = [
        "curl.exe",
        "--location",
        "--fail",
        "--proto",
        "=https",
        "--proto-redir",
        "=https",
        "--connect-timeout",
        "30",
        "--speed-time",
        "60",
        "--speed-limit",
        "1024",
        "--retry",
        "0",
        "--continue-at",
        "-",
        "--output",
        str(destination),
        url,
    ]
    return subprocess.run(command, check=False, shell=False).returncode


def acquire_lock(lock_path: Path, script_sha256: str, root: Path) -> tuple[int, str]:
    token = uuid.uuid4().hex
    payload = {
        "pid": os.getpid(),
        "createdAt": now(),
        "downloaderScriptSha256": script_sha256,
        "framepackRoot": str(root),
        "ownerToken": token,
    }
    try:
        descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise RuntimeError(f"Another downloader lock already exists: {lock_path}") from error
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return os.getpid(), token


def release_lock(lock_path: Path, ownership: tuple[int, str]) -> None:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if payload.get("pid") == ownership[0] and payload.get("ownerToken") == ownership[1]:
        lock_path.unlink(missing_ok=True)


def progress_bytes(model_root: Path) -> int:
    total = 0
    for _, folder, relative, expected_size in FILES:
        destination = safe_destination(model_root, folder, relative)
        part = destination.with_name(destination.name + ".part")
        assert_no_reparse_components(part)
        source = destination if destination.is_file() else part
        if source.is_file():
            total += min(source.stat().st_size, expected_size)
    return total


def finalize_part(part: Path, destination: Path, expected_size: int, identity: tuple[str, str]) -> bool:
    valid, reason = verify_file(part, expected_size, identity)
    if valid:
        if destination.exists():
            raise RuntimeError(f"Refusing to overwrite an existing model file: {destination}")
        os.replace(part, destination)
        return True
    if part.is_file() and part.stat().st_size >= expected_size:
        raise RuntimeError(f"Downloaded part failed verification and was preserved: {part} ({reason})")
    return False


def manifest_fingerprint() -> str:
    payload = {
        "files": FILES,
        "identities": sorted((list(key), list(value)) for key, value in IDENTITIES.items()),
        "revisions": REVISIONS,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def run() -> None:
    runtime = load_runtime()
    root = runtime["root"]
    model_root = runtime["model_root"]
    status_path = runtime["status"]
    complete_path = runtime["complete"]
    lock_path = runtime["lock"]
    endpoint = runtime["endpoint"]
    max_attempts = runtime["max_attempts"]
    assert isinstance(root, Path)
    assert isinstance(model_root, Path)
    assert isinstance(status_path, Path)
    assert isinstance(complete_path, Path)
    assert isinstance(lock_path, Path)
    assert isinstance(endpoint, str)
    assert isinstance(max_attempts, int)

    script_sha256 = hash_file(Path(__file__).resolve(), "sha256")
    ownership = acquire_lock(lock_path, script_sha256, root)
    total_bytes = sum(size for _, _, _, size in FILES)
    try:
        assert_no_reparse_components(model_root)
        model_root.mkdir(parents=True, exist_ok=True)
        assert_no_reparse_components(model_root)
        complete_path.unlink(missing_ok=True)

        for index, (repo, folder, relative, expected_size) in enumerate(FILES, start=1):
            if repo not in REVISIONS or (repo, relative) not in IDENTITIES:
                raise RuntimeError(f"Pinned identity is missing for {repo}/{relative}")
            destination = safe_destination(model_root, folder, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            assert_no_reparse_components(destination.parent)
            part = destination.with_name(destination.name + ".part")
            assert_no_reparse_components(part)
            identity = IDENTITIES[(repo, relative)]

            if destination.exists():
                valid, reason = verify_file(destination, expected_size, identity)
                if not valid:
                    raise RuntimeError(
                        f"Existing model file differs from the pinned manifest and was not overwritten: "
                        f"{destination} ({reason})"
                    )
                print(f"[{now()}] verified {folder}/{relative}", flush=True)
                continue

            if finalize_part(part, destination, expected_size, identity):
                print(f"[{now()}] finalized verified part {folder}/{relative}", flush=True)
                continue

            for attempt in range(1, max_attempts + 1):
                current_size = part.stat().st_size if part.is_file() else 0
                write_status(
                    status_path,
                    state="downloading",
                    file=f"{folder}/{relative}",
                    fileIndex=index,
                    fileCount=len(FILES),
                    fileBytes=current_size,
                    fileExpectedBytes=expected_size,
                    downloadedBytes=progress_bytes(model_root),
                    totalBytes=total_bytes,
                    attempt=attempt,
                    maxAttempts=max_attempts,
                    revision=REVISIONS[repo],
                )
                print(f"[{now()}] downloading {folder}/{relative} from byte {current_size}", flush=True)
                code = curl_download(endpoint, repo, REVISIONS[repo], relative, part)
                if finalize_part(part, destination, expected_size, identity):
                    print(f"[{now()}] completed and verified {folder}/{relative}", flush=True)
                    break
                current_size = part.stat().st_size if part.is_file() else 0
                message = f"curl exit {code}; part size {current_size}/{expected_size}"
                if attempt == max_attempts:
                    write_status(
                        status_path,
                        state="failed",
                        file=f"{folder}/{relative}",
                        fileIndex=index,
                        fileCount=len(FILES),
                        fileBytes=current_size,
                        fileExpectedBytes=expected_size,
                        downloadedBytes=progress_bytes(model_root),
                        totalBytes=total_bytes,
                        attempt=attempt,
                        maxAttempts=max_attempts,
                        error=message,
                    )
                    raise RuntimeError(f"Download attempts exhausted for {folder}/{relative}: {message}")
                write_status(
                    status_path,
                    state="retrying",
                    file=f"{folder}/{relative}",
                    fileIndex=index,
                    fileCount=len(FILES),
                    fileBytes=current_size,
                    fileExpectedBytes=expected_size,
                    downloadedBytes=progress_bytes(model_root),
                    totalBytes=total_bytes,
                    attempt=attempt,
                    maxAttempts=max_attempts,
                    error=message,
                )
                print(f"[{now()}] retrying {folder}/{relative}: {message}", file=sys.stderr, flush=True)
                time.sleep(min(30, 5 * attempt))
            else:  # pragma: no cover - the loop either completes a file or raises.
                raise RuntimeError(f"Download did not complete: {folder}/{relative}")

        marker = {
            "modelsVerified": True,
            "completedAt": now(),
            "fileCount": len(FILES),
            "totalBytes": total_bytes,
            "revisions": REVISIONS,
            "manifestSha256": manifest_fingerprint(),
            "downloaderScriptSha256": script_sha256,
        }
        atomic_write_json(complete_path, marker)
        write_status(
            status_path,
            state="complete",
            modelsVerified=True,
            downloadedBytes=total_bytes,
            totalBytes=total_bytes,
            downloaderScriptSha256=script_sha256,
            manifestSha256=marker["manifestSha256"],
        )
        print(f"[{now()}] all FramePack model files completed and verified", flush=True)
    finally:
        release_lock(lock_path, ownership)


def main() -> int:
    try:
        run()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
