import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock


class ErrorType(Enum):
    WARNING = 1
    ERROR = 2

class YTDLPInfoType(Enum):
    URL = 1
    PLAYLIST = 2
    VIDEO = 3
    CHANNEL = 4

@dataclass
class ErrorMessage:
    type: ErrorType
    description: str
    name: str = ''
    traceback: str = ''
    occurred_time: float = field(default_factory=time.time)

class StatusManager:
    def __init__(self, url: str, name: str = '', info_type: YTDLPInfoType = YTDLPInfoType.URL) -> None:
        self.url = url
        self.name = name
        self._type = info_type
        self.is_running = True
        self._errors: list[ErrorMessage] = []
        self.lock = Lock()

    def append_error(self, error: ErrorMessage) -> None:
        with self.lock:
            self._errors.append(error)
            self._errors.sort(key=lambda msg: msg.occurred_time)

    def get_errors(self, seconds_ago: float = 10.0, max_count: int = 5) -> list[ErrorMessage]:
        min_time = time.time() - seconds_ago
        result: list[ErrorMessage] = []
        with self.lock:
            for error in reversed(self._errors):
                if min_time < error.occurred_time and len(result) < max_count:
                    result.insert(0, error)
                else:
                    break
        return result
