import inspect
from collections.abc import Callable
from typing import Any


class TrackAttribute[T_Attr: (int, float)]:
    def __init__(
        self,
        init: T_Attr,
        min_val: T_Attr,
        max_val: T_Attr,
        on_update_callback: Callable[..., Any],
    ) -> None:
        self.value: T_Attr = init
        self.min: T_Attr = min_val
        self.max: T_Attr = max_val
        self.on_update_callback = on_update_callback

    def get(self) -> T_Attr:
        return self.value

    async def set(self, target_value: T_Attr) -> bool:
        if isinstance(target_value, float):
            target_value = round(target_value, 2)  # type: ignore[assignment]
        return await self._check(target_value)

    async def add(self, delta_value: T_Attr) -> bool:
        new_val = self.value + delta_value
        if isinstance(new_val, float):
            new_val = round(new_val, 2)  # type: ignore[assignment]
        return await self._check(new_val)

    async def _check(self, target_value: T_Attr) -> bool:
        if self.min <= target_value <= self.max:
            self.value = target_value
            res = self.on_update_callback()
            if inspect.isawaitable(res):
                await res
            return True
        return False
