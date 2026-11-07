import os
import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Tuple
from filelock import FileLock


class CorruptStateError(RuntimeError):
    """Raised when a managed JSON state file exists but cannot be parsed.

    The unreadable file is copied to a ``<file>.corrupt-<UTC timestamp>``
    backup and the original is left in place. Callers must not treat this as
    an empty state, because the next save would overwrite the real data.
    """

    def __init__(self, path: str, backup_path: str, cause: Exception):
        self.path = path
        self.backup_path = backup_path
        super().__init__(
            f"{path} is not valid JSON ({cause}). The unreadable file was copied to "
            f"{backup_path}; the original was left untouched. Restore or remove it before retrying."
        )


class BaseJSONManager:
    """Base class for managers that handle JSON file persistence with locking.

    ``FileLock`` is reentrant within a thread, so helpers that take the lock
    may call ``_load``/``_save`` (which also take it) without deadlocking.
    """
    def __init__(self, base_dir: str, filename: str):
        self.base_dir = base_dir
        self.path = os.path.join(base_dir, filename)
        self.lock = FileLock(self.path + ".lock")

    def _load(self) -> Dict[str, Any]:
        with self.lock:
            if not os.path.exists(self.path):
                return {}
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except ValueError as exc:  # JSONDecodeError and bad UTF-8 both subclass ValueError
                raise self._quarantine(exc) from exc

    def _quarantine(self, exc: Exception) -> CorruptStateError:
        """Copy the unreadable file to a timestamped backup and build the error to raise.

        If an existing ``<file>.corrupt-*`` backup already holds identical bytes
        (for example because the UI polls a corrupt file), that backup is reused
        instead of writing another copy on every read.
        """
        with open(self.path, "rb") as f:
            bad_bytes = f.read()
        backup = self._find_identical_backup(bad_bytes)
        if backup is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = f"{self.path}.corrupt-{stamp}"
            counter = 1
            while os.path.exists(backup):
                backup = f"{self.path}.corrupt-{stamp}-{counter}"
                counter += 1
            with open(backup, "wb") as f:
                f.write(bad_bytes)
        return CorruptStateError(self.path, backup, exc)

    def _find_identical_backup(self, data: bytes):
        directory = os.path.dirname(self.path) or "."
        prefix = os.path.basename(self.path) + ".corrupt-"
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            return None
        for name in names:
            if not name.startswith(prefix):
                continue
            candidate = os.path.join(directory, name)
            try:
                with open(candidate, "rb") as f:
                    if f.read() == data:
                        return candidate
            except OSError:
                continue
        return None

    def _save(self, data: Dict[str, Any]):
        with self.lock:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp_path = self.path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.path)

    def _update(self, fn: Callable[[Dict[str, Any]], Tuple[bool, Any]]) -> Any:
        """Read-modify-write under a single lock acquisition.

        ``fn`` receives the loaded state, mutates it in place and returns
        ``(changed, result)``. The state is saved only when ``changed`` is true.
        Because load, apply and save happen while the lock is held, concurrent
        updates to different keys cannot overwrite each other.
        """
        with self.lock:
            data = self._load()
            changed, result = fn(data)
            if changed:
                self._save(data)
            return result
