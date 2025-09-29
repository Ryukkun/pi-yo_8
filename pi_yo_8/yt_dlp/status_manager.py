from threading import Lock
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class LambdaLogger:
    def __init__(self,
                 debug:Callable[[str], Any]|None = None,
                 warning:Callable[[str], Any]|None = None,
                 error:Callable[[str], Any]|None = None
                 ) -> None:
        self.debug_callback = debug
        self.warning_callback = warning
        self.error_callback = error

    def debug(self, msg:str):
        if self.debug_callback:
            self.debug_callback(msg)

    def warning(self, msg:str):
        if self.warning_callback:
            self.warning_callback(msg)

    def error(self, msg:str):
        if self.error_callback:
            self.error_callback(msg)


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
    type:ErrorType
    description:str
    name:str = ''
    traceback:str = ''
    occurred_time:float = field(default_factory=time.time)


class YTDLPStatusManager:
    def __init__(self, url:str, name:str = '', _type=YTDLPInfoType.URL) -> None:
        self.url = url
        self.name = name
        self._type = _type
        self.is_running = True
        self._errors:list[ErrorMessage] = []
        self.lock = Lock()

    def append_error(self, error:ErrorMessage):
        with self.lock:
            self._errors.append(error)
            self._sort_error()

    def extend_error(self, manager:"YTDLPStatusManager"):
        self._errors.extend(manager._errors)
        self._sort_error()

    def _sort_error(self):
        self._errors.sort(key = lambda msg: msg.occurred_time)

    def get_errors(self, seconds_ago:float=10.0, _max:int=5) -> list[ErrorMessage]:
        min_time = time.time() - seconds_ago
        result:list[ErrorMessage] = []
        with self.lock:
            for error in reversed(self._errors):
                if min_time < error.occurred_time and len(result) < _max:
                    result.insert(0, error)
                else:
                    break
        return result