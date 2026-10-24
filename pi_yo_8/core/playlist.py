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
    ) -> None:
        self.title = title
        self.url = url
        self.entries: list[Any] = []
        self.next_indexes: deque[int] = deque()
        self.play_history: deque[int] = deque(maxlen=200)
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
                if self.cooldowns:
                    self.random.cooldowns = self.cooldowns.copy()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.update_next_indexes())
            except RuntimeError:
                pass

    async def update_next_indexes(self, length: int = 25) -> None:
        if not self.entries:
            return

        if self.status.random_pl:
            while len(self.next_indexes) < length:
                self.next_indexes.append(self.random.select_next_index())
        else:
            num_entries = len(self.entries)
            while len(self.next_indexes) < length:
                i = (self.next_indexes[-1] + 1) if self.next_indexes else 0
                if not self.status.loop_pl and num_entries <= i:
                    break
                self.next_indexes.append(i % num_entries)
        self._preload_upcoming_entries()

    def _preload_upcoming_entries(self, count: int = 2) -> None:
        if not self._preload_callback or not self.next_indexes:
            return
        upcoming = [
            self.entries[self.next_indexes[i]]
            for i in range(min(len(self.next_indexes), count))
            if self.next_indexes[i] < len(self.entries)
        ]
        if upcoming:
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
        completed = 0
        while completed < count and self.next_indexes:
            self.play_history.append(self.next_indexes.popleft())
            completed += 1
        self._preload_upcoming_entries()
        self._update_cooldowns()
        return count - completed

    def _update_cooldowns(self) -> None:
        if self.next_indexes and self.entries:
            current = self.next_indexes[0]
            self.random.record_played(current)
            self.cooldowns = self.random.cooldowns
