import asyncio


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

    


def run_check_storage(check_fin= True):
    def wapper(func) -> RunCheckStorageWrapper:
        return RunCheckStorageWrapper(func, check_fin)
    
    return wapper


class MyClass:
    def __init__(self, val):
        self.value = val

    @run_check_storage()
    async def heavy_computation(self):
        print(f"<{self.value}> start....")
        await asyncio.sleep(1)
        print(f"<{self.value}> end")
        return
    

async def main():
    obj = MyClass(1)
    obj2 = MyClass(2)
    loop = asyncio.get_event_loop()
    t1 = loop.create_task(obj.heavy_computation())
    print("1 : ", obj.heavy_computation.is_running)
    t2 = loop.create_task(obj2.heavy_computation())
    print("2 : ", obj2.heavy_computation.is_running)
    
    await asyncio.gather(t1, t2)


if __name__ == "__main__":
    asyncio.run(main())