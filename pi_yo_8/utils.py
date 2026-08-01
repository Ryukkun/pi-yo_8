from concurrent.futures import ThreadPoolExecutor
from http import cookies
import io
import logging
import asyncio
import threading
import traceback
from typing import Any, AsyncGenerator, AsyncIterator, Callable, Coroutine, Self
import aiohttp
import re
import urllib.parse
from discord.utils import _ColourFormatter

from pi_yo_8.type import T




def setup_logger():
    library, _, _ = __name__.partition('.')
    logger = logging.getLogger(library)
    handler = logging.StreamHandler()
    handler.setFormatter(_ColourFormatter())
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


class UrlAnalyzer:
    RE_IS_YOUTUBE = re.compile(r'^(.*?(youtube\.com|youtube-nocookie\.com)|youtu\.be)$')
    def __init__(self, url_or_search_text: str):
        self.url_parse = urllib.parse.urlparse(url_or_search_text)
        self.url_query: dict = {}
        self.is_url = False
        self.is_yt = False
        self.list_id: str | None = None
        self.video_id: str | None = None

        if self.url_parse.query:
            self.url_query = urllib.parse.parse_qs(self.url_parse.query)

        self.is_url = bool(self.url_parse.hostname)
        if self.is_url:
            self.is_yt = bool(self.RE_IS_YOUTUBE.match(self.url_parse.hostname)) if self.url_parse.hostname else False
            if self.is_yt:
                self.list_id = self.url_query.get('list', [None])[0]
                self.video_id = self.url_query.get('v', [None])[0]
                if not self.video_id and self.url_parse.hostname == 'youtu.be':
                    self.video_id = self.url_parse.path[1:]


async def is_url_accessible(url: str, headers: dict | None = None, cookie_str: str | None = None) -> bool:
    """
    指定したURLに接続可能かどうかを判定する

    Parameters
    ----------
    url : str
        チェックしたいURL

    Returns
    -------
    bool
        接続できればTrue、できなければFalse
    """
    try:
        cookies_dict = {}
        if cookie_str:
            cookie_jar = cookies.SimpleCookie()
            cookie_jar.load(cookie_str)
            for key, morsel in cookie_jar.items():
                cookies_dict[key] = morsel.value
        async with aiohttp.ClientSession(headers=headers, cookies=cookies_dict) as session:
            async with session.get(url) as response:
                return response.status == 200
    except Exception as e:
        traceback.print_exc()
        return False



class AsyncGenWrapper():
    def __init__(self, async_generator: AsyncGenerator[dict[str, Any], None], callback: Callable[[AsyncGenerator], Any]):
        self._agen = async_generator
        self._callback = callback

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        return self._agen.__aiter__()

    async def __anext__(self) -> dict[str, Any]:
        return await self._agen.__anext__()

    def __del__(self):
        self._callback(self._agen)



class YoutubeUtil:
    @staticmethod
    def get_video_url(video_id: str) -> str:
        return f"https://youtu.be/{video_id}"
    
    @staticmethod
    def get_channel_url(ch_id: str) -> str:
        return f"https://www.youtube.com/channel/{ch_id}"



# async 関数の型定義
AsyncFunc = Callable[..., Coroutine[Any, Any, T]]


class WrapperAbstract[T]:
    """
    メソッドに付与するディザインパターンの基底クラス。
    インスタンスバインド時にデスクリプタ(__get__)を介してラッパーを生成・キャッシュする。
    """
    def __init__(self, func: Callable[..., T], instance: object = None):
        self.func = func
        self._instance = instance

    def _new_instance(self, obj: object) -> Self:
        return self.__class__(self.func, instance=obj) # type: ignore

    def __get__(self, obj: object, objtype: type|None = None) -> Self:
        if obj is None or self._instance is not None:
            return self
        wrapper = self._new_instance(obj)
        setattr(obj, self.func.__name__, wrapper)
        return wrapper


class RunCheckStorageWrapper(WrapperAbstract[T]):
    """
    関数の二重実行を防止するラッパー
    """
    def __init__(self, func: Callable[..., T], check_completion: bool = True, instance: object = None):
        super().__init__(func, instance)
        self.is_running = False
        self.check_completion = check_completion
        self.exe: ThreadPoolExecutor | None = None
        self.lock = threading.Lock()

    def __call__(self, *args: Any, **kwargs: Any) -> T:
        with self.lock:
            if self.is_running:
                raise RuntimeError(f'{self.func.__name__} is already running')
            self.is_running = True

        if self._instance:
            args = (self._instance,) + args
        return self._run(*args, **kwargs)

    def run_in_thread(self, *args: Any, **kwargs: Any):
        with self.lock:
            if self.is_running:
                raise RuntimeError(f'{self.func.__name__} is already running')
            self.is_running = True

        if self._instance:
            args = (self._instance,) + args
        if not self.exe:
            self.exe = ThreadPoolExecutor(max_workers=1)
        self.exe.submit(self._run, *args, **kwargs)

    def __del__(self):
        if self.exe:
            self.exe.shutdown(wait=False)

    def _run(self, *args: Any, **kwargs: Any) -> T:
        try:
            return self.func(*args, **kwargs)
        finally:
            if self.check_completion:
                with self.lock:
                    self.is_running = False

    def _new_instance(self, obj: object) -> 'RunCheckStorageWrapper[T]':
        return RunCheckStorageWrapper(self.func, self.check_completion, instance=obj)


def run_check_storage(check_completion: bool = True):
    def wrapper(func: Callable[..., T]) -> RunCheckStorageWrapper[T]:
        return RunCheckStorageWrapper(func, check_completion)
    return wrapper


class TaskRunningWrapper(WrapperAbstract[Coroutine[Any, Any, T]]):
    """
    asyncio.Taskの重複作成を抑制し、単一タスクのライフサイクル（create/run/wait/cancel）を提供するラッパー
    """
    def __init__(self, func: AsyncFunc[T], instance: object = None):
        super().__init__(func, instance)
        self.task: asyncio.Task | None = None

    def _create_task(self, *args: Any, **kwargs: Any) -> asyncio.Task[T]:
        if self._instance:
            args = (self._instance,) + args
        self.task = asyncio.create_task(self.func(*args, **kwargs))
        return self.task

    def create_task(self, *args: Any, **kwargs: Any):
        if not self.is_running():
            self._create_task(*args, **kwargs)

    def wait(self) -> asyncio.Task[T] | None:
        if self.task and not self.task.done():
            return self.task
        return None

    def run(self, *args: Any, **kwargs: Any) -> asyncio.Task[T]:
        if self.task and not self.task.done():
            return self.task
        return self._create_task(*args, **kwargs)

    def is_running(self) -> bool:
        return self.task is not None and not self.task.done()

    def cancel(self):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

    def _new_instance(self, obj: object) -> 'TaskRunningWrapper[T]':
        return TaskRunningWrapper(self.func, instance=obj)


def task_running_wrapper():
    def wrapper(func: AsyncFunc[T]) -> TaskRunningWrapper[T]:
        return TaskRunningWrapper(func)
    return wrapper




class ModdedBuffer(io.StringIO):
    '''
    readlineをするときは最初から読み込まれていく
    readlineとwrite以外は使わない想定
    '''
    def __init__(self, initial_value: str | None = "", newline: str | None = "\n") -> None:
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
        self.seek(0)
        self.truncate(0)
        self.read_pos = 0