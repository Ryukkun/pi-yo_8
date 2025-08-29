from concurrent.futures import ThreadPoolExecutor
import datetime
import logging
import asyncio
from typing import Any, Callable, Generic, Self, TypeVar
import aiohttp
import re
import urllib.parse
from discord.utils import _ColourFormatter



FREE_THREADS = ThreadPoolExecutor(max_workers=50)


def set_logger():
    library, _, _ = __name__.partition('.')
    logger = logging.getLogger(library)
    handler = logging.StreamHandler()
    handler.setFormatter(_ColourFormatter())
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


class UrlAnalyzer:
    def __init__(self, arg:str):
        self.url_parse = urllib.parse.urlparse(arg)
        self.url_query:dict = {}
        self.is_url = False
        self.is_yt = False
        self.list_id:str | None = None
        self.video_id:str | None = None

        if self.url_parse.query:
            self.url_query = urllib.parse.parse_qs(self.url_parse.query)

        self.is_url = bool(self.url_parse.hostname)
        if self.is_url:
            self.is_yt = re.match(r'^(.*?(youtube\.com|youtube-nocookie\.com)|youtu\.be)$',self.url_parse.hostname)
            if self.is_yt:
                self.list_id = self.url_query.get('list', [None])[0]
                self.video_id = self.url_query.get('v', [None])[0]
                if not self.video_id and self.url_parse.hostname == 'youtu.be':
                    self.video_id = self.url_parse.path[1:]


async def is_url_accessible(url: str) -> bool:
    """
    指定したURLに接続可能かどうかを判定する

    Parameters
    ----------
    url : str
        チェックしたいURL
    timeout : float
        タイムアウト秒数（デフォルト5秒）

    Returns
    -------
    bool
        接続できればTrue、できなければFalse
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return response.status == 200
    except Exception:
        return False


class YoutubeUtil:
    @staticmethod
    def get_web_url(video_id: str) -> str:
        return f"https://youtu.be/{video_id}"
    
    @staticmethod
    def get_ch_url(ch_id: str) -> str:
        return f"https://www.youtube.com/channel/{ch_id}"


class WrapperAbstract:
    """
    一度しか実行できないように

    メソッドにデコレータを付与することで実装
    実装クラスがimportで読み込まれた時点で_class=Noneのインスタンスが生成される
    実装クラスがインスタンス化された後、呼び出される際に __get__ , __call__ の順で呼び出される
    """
    def __init__(self, func:Callable[..., Any], _class:object=None):
        self.func = func
        self._class = _class

    def _new_instance(self, obj):
        return WrapperAbstract(self.func, _class=obj)

    def __get__(self, obj:object, objtype) -> Self:
        """
        このインスタンスが参照された場合に呼び出される

        Parameters
        ----------
        obj : Any
            参照元のオブジェクト(実装元のクラス)  クラスメソッドとして呼び出されたらNoneとなる 
        objtype : type
            参照元のオブジェクトのクラス

        Returns
        -------
        RunCheckStorageWrapper
            ラップされた関数
        """
        if obj is None:
            # クラスメソッドとして呼び出されたため処理は不要
            return self
        
        if self._class is not None:
            # _Classがあるってことは すでにラップされてる
            return self
        
        # インスタンスメソッドとして呼び出されたため、新しいラッパーを上書きし返す
        wrapper = self._new_instance(obj)
        # objの self.func.__name__[str] に wrapper をセットする
        setattr(obj, self.func.__name__, wrapper)
        return wrapper  # type: ignore


class RunCheckStorageWrapper(WrapperAbstract):
    """
    一度しか実行できないように

    メソッドにデコレータを付与することで実装
    実装クラスがimportで読み込まれた時点で_class=Noneのインスタンスが生成される
    実装クラスがインスタンス化された後、呼び出される際に __get__ , __call__ の順で呼び出される
    """
    def __init__(self, func:Callable[..., Any], check_fin:bool, _class:object=None):
        super().__init__(func, _class)
        self.is_running = False
        self.check_fin = check_fin
        self.is_coroutine = asyncio.iscoroutinefunction(func)

    def __call__(self, *args:Any, **kwargs:Any):
        if self.is_running:
            raise Exception(f'{self.func.__name__} is already running')
        self.is_running = True
        if self._class:
            args = (self._class,) + args
        return self.async_run(*args, **kwargs) if self.is_coroutine else self.sync_run(*args, **kwargs)

    def sync_run(self, *args:Any, **kwargs:Any):
        try:
            return self.func(*args, **kwargs)
        finally:
            if self.check_fin:
                self.is_running = False

    async def async_run(self, *args:Any, **kwargs:Any):
        try:
            return await self.func(*args, **kwargs)
        finally:
            if self.check_fin:
                self.is_running = False

    def set_running(self, status: bool):
        self.is_running = status

    def _new_instance(self, obj) -> 'RunCheckStorageWrapper':
        return RunCheckStorageWrapper(self.func, self.check_fin, _class=obj)


def run_check_storage(check_fin= True):
    def wapper(func) -> RunCheckStorageWrapper:
        return RunCheckStorageWrapper(func, check_fin)
    return wapper



class TaskRunningWrapper(WrapperAbstract):
    def __init__(self, func:Callable[..., Any], _class:object=None):
        super().__init__(func, _class)
        self.task: asyncio.Task | None = None

    def create_task(self, *args:Any, **kwargs:Any):
        if not self.is_running():
            self.task = asyncio.get_event_loop().create_task(self.func(*args, **kwargs))

    async def wait(self):
        if self.is_running():
            return await self.task # type: ignore
        return 
    
    async def run(self, *args:Any, **kwargs:Any):
        if self.is_running():
            return await self.wait()
        self.create_task(*args, **kwargs)
        return await self.task() # type: ignore
    
    def is_running(self) -> bool:
        if self.task is None:
            return False
        return not self.task.done()

    def _new_instance(self, obj:object):
        return TaskRunningWrapper(self.func, _class=obj)
    

def task_running_wrapper():
    def wapper(func) -> TaskRunningWrapper:
        return TaskRunningWrapper(func)
    return wapper