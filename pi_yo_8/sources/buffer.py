import io
import threading


class ModdedBuffer(io.StringIO):
    """
    readlineで先頭から行単位で読めるスレッドセーフなBuffer
    """
    def __init__(self, initial_value: str = "", newline: str | None = "\n") -> None:
        super().__init__(initial_value, newline)
        self.read_pos = 0
        self._lock = threading.Lock()

    def readline(self, size: int = -1) -> str:
        with self._lock:
            self.seek(self.read_pos)
            result = super().readline(size)
            self.read_pos = self.tell()
        return result

    def write(self, s: str) -> int:
        with self._lock:
            self.seek(0, 2)
            result = super().write(s)
        return result

    def clean(self) -> None:
        with self._lock:
            self.seek(0)
            self.truncate(0)
            self.read_pos = 0
