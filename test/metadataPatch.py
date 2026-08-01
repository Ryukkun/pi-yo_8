
import discord
import yt_dlp
import io
import time
import itertools

from typing import IO


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
patch()

YTDLP_GENERAL_PARAMS = {
    "http_headers": {
        "Accept-Language": "ja-JP,ja;q=0.9",
    },
    'format':'bestaudio/worst',
    "default_search":"ytsearch30",
    'extract_flat':"in_playlist",
    'quiet':True,
    'skip_download': True,
    "lazy_playlist": True,
    "forcejson":True
}
YTDLP_VIDEO_PARAMS = {
    "http_headers": {
        "Accept-Language": "ja-JP,ja;q=0.9",
    },
    'format':'bestaudio/worst',
    "default_search":"ytsearch30",
    'extract_flat':"in_playlist",
    'quiet':True,
    'skip_download': True,
    "noplaylist": True,
}

buffer = io.BytesIO()

ytd = yt_dlp.YoutubeDL(YTDLP_VIDEO_PARAMS)
#res = ytd.extract_info("https://www.youtube.com/watch?v=uy_BaRBJIzQ", download=False)
res = ytd.extract_info("https://rr5---sn-a5mlrnls.googlevideo.com/videoplayback?expire=1785616889&ei=mQVuapLgM8-M1d8PzeTz2Qg&ip=2001%3A240%3A2844%3A6900%3A8d32%3A161b%3Ac08c%3Aa842&id=o-AKsfDYTiUjwVJE3Mhf1CiaDJKswDQnGsJ3Gc3V5xy7Oj&itag=251&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&cps=509&met=1785595289%2C&mh=SE&mm=31%2C29&mn=sn-a5mlrnls%2Csn-oguesnd6&ms=au%2Crdu&mv=m&mvi=5&pl=39&rms=au%2Cau&initcwndbps=1203750&bui=AZFlqhNUHxgKZywiZdG-UOyhxN-S_Jv9WyCzyMKHQMRkiB-OZTyFxy33xGbMP9qr4Fy3JpE4HUogj2KA&spc=KBGBcjhTcmKkBMMPKuYdv-t1sqi3Nms7wOQxQVBByjDA&vprv=1&svpuc=1&mime=audio%2Fwebm&rqh=1&gir=yes&clen=834699&dur=49.221&lmt=1780737373248932&mt=1785594827&fvip=1&keepalive=yes&fexp=51565115&c=ANDROID_VR&txp=3308224&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cbui%2Cspc%2Cvprv%2Csvpuc%2Cmime%2Crqh%2Cgir%2Cclen%2Cdur%2Clmt&sig=AE0s2JYwRgIhAL5c8Ho7jalbyhBovXhhvZj5M2ORMoT5_9IXGDrDiVP0AiEAs8ym_mIdotBvlaWYVa1bp9tOmNYav3NqB46IqFLu7EY%3D&lsparams=cps%2Cmet%2Cmh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Crms%2Cinitcwndbps&lsig=APaTxxMwRAIgJEOeKB20hKPbQBe-i6AEjM2crhz-cZZf9Bf_4z2_t1cCIHoy5zfJSM3Lw3gzKCZcgTcOYh09xaNaKlzEcjb_g_MF", download=False)
source = discord.FFmpegOpusAudio(res["formats"][-1]["url"], stderr=buffer, options="-loglevel info -nostats")

time.sleep(1)
for line in buffer.getvalue().decode("utf-8").splitlines():
    print(line)

print("-----")
print(source.read())