import random


class PlaylistRandom:
    """
    プレイリストのランダム再生アルゴリズム。
    出た曲はクールダウンがリセットされ、出ていない曲は重みが増加する。
    """
    def __init__(self, _range: int):
        self._range = _range
        self.cooldowns: list[int] = [0] * _range

    @property
    def range(self) -> int:
        return self._range

    def set_range(self, value: int) -> None:
        self._range = value
        max_value = max(self.cooldowns) if self.cooldowns else 0
        for _ in range(value - len(self.cooldowns)):
            self.cooldowns.append(max_value)

    def select_next_index(self) -> int:
        if self.range <= 0:
            return 0
        weights = self.calculate_weights()
        choice = random.choices(range(self.range), weights=weights, k=1)[0]

        for i in range(self.range):
            if i == choice:
                self.cooldowns[i] = 0
            else:
                self.cooldowns[i] += 1

        return choice

    def calculate_weights(self) -> list[float]:
        if self.range <= 0:
            return []
        return [0.000001 if c / self.range < 0.3 else float(c ** 2) for c in self.cooldowns]
