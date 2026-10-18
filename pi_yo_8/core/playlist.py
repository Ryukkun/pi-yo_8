import asyncio
from collections import deque
from collections.abc import Callable
from typing import Any

from pi_yo_8.core.play_mode import PlayMode
from pi_yo_8.core.shuffle import PlaylistRandom


class Playlist:
    """
    プレイリスト管理クラス (純ドメインロジック)
    """
    def __init__(
        self,
        title: str,
        url: str,
        loop: bool = False,
        loop_pl: bool = True,
        random_pl: bool = False,
        preload_callback: Callable[[list[Any]], Any] | None = None,
    ):
        self.title = title
        self.url = url
        self.entries: list[Any] = []
        self.next_indexes: deque[int] = deque()
        self.play_history: deque[int] = deque()
        self.cooldowns: list[int] = []
        self._preload_callback = preload_callback
        self._status = PlayMode(loop, loop_pl, random_pl, on_change=self._on_status_change)
        self.random = PlaylistRandom(len(self.entries))

    @property
    def status(self) -> PlayMode:
        return self._status

    def _on_status_change(self, old: PlayMode, new: PlayMode) -> None:
        if new.loop_pl != old.loop_pl or new.random_pl != old.random_pl:
            if self.next_indexes:
                playing_index = self.next_indexes[0]
                self.next_indexes.clear()
                self.next_indexes.append(playing_index)
            if new.random_pl:
                self.random.set_range(len(self.entries))
                self.random.cooldowns = self.cooldowns.copy()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.update_next_indexes())
            except RuntimeError:
                pass

    async def update_next_indexes(self, length: int = 25) -> None:
        if self.status.random_pl:
            while len(self.next_indexes) < length:
                self.next_indexes.append(self.random.select_next_index())
        else:
            while len(self.next_indexes) < length:
                i = (self.next_indexes[-1] + 1) if self.next_indexes else 0
                if not self.status.loop_pl and len(self.entries) <= i:
                    break
                self.next_indexes.append(i % len(self.entries))
        self._preload_upcoming_entries()

    def _preload_upcoming_entries(self, count: int = 2) -> None:
        if not self._preload_callback or not self.next_indexes:
            return
        upcoming = [self.entries[self.next_indexes[i]] for i in range(min(len(self.next_indexes), count))]
        self._preload_callback(upcoming)

    def set_next_index_by_id(self, item_id: str) -> bool:
        for i, entry in enumerate(self.entries):
            entry_id = getattr(entry, "id", None) or (entry.get("id") if isinstance(entry, dict) else None)
            if entry_id == item_id:
                self.next_indexes.clear()
                self.next_indexes.append(i)
                self._preload_upcoming_entries()
                return True
        return False

    async def rewind(self, count: int = 1) -> int:
        rewind_count = min(len(self.play_history), count)
        for _ in range(rewind_count):
            self.next_indexes.appendleft(self.play_history.pop())
        self._update_cooldowns()
        self._preload_upcoming_entries()
        return count - rewind_count

    async def next(self, count: int = 1) -> int:
        await self.update_next_indexes(count + 25)
        for _ in range(count):
            if not self.next_indexes:
                return count - _
            self.play_history.append(self.next_indexes.popleft())
            if not self.next_indexes:
                return count - _
        self._preload_upcoming_entries()
        self._update_cooldowns()
        return 0

    def _update_cooldowns(self) -> None:
        if self.next_indexes:
            current = self.next_indexes[0]
            for i in range(len(self.cooldowns)):
                if i == current:
                    self.cooldowns[i] = 0
                else:
                    self.cooldowns[i] += 1
