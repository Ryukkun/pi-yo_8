"""
The MIT License (MIT)
Copyright (c) 2015-present Rapptz
Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""


import io
import subprocess

from typing import Union, Optional, IO
from discord import FFmpegAudio
from discord.oggparse import OggStream
from discord.opus import Encoder as OpusEncoder



class FFmpegPCMAudio(FFmpegAudio):
    """An audio source from FFmpeg (or AVConv).
    This launches a sub-process to a specific input file given.
    .. warning::
        You must have the ffmpeg or avconv executable in your path environment
        variable in order for this to work.
    Parameters
    ------------
    source: Union[:class:`str`, :class:`io.BufferedIOBase`]
        The input that ffmpeg will take and convert to PCM bytes.
        If ``pipe`` is ``True`` then this is a file-like object that is
        passed to the stdin of ffmpeg.
    executable: :class:`str`
        The executable name (and path) to use. Defaults to ``ffmpeg``.
    pipe: :class:`bool`
        If ``True``, denotes that ``source`` parameter will be passed
        to the stdin of ffmpeg. Defaults to ``False``.
    stderr: Optional[:term:`py:file object`]
        A file-like object to pass to the Popen constructor.
        Could also be an instance of ``subprocess.PIPE``.
    before_options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg before the ``-i`` flag.
    options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg after the ``-i`` flag.
    Raises
    --------
    ClientException
        The subprocess failed to be created.
    """

    def __init__(
        self,
        source: Union[str, io.BufferedIOBase],
        *,
        executable: str = 'ffmpeg',
        pipe: bool = False,
        stderr: Optional[IO[str]] = None,
        before_options: Optional[list] = None,
        options: Optional[list] = None,
    ) -> None:
        args = []
        subprocess_kwargs = {'stdin': subprocess.PIPE if pipe else subprocess.DEVNULL, 'stderr': stderr}

        if before_options:
            args.extend(before_options)

        args.append('-i')
        args.append('-' if pipe else source)
        args.extend(('-ac', '2', '-loglevel', 'warning', '-b:a', '128k'))

        if options:
            args.extend(options)

        args.append('pipe:1')

        super().__init__(source, executable=executable, args=args, **subprocess_kwargs)

    def read(self) -> bytes:
        ret = self._stdout.read(OpusEncoder.FRAME_SIZE)
        if len(ret) != OpusEncoder.FRAME_SIZE:
            return b''
        return ret

    def is_opus(self) -> bool:
        return False




class FFmpegOpusAudio(FFmpegAudio):
    """An audio source from FFmpeg (or AVConv).
    This launches a sub-process to a specific input file given.  However, rather than
    producing PCM packets like :class:`FFmpegPCMAudio` does that need to be encoded to
    Opus, this class produces Opus packets, skipping the encoding step done by the library.
    Alternatively, instead of instantiating this class directly, you can use
    :meth:`FFmpegOpusAudio.from_probe` to probe for bitrate and codec information.  This
    can be used to opportunistically skip pointless re-encoding of existing Opus audio data
    for a boost in performance at the cost of a short initial delay to gather the information.
    The same can be achieved by passing ``copy`` to the ``codec`` parameter, but only if you
    know that the input source is Opus encoded beforehand.
    .. versionadded:: 1.3
    .. warning::
        You must have the ffmpeg or avconv executable in your path environment
        variable in order for this to work.
    Parameters
    ------------
    source: Union[:class:`str`, :class:`io.BufferedIOBase`]
        The input that ffmpeg will take and convert to Opus bytes.
        If ``pipe`` is ``True`` then this is a file-like object that is
        passed to the stdin of ffmpeg.
    bitrate: :class:`int`
        The bitrate in kbps to encode the output to.  Defaults to ``128``.
    codec: Optional[:class:`str`]
        The codec to use to encode the audio data.  Normally this would be
        just ``libopus``, but is used by :meth:`FFmpegOpusAudio.from_probe` to
        opportunistically skip pointlessly re-encoding Opus audio data by passing
        ``copy`` as the codec value.  Any values other than ``copy``, ``opus``, or
        ``libopus`` will be considered ``libopus``.  Defaults to ``libopus``.
        .. warning::
            Do not provide this parameter unless you are certain that the audio input is
            already Opus encoded.  For typical use :meth:`FFmpegOpusAudio.from_probe`
            should be used to determine the proper value for this parameter.
    executable: :class:`str`
        The executable name (and path) to use. Defaults to ``ffmpeg``.
    pipe: :class:`bool`
        If ``True``, denotes that ``source`` parameter will be passed
        to the stdin of ffmpeg. Defaults to ``False``.
    stderr: Optional[:term:`py:file object`]
        A file-like object to pass to the Popen constructor.
        Could also be an instance of ``subprocess.PIPE``.
    before_options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg before the ``-i`` flag.
    options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg after the ``-i`` flag.
    Raises
    --------
    ClientException
        The subprocess failed to be created.
    """

    def __init__(
        self,
        source: Union[str, io.BufferedIOBase],
        *,
        executable: str = 'ffmpeg',
        pipe: bool = False,
        stderr: Optional[IO[bytes]] = None,
        before_options: Optional[list] = None,
        options: Optional[list] = None,
    ) -> None:
        args = []
        subprocess_kwargs = {'stdin': subprocess.PIPE if pipe else subprocess.DEVNULL, 'stderr': stderr}

        if before_options:
            args.extend(before_options)

        args.append('-i')
        args.append('-' if pipe else source)

        # fmt: off
        args.extend(('-map_metadata', '-1',
                     '-f', 'opus',
                     '-ac', '2',
                     '-b:a', '128k',
                     '-loglevel', 'warning'))
        # fmt: on

        if options:
            args.extend(options)

        args.append('pipe:1')

        super().__init__(source, executable=executable, args=args, **subprocess_kwargs)
        self._packet_iter = OggStream(self._stdout).iter_packets()

    def read(self) -> bytes:
        return next(self._packet_iter, b'')

    def is_opus(self) -> bool:
        return True
