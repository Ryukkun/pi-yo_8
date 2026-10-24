import random


class PlaylistRandom:
    """
    プレイリストのランダム再生アルゴリズム。
    出た曲はクールダウンがリセットされ、出ていない曲は重みが増加する。
    """
    def __init__(self, _range: int) -> None:
        self._range = max(0, _range)
        self.cooldowns: list[int] = [0] * self._range

    @property
    def range(self) -> int:
        return self._range

    def set_range(self, value: int) -> None:
        self._range = max(0, value)
        if len(self.cooldowns) < self._range:
            max_value = max(self.cooldowns) if self.cooldowns else 0
            self.cooldowns.extend([max_value] * (self._range - len(self.cooldowns)))
        elif len(self.cooldowns) > self._range:
            self.cooldowns = self.cooldowns[:self._range]

    def select_next_index(self) -> int:
        if self._range <= 0:
            return 0
        weights = self.calculate_weights()
        choice = random.choices(range(self._range), weights=weights, k=1)[0]
        self.record_played(choice)
        return choice

    def record_played(self, index: int) -> None:
        for i in range(min(self._range, len(self.cooldowns))):
            if i == index:
                self.cooldowns[i] = 0
            else:
                self.cooldowns[i] += 1

    def calculate_weights(self) -> list[float]:
        if self._range <= 0:
            return []
        return [0.000001 if c / self._range < 0.3 else float(c ** 2) for c in self.cooldowns]
