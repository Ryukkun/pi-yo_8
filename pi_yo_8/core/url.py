import re
import urllib.parse


class UrlAnalyzer:
    RE_EMBEDDED_URL = re.compile(r'https?://[^\s<>"\']+')
    RE_IS_YOUTUBE = re.compile(r'^(.*?(youtube\.com|youtube-nocookie\.com)|youtu\.be)$')
    RE_IS_SPOTIFY = re.compile(r'^(open\.spotify\.com|spotify\.link|spoti\.fi)$')
    RE_IS_SPOTIFY_SHORT = re.compile(r'^(spotify\.link|spoti\.fi)$')
    RE_SPOTIFY_PATH = re.compile(r'^/(?:intl-[a-zA-Z-]+/)?(?:embed/)?(playlist|album|track|artist)/([a-zA-Z0-9]+)')
    RE_SPOTIFY_URI = re.compile(r'^spotify:(playlist|album|track|artist):([a-zA-Z0-9]+)$')
    RE_IS_APPLE_MUSIC = re.compile(r'^(?:beta\.)?(music\.apple\.com|itunes\.apple\.com|apple\.co)$')
    RE_IS_APPLE_SHORT = re.compile(r'^apple\.co$')
    RE_APPLE_PATH = re.compile(r'^/(?:[a-zA-Z]{2}/)?(playlist|album|song|artist|music-video)/(?:[^/]+/)?([^/?#]+)')

    def __init__(self, url_or_search_text: str):
        text = url_or_search_text.strip()
        self.normalized_url = text
        self.url_parse = urllib.parse.urlparse(text)
        if not self.url_parse.hostname:
            if m_uri := self.RE_SPOTIFY_URI.match(text):
                self.normalized_url = f"https://open.spotify.com/{m_uri.group(1)}/{m_uri.group(2)}"
                self.url_parse = urllib.parse.urlparse(self.normalized_url)
            elif m_url := self.RE_EMBEDDED_URL.search(text):
                self.normalized_url = m_url.group(0)
                self.url_parse = urllib.parse.urlparse(self.normalized_url)

        self.url_query: dict[str, list[str]] = {}
        self.is_url = bool(self.url_parse.hostname)
        self.is_yt = False
        self.list_id: str | None = None
        self.video_id: str | None = None

        self.is_spotify = False
        self.is_spotify_short = False
        self.spotify_type: str | None = None
        self.spotify_id: str | None = None

        self.is_apple_music = False
        self.is_apple_short = False
        self.apple_type: str | None = None
        self.apple_id: str | None = None
        self.apple_song_id: str | None = None

        if self.url_parse.query:
            self.url_query = urllib.parse.parse_qs(self.url_parse.query)

        if self.is_url and self.url_parse.hostname:
            hostname = self.url_parse.hostname.lower()
            self.is_yt = bool(self.RE_IS_YOUTUBE.match(hostname))
            if self.is_yt:
                self.list_id = self.url_query.get('list', [None])[0]
                self.video_id = self.url_query.get('v', [None])[0]
                if not self.video_id and hostname == 'youtu.be':
                    self.video_id = self.url_parse.path.lstrip('/')
                return

            self.is_spotify = bool(self.RE_IS_SPOTIFY.match(hostname))
            if self.is_spotify:
                self.is_spotify_short = bool(self.RE_IS_SPOTIFY_SHORT.match(hostname))
                if m := self.RE_SPOTIFY_PATH.match(self.url_parse.path):
                    self.spotify_type = m.group(1)
                    self.spotify_id = m.group(2)
                return

            self.is_apple_music = bool(self.RE_IS_APPLE_MUSIC.match(hostname))
            if self.is_apple_music:
                self.is_apple_short = bool(self.RE_IS_APPLE_SHORT.match(hostname))
                if m := self.RE_APPLE_PATH.match(self.url_parse.path):
                    self.apple_type = m.group(1)
                    self.apple_id = m.group(2)
                self.apple_song_id = self.url_query.get('i', [None])[0]
