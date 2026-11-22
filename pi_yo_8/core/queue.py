from collections import deque
from typing import Any

from pi_yo_8.core.playlist import Playlist


class PlayQueue:
    """
    全体の再生キュー及び再生履歴を管理する。
    単一トラックまたはプレイリストがキュー要素となり得る。
    """
    def __init__(self, history_maxlen: int = 200) -> None:
        self.play_history: deque[Any] = deque(maxlen=history_maxlen)
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
        prev_items = list(self.play_history)
        if self.play_queue and isinstance(self.play_queue[0], Playlist):
            prev_items.append(self.play_queue[0])

        for item in reversed(prev_items):
            if isinstance(item, Playlist):
                for entry_idx in reversed([item.entries[i] for i in item.play_history if i < len(item.entries)]):
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
                for i in item.next_indexes:
                    if i < len(item.entries):
                        items.append(item.entries[i])
                    if len(items) >= count:
                        break
            else:
                items.append(item)
            if len(items) >= count:
                break
        return items

    def get_upcoming_playlists(self, max_count: int = 2) -> list[tuple[int, Playlist]]:
        """後続キュー(play_queue[1:])に含まれるPlaylistを最大max_count件返す。"""
        upcoming: list[tuple[int, Playlist]] = []
        for idx in range(1, len(self.play_queue)):
            item = self.play_queue[idx]
            if isinstance(item, Playlist):
                upcoming.append((idx, item))
                if len(upcoming) >= max_count:
                    break
        return upcoming

    def get_history_menu_items(
        self, max_count: int = 25, prev_display_count: int = 4
    ) -> list[tuple[str, str]]:
        """
        上の履歴セレクトメニューに表示する (label, value) のリストを古い順で返す。
        現在再生中のプレイリストは下のメニューに表示されない5個前以降、
        過去のキュー履歴はプレイリスト・単曲ともに隙間がある限り表示する。
        """
        collected: list[tuple[str, str]] = []

        head = self.get_current_raw()
        if isinstance(head, Playlist):
            pl_hist = list(head.play_history)
            if len(pl_hist) > prev_display_count:
                pl_title = str(head.title or "No Title")
                pl_prefix = pl_title if len(pl_title) <= 15 else f"{pl_title[:14]}…"
                older_count = len(pl_hist) - prev_display_count
                # 新しい方（5個前）から古い方へ走査して枠を埋める
                for offset in range(older_count):
                    steps = prev_display_count + 1 + offset
                    entry_idx = pl_hist[older_count - 1 - offset]
                    if entry_idx < len(head.entries):
                        entry = head.entries[entry_idx]
                        title = getattr(entry, "title", None)
                        if callable(title):
                            title = title()
                        video_title = str(title or "No Title")
                        label = f"{pl_prefix}  |  {video_title}"[:100]
                        collected.append((label, f"pl_rewind:{steps}"))
                        if len(collected) >= max_count:
                            collected.reverse()
                            return collected

        # 過去のキュー履歴を新しい方から走査
        for hist_idx in range(len(self.play_history) - 1, -1, -1):
            item = self.play_history[hist_idx]
            if isinstance(item, Playlist):
                pl_title = str(item.title or "No Title")
                label = f"Playlist  |  {pl_title}"[:100]
                collected.append((label, f"hist:{hist_idx}"))
            else:
                entry_title = getattr(item, "title", None)
                if callable(entry_title):
                    entry_title = entry_title()
                video_title = str(entry_title or "No Title")
                label = f"単曲  |  {video_title}"[:100]
                collected.append((label, f"hist:{hist_idx}"))

            if len(collected) >= max_count:
                break

        collected.reverse()
        return collected

    def skip_to_queue_index(self, target_index: int) -> bool:
        """指定したキューインデックスのアイテムが先頭になるまで進める。"""
        if target_index <= 0 or target_index >= len(self.play_queue):
            return False
        for _ in range(target_index):
            self.play_history.append(self.play_queue.popleft())
        return bool(self.play_queue)

    def recall_history_item(self, history_index: int) -> bool:
        """play_history の指定インデックスのアイテムを先頭へ復帰させる（状態はリセットしない）。"""
        if history_index < 0 or history_index >= len(self.play_history):
            return False
        hist_list = list(self.play_history)
        target = hist_list.pop(history_index)
        self.play_history.clear()
        self.play_history.extend(hist_list)
        if self.play_queue:
            self.play_history.append(self.play_queue.popleft())
        self.play_queue.appendleft(target)
        return True
