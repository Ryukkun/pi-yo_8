import asyncio
import logging
import threading
import time
from math import sqrt

import discord
import numpy as np
from discord import Guild, SpeakingState, opus

from pi_yo_8.engine.track_stream import AudioTrack

_log = logging.getLogger(__name__)

class MultiTrackVoiceClient:
    """
    Discord音声送出エンジン。複数AudioTrackの同時ミックス（20ms周期）に対応。
    """
    def __init__(self, guild: Guild, vc: discord.VoiceClient, loop: asyncio.AbstractEventLoop) -> None:
        self.guild = guild
        self.vc = vc
        self.loop = loop
        self.enable_loop = True
        self.tracks: list[AudioTrack] = []
        self.should_encode = False
        self.vc.encoder = opus.Encoder()
        self._thread: threading.Thread | None = None
        self._thread_running = False
        self._thread_lock = threading.Lock()

    def kill(self) -> None:
        self.enable_loop = False
        for track in self.tracks:
            track.pause()
            if track.ffmpeg_audio:
                track.ffmpeg_audio.cleanup()

    def add_track(self, opus_mode: bool = False) -> AudioTrack:
        track = AudioTrack(opus_mode=opus_mode, on_state_change=self.ensure_audio_loop_running)
        self.tracks.append(track)
        self.should_encode = len(self.tracks) != 1 or (len(self.tracks) == 1 and not opus_mode)
        return track

    def ensure_audio_loop_running(self) -> None:
        active = sum(1 for t in self.tracks if not t.is_paused())
        if active > 0:
            with self._thread_lock:
                if not self._thread_running:
                    self._thread_running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()

    def _set_speaking_state(self, speaking: SpeakingState) -> None:
        try:
            if self.vc.ws:
                asyncio.run_coroutine_threadsafe(self.vc.ws.speak(speaking), self.loop)
        except Exception:
            _log.exception(f"MultiTrackVoiceClient._set_speaking_state guild:{self.guild.name}")

    def _run_loop(self) -> None:
        send_audio = self.vc.send_audio_packet
        self._set_speaking_state(SpeakingState.voice)
        start_time = time.perf_counter()

        try:
            while self.enable_loop:
                byte_list: list[bytes] = []
                for track in self.tracks:
                    if chunk := track.read_bytes():
                        byte_list.append(chunk)

                active_tracks = len(byte_list)
                audio_bytes: bytes = b''
                if active_tracks >= 1:
                    if self.should_encode:
                        adjust_vol = 1 / sqrt(active_tracks)
                        audio_numpy: np.ndarray = np.sum(
                            [np.frombuffer(byte_list[i], dtype=np.int16) * adjust_vol for i in range(active_tracks)],
                            axis=0
                        )
                        audio_bytes = audio_numpy.astype(np.int16).tobytes()
                    else:
                        audio_bytes = byte_list[0]

                start_time += 0.02
                delay = max(0.0, start_time - time.perf_counter())
                time.sleep(delay)

                if audio_bytes:
                    send_audio(audio_bytes, encode=self.should_encode)
                else:
                    send_audio(opus.OPUS_SILENCE, encode=False)
                    playing = sum(1 for t in self.tracks if not t.is_paused())
                    if playing == 0:
                        self._set_speaking_state(SpeakingState.none)
                        break
        except Exception:
            _log.exception(f"MultiTrackVoiceClient._run_loop guild:{self.guild.name}")
        finally:
            with self._thread_lock:
                self._thread_running = False
