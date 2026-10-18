import re
import urllib.parse


class UrlAnalyzer:
    RE_IS_YOUTUBE = re.compile(r'^(.*?(youtube\.com|youtube-nocookie\.com)|youtu\.be)$')

    def __init__(self, url_or_search_text: str):
        self.url_parse = urllib.parse.urlparse(url_or_search_text)
        self.url_query: dict[str, list[str]] = {}
        self.is_url = bool(self.url_parse.hostname)
        self.is_yt = False
        self.list_id: str | None = None
        self.video_id: str | None = None

        if self.url_parse.query:
            self.url_query = urllib.parse.parse_qs(self.url_parse.query)

        if self.is_url and self.url_parse.hostname:
            self.is_yt = bool(self.RE_IS_YOUTUBE.match(self.url_parse.hostname))
            if self.is_yt:
                self.list_id = self.url_query.get('list', [None])[0]
                self.video_id = self.url_query.get('v', [None])[0]
                if not self.video_id and self.url_parse.hostname == 'youtu.be':
                    self.video_id = self.url_parse.path.lstrip('/')
