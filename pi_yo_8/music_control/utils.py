import copy
from dataclasses import dataclass
import random
from typing import Any, Callable

@dataclass
class Status:
    loop: bool = False
    loop_pl: bool = False
    random_pl: bool = False
    callback: Callable[..., Any] | None = None

    def set(self, loop: bool | None = None, loop_pl: bool | None = None, random_pl: bool | None = None):
        old = copy.copy(self)
        if loop != None: self.loop = loop
        if loop_pl != None: self.loop_pl = loop_pl
        if random_pl != None: self.random_pl = random_pl

        if self.callback and self != old:
            self.callback(old=old, new=copy.copy(self))



class PlaylistRandom:
    def __init__(self, _range:int):
        self._range = _range
        self.cooldowns = [0] * _range  # 初期は全員同じ重み

    @property
    def range(self) -> int:
        return self._range

    @range.setter
    def range(self, value:int):
        self._range = value
        max_value = max(self.cooldowns) if self.cooldowns else 0
        for _ in range(value - len(self.cooldowns)):
            self.cooldowns.append(max_value)

    def next(self):
        # 重みを二次関数で計算
        weights = self.get_weight()
        # 選択
        choice = random.choices(range(self.range), weights=weights, k=1)[0]
        
        # クールダウン更新
        for i in range(self.range):
            if i == choice:
                self.cooldowns[i] = 0   # 出た数字はリセット
            else:
                self.cooldowns[i] += 1  # 出てない数字は蓄積

        return choice
    
    def get_weight(self):
        return [0.000001 if c/self.range < 0.3 else c**2 for c in self.cooldowns]