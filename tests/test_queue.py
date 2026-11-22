import pytest

from pi_yo_8.core.playlist import Playlist
from pi_yo_8.core.queue import PlayQueue
from pi_yo_8.core.track import Track


@pytest.mark.asyncio
async def test_queue_single_tracks():
    queue = PlayQueue()
    t1 = Track(id="1", title="Track 1", web_url="http://1")
    t2 = Track(id="2", title="Track 2", web_url="http://2")
    t3 = Track(id="3", title="Track 3", web_url="http://3")

    queue.play_queue.extend([t1, t2, t3])
    assert queue.get_current_raw() == t1

    has_next = await queue.next(1)
    assert has_next is True
    assert queue.get_current_raw() == t2

    has_next = await queue.next(1)
    assert has_next is True
    assert queue.get_current_raw() == t3

    # Rewind
    has_prev = await queue.next(-1)
    assert has_prev is True
    assert queue.get_current_raw() == t2

@pytest.mark.asyncio
async def test_queue_with_playlist():
    pl = Playlist("My Playlist", "http://pl")
    pl.entries = [
        Track(id="p1", title="PL 1", web_url="http://p1"),
        Track(id="p2", title="PL 2", web_url="http://p2"),
    ]
    pl.cooldowns = [0, 0]
    await pl.update_next_indexes()

    queue = PlayQueue()
    queue.play_queue.append(pl)
    assert queue.is_playing_playlist() is True

    await queue.next(1)
    assert len(pl.play_history) == 1


@pytest.mark.asyncio
async def test_get_upcoming_playlists():
    queue = PlayQueue()
    t1 = Track(id="t1", title="Track 1", web_url="http://t1")
    pl1 = Playlist("PL 1", "http://pl1")
    t2 = Track(id="t2", title="Track 2", web_url="http://t2")
    pl2 = Playlist("PL 2", "http://pl2")
    pl3 = Playlist("PL 3", "http://pl3")

    # play_queue[0] がプレイリストでも、play_queue[1:] にある次のプレイリストを最大2件取得
    pl0 = Playlist("PL 0", "http://pl0")
    queue.play_queue.extend([pl0, t1, pl1, t2, pl2, pl3])

    upcoming = queue.get_upcoming_playlists(2)
    assert len(upcoming) == 2
    assert upcoming[0] == (2, pl1)
    assert upcoming[1] == (4, pl2)

    # 単曲とプレイリストが混在する後続アイテム取得（除外指定なし／あり）
    upcoming_all = queue.get_upcoming_queue_items(2)
    assert upcoming_all == [(1, t1), (2, pl1)]

    upcoming_excluded = queue.get_upcoming_queue_items(2, exclude_ids={id(t1)})
    assert upcoming_excluded == [(2, pl1), (3, t2)]


@pytest.mark.asyncio
async def test_history_menu_items_single_tracks():
    queue = PlayQueue()
    tracks = [Track(id=str(i), title=f"Track {i}", web_url=f"http://{i}") for i in range(8)]
    queue.play_queue.extend(tracks)

    # 7曲進める -> 過去の履歴は最大5件 (Track 2 .. Track 6) が古い順で返る
    await queue.next(7)
    items = queue.get_history_menu_items(max_past=5, max_current_pl=20)
    assert [label for label, _ in items] == [f"単曲  │  Track {i}" for i in range(2, 7)]
    assert [val for _, val in items] == [f"hist:{i}" for i in range(2, 7)]


@pytest.mark.asyncio
async def test_history_menu_items_playlist_overflow_and_past_playlist():
    pl0 = Playlist("Past PL", "http://pl0")
    pl0.entries = [Track(id="a0", title="A0", web_url="http://a0")]
    await pl0.update_next_indexes()

    pl1 = Playlist("12345678901234567890", "http://pl1")
    pl1.entries = [Track(id=f"b{i}", title=f"B{i}", web_url=f"http://b{i}") for i in range(25)]
    pl1.cooldowns = [0] * 25
    await pl1.update_next_indexes()

    queue = PlayQueue()
    queue.play_queue.extend([pl0, pl1])

    # pl0 を飛ばして pl1 を22曲進める -> 過去PL1件 + 現PLの直近20件 (B2..B21) が返る
    assert queue.skip_to_queue_index(1) is True
    await queue.next(22)

    items = queue.get_history_menu_items(max_past=5, max_current_pl=20)
    assert items[0] == ("Playlist  │  Past PL", "hist:0")
    assert len(items) == 21
    assert items[1] == ("12345678901234…  │  B2", "pl_rewind:20")
    assert items[-1] == ("12345678901234…  │  B21", "pl_rewind:1")


@pytest.mark.asyncio
async def test_recall_history_item_preserves_playlist_state():
    pl0 = Playlist("Past PL", "http://pl0")
    pl0.entries = [Track(id=f"a{i}", title=f"A{i}", web_url=f"http://a{i}") for i in range(5)]
    await pl0.update_next_indexes()
    await pl0.next(2)  # next_indexes[0] == 2 (A2)

    t_cur = Track(id="cur", title="Current", web_url="http://cur")
    queue = PlayQueue()
    queue.play_history.append(pl0)
    queue.play_queue.append(t_cur)

    assert queue.recall_history_item(0) is True
    assert queue.get_current_raw() is pl0
    # プレイリストの再生位置がリセットされず続きのまま
    assert pl0.next_indexes[0] == 2
    assert list(queue.play_history) == [t_cur]

