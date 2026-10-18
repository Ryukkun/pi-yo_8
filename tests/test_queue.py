import pytest
from pi_yo_8.core.queue import PlayQueue
from pi_yo_8.core.playlist import Playlist
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
