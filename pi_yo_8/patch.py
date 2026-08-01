from typing import IO
import discord


def _patch_pipe_reader(self, dest: IO[bytes]) -> None:
    while self._process:
        if self._stderr is None:
            return
        try:
            data: bytes = self._stderr.readline()
        except Exception:
            discord.player._log.debug('Read error for %s, this is probably not a problem', self, exc_info=True)
            return
        if data is None:
            return
        try:
            dest.write(data)
        except Exception:
            discord.player._log.exception('Write error for %s', self)
            self._stderr.close()
            return

def patch():
    discord.FFmpegOpusAudio._pipe_reader = _patch_pipe_reader
    discord.FFmpegPCMAudio._pipe_reader = _patch_pipe_reader