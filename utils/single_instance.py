import fcntl
import logging
import os


class SingleInstanceLock:
    """Process-level singleton lock to prevent duplicate local bot instances."""

    def __init__(self, lock_path: str):
        self.lock_path = lock_path
        self._fh = None

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(self.lock_path)), exist_ok=True)
        self._fh = open(self.lock_path, "w")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._fh.write(str(os.getpid()))
            self._fh.flush()
            return True
        except OSError:
            return False

    def release(self):
        if not self._fh:
            return
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            logging.warning("Failed to unlock instance lock: %s", e)
        try:
            self._fh.close()
        except OSError:
            pass
        self._fh = None
