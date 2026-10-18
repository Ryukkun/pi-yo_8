import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any



class ErrorType(Enum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3

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

class LambdaLogger:
    def __init__(
        self,
        debug: Any | None = None,
        info: Any | None = None,
        warning: Any | None = None,
        error: Any | None = None,
    ) -> None:
        self.debug_callback = debug
        self.info_callback = info
        self.warning_callback = warning
        self.error_callback = error

    def debug(self, msg: str) -> None:
        if self.debug_callback:
            self.debug_callback(msg)

    def info(self, msg: str) -> None:
        if self.info_callback:
            self.info_callback(msg)

    def warning(self, msg: str) -> None:
        if self.warning_callback:
            self.warning_callback(msg)

    def error(self, msg: str) -> None:
        if self.error_callback:
            self.error_callback(msg)

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
                if error.type in (ErrorType.WARNING, ErrorType.ERROR):
                    if min_time < error.occurred_time and len(result) < max_count:
                        result.insert(0, error)
                    else:
                        break
        return result

