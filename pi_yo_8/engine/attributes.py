from collections.abc import Callable
from typing import Any, Generic, TypeVar

T_Attr = TypeVar("T_Attr", int, float)

class TrackAttribute(Generic[T_Attr]):
    def __init__(self, init: T_Attr, min_val: T_Attr, max_val: T_Attr, on_update_callback: Callable[..., Any]) -> None:
        self.value = init
        self.min = min_val
        self.max = max_val
        self.on_update_callback = on_update_callback

    def get(self) -> T_Attr:
        return self.value

    async def set(self, target_value: T_Attr) -> bool:
        return await self._check(target_value)

    async def add(self, delta_value: T_Attr) -> bool:
        return await self._check(self.value + delta_value)

    async def _check(self, target_value: T_Attr) -> bool:
        if self.min <= target_value <= self.max:
            self.value = target_value
            await self.on_update_callback()
            return True
        return False
