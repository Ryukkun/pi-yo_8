import asyncio
import traceback
from typing import Any


class DetectRunWrapper:
    def __init__(self, func, _class=None, _exception=False) -> None:
        self.is_running = False
        self.is_coroutine = asyncio.iscoroutinefunction(func)
        self.func = func
        self._class = _class
        self._exception = _exception
    

    def self_run(self, *args, **kwargs) -> None:
        if self._class:
            args = (self._class,) + args

        if self.is_coroutine:
            return self.async_run(*args, **kwargs)
        else:
            return self.sync_run(*args, **kwargs)


    async def async_run(self, *args, **kwargs) -> None:
        if self.is_running:
            if self._exception:
                raise Exception('This function is already running.')
            return
        self.is_running = True
        try:
            await self.func(*args, **kwargs)
        except:
            traceback.print_exc()
        finally:
            self.is_running = False
    

    def sync_run(self, *args, **kwargs) -> None:
        if self.is_running:
            if self._exception:
                raise Exception('This function is already running.')
            return
        self.is_running = True
        try:
            self.func(*args, **kwargs)
        except:
            traceback.print_exc()
        finally:
            self.is_running = False



    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return self.self_run(*args, **kwds)


    def __get__(self, obj, objtype):
        if obj is None:
            return self

        copy = DetectRunWrapper(self.func, _class=obj)
        copy._exception = self._exception

        setattr(obj, self.func.__name__, copy)
        return copy


def detect_run(exception = False):


    def wrapper(func) -> DetectRunWrapper:
        return DetectRunWrapper(func)

    return wrapper