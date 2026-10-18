from collections import deque
from typing import Any

from pi_yo_8.core.playlist import Playlist


class PlayQueue:
    """
    全体の再生キュー及び再生履歴を管理する。
    単一トラックまたはプレイリストがキュー要素となり得る。
    """
    def __init__(self):
        self.play_history: deque[Any] = deque()
        self.play_queue: deque[Any] = deque()

    async def next(self, count: int = 1, ignore_playlist: bool = False) -> bool:
        """音楽キューを進める（正で次へ、負で前へ）"""
        # 次へ
        while count > 0 and self.play_queue:
            head = self.play_queue[0]
            if isinstance(head, Playlist) and not ignore_playlist:
                count = await head.next(count)
                if count == 0:
                    break
            self.play_history.append(self.play_queue.popleft())
            count -= 1

        # 前へ
        while count < 0:
            if self.play_queue and isinstance(self.play_queue[0], Playlist):
                count = - await self.play_queue[0].rewind(abs(count))
                if count == 0:
                    break

            if self.play_history:
                count += 1
                self.play_queue.appendleft(self.play_history.pop())
            else:
                break

        return bool(self.play_queue)

    def get_current_raw(self) -> Any | None:
        if not self.play_queue:
            return None
        return self.play_queue[0]

    def is_playing_playlist(self) -> bool:
        if not self.play_queue:
            return False
        return isinstance(self.play_queue[0], Playlist)

    def get_prev_items(self, count: int = 25) -> list[Any]:
        return_items: deque[Any] = deque()
        prev_items = self.play_history.copy()
        if self.play_queue and isinstance(self.play_queue[0], Playlist):
            prev_items.append(self.play_queue[0])

        for item in reversed(prev_items):
            if isinstance(item, Playlist):
                for entry_idx in reversed([item.entries[i] for i in item.play_history]):
                    return_items.appendleft(entry_idx)
                    if len(return_items) >= count:
                        return list(return_items)
            else:
                return_items.appendleft(item)
                if len(return_items) >= count:
                    break
        return list(return_items)

    def get_next_items(self, count: int = 25) -> list[Any]:
        if not self.play_queue:
            return []
        items = []
        for queue_index in range(min(count, len(self.play_queue))):
            item = self.play_queue[queue_index]
            if isinstance(item, Playlist):
                for entry in [item.entries[i] for i in item.next_indexes]:
                    items.append(entry)
                    if len(items) >= count:
                        break
            else:
                items.append(item)
            if len(items) >= count:
                break
        return items
