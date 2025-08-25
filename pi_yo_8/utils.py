from concurrent.futures import ThreadPoolExecutor
import datetime
import logging
import asyncio
import aiohttp
from discord.utils import _ColourFormatter


FREE_THREADS = ThreadPoolExecutor(max_workers=50)

def int_analysis(arg):
    '''
    数字を見やすく変換
    12345 -> 1万
    '''
    arg = str(arg)
    ketas = ['万', '億', '兆', '京']
    arg_list = []
    while arg:
        if 4 < len(arg):
            arg_list.insert(0, arg[-4:])
            arg = arg[:-4]
        else:
            arg_list.insert(0, arg)
            break
    
    if len(arg_list) == 1:
        return arg_list[0]
    
    num = arg_list[0]
    if len(arg_list[0]) == 1 and arg_list[1][0] != '0':
        num = f'{num}.{arg_list[1][0]}'
    return f'{num}{ketas[ len(arg_list)-2 ]}'


def date_difference(arg:str) -> str:
    """何日前の日付か計算

    Parameters
    ----------
    arg : str
        YYYY/MM/DD

    Returns
    -------
    str
        
    """
    up_date = arg.split("/")

    diff = datetime.datetime.now() - datetime.datetime(year=int(up_date[0]), month=int(up_date[1]), day=int(up_date[2]))
    diff = diff.days 
    year_days = 365.24219
    month_days = year_days / 12
    if _ := diff // year_days:
        res = f'{int(_)}年前'

    elif _ := diff // month_days:
        res = f'{int(_)}ヵ月前'

    elif diff:
        res = f'{diff}日前'

    else:
        res = '今日'
        
    return res



def calc_time(Time:int) -> str:
    """秒から分と時間を計算

    Parameters
    ----------
    Time : int
        sec

    Returns
    -------
    str
        HH:MM:SS
    """
    Sec = Time % 60
    Min = Time // 60 % 60
    Hour = Time // 3600
    if Sec <= 9:
        Sec = f'0{Sec}'
    if Hour == 0:
        Hour = ''
    else:
        Hour = f'{Hour}:'
        if Min <= 9:
            Min = f'0{Min}'
    
    return f'{Hour}{Min}:{Sec}'



def set_logger():
    library, _, _ = __name__.partition('.')
    logger = logging.getLogger(library)
    handler = logging.StreamHandler()
    handler.setFormatter(_ColourFormatter())
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


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
    def __init__(self, func, _class=None):
        self.func = func
        self._class = _class

    def _new_instance(self, obj):
        return WrapperAbstract(self.func, _class=obj)

    def __get__(self, obj, objtype):
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
        return wrapper


class RunCheckStorageWrapper(WrapperAbstract):
    """
    一度しか実行できないように

    メソッドにデコレータを付与することで実装
    実装クラスがimportで読み込まれた時点で_class=Noneのインスタンスが生成される
    実装クラスがインスタンス化された後、呼び出される際に __get__ , __call__ の順で呼び出される
    """
    def __init__(self, func, check_fin, _class=None):
        super().__init__(func, _class)
        self.is_running = False
        self.check_fin = check_fin
        self.is_coroutine = asyncio.iscoroutinefunction(func)

    def __call__(self, *args, **kwds):
        if self.is_running:
            raise Exception(f'{self.func.__name__} is already running')
        self.is_running = True
        if self._class:
            args = (self._class,) + args
        return self.async_run(*args, **kwds) if self.is_coroutine else self.sync_run(*args, **kwds)

    def sync_run(self, *a, **k):
        try:
            return self.func(*a, **k)
        finally:
            if self.check_fin:
                self.is_running = False

    async def async_run(self, *a, **k):
        try:
            return await self.func(*a, **k)
        finally:
            if self.check_fin:
                self.is_running = False

    def set_running(self, status: bool):
        self.is_running = status

    def _new_instance(self, obj):
        return RunCheckStorageWrapper(self.func, self.check_fin, _class=obj)


def run_check_storage(check_fin= True):
    def wapper(func) -> RunCheckStorageWrapper:
        return RunCheckStorageWrapper(func, check_fin)
    return wapper



class TaskRunningWrapper(WrapperAbstract):
    def __init__(self, func, _class=None):
        super().__init__(func, _class)
        self.task: asyncio.Task | None = None

    def create_task(self, *args, **kwargs):
        if self.is_running():
            raise Exception("Task is already running")
        self.task = asyncio.get_event_loop().create_task(self.func(*args, **kwargs))

    async def wait(self):
        if not self.is_running():
            return
        return await self.task
    
    async def run(self, *args, **kwargs):
        if self.is_running():
            raise Exception("Task is already running")
        return await self.task(*args, **kwargs)
    
    def is_running(self) -> bool:
        if self.task is None:
            return False
        return not self.task.done()

    def _new_instance(self, obj):
        return TaskRunningWrapper(self.func, _class=obj)
    

def task_running_wrapper():
    def wapper(func) -> TaskRunningWrapper:
        return TaskRunningWrapper(func)
    return wapper