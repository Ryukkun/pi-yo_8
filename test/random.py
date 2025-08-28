import random
import matplotlib.pyplot as plt

class BiasedRandom:
    def __init__(self, _range:int):
        self._range = _range
        self.cooldowns = [0] * _range  # 初期は全員同じ重み

    @property
    def range(self) -> int:
        return self._range

    @range.setter
    def range(self, value:int):
        self._range = value
        max_value = max(self.cooldowns)
        self.cooldowns.extend([max_value] * (value - len(self.cooldowns)))

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


# --- 使用例 ---
br = BiasedRandom(500)
n0_weight = []
for _ in range(2000):
    weight = br.get_weight()
    n0_weight.append(weight[0] / sum(weight) * 100)
    print(br.next(), end=', ')

plt.plot(n0_weight)
plt.xlabel("try")
plt.ylabel("weight")
plt.title("BiasedRandom")
plt.show()