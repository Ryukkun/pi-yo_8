from pi_yo_8.core.play_mode import PlayMode
from pi_yo_8.core.shuffle import PlaylistRandom

def test_play_mode_defaults():
    mode = PlayMode()
    assert not mode.loop
    assert not mode.loop_pl
    assert not mode.random_pl

def test_play_mode_callback():
    changes = []
    def callback(old: PlayMode, new: PlayMode):
        changes.append((old.loop, new.loop))

    mode = PlayMode(on_change=callback)
    mode.set(loop=True)
    assert mode.loop
    assert len(changes) == 1
    assert changes[0] == (False, True)

def test_shuffle_random():
    shuffler = PlaylistRandom(10)
    assert shuffler.range == 10
    selected = set()
    for _ in range(30):
        idx = shuffler.select_next_index()
        assert 0 <= idx < 10
        selected.add(idx)
    # Check that it samples various indices
    assert len(selected) > 1

def test_shuffle_set_range():
    shuffler = PlaylistRandom(5)
    shuffler.set_range(8)
    assert shuffler.range == 8
    assert len(shuffler.cooldowns) == 8
