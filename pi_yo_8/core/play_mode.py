import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class PlayMode:
    loop: bool = False
    loop_pl: bool = False
    random_pl: bool = False
    on_change: Callable[["PlayMode", "PlayMode"], Any] | None = None

    def set(
        self,
        loop: bool | None = None,
        loop_pl: bool | None = None,
        random_pl: bool | None = None,
    ) -> None:
        old = copy.copy(self)
        if loop is not None:
            self.loop = loop
        if loop_pl is not None:
            self.loop_pl = loop_pl
        if random_pl is not None:
            self.random_pl = random_pl

        if self.on_change and (
            self.loop != old.loop
            or self.loop_pl != old.loop_pl
            or self.random_pl != old.random_pl
        ):
            self.on_change(old, copy.copy(self))
