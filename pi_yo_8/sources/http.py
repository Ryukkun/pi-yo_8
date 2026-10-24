from http import cookies
import aiohttp


async def is_url_accessible(url: str, headers: dict[str, str] | None = None, cookie_str: str | None = None) -> bool:
    """
    指定したURLに接続可能かどうかを判定する (ストリーム有効性確認等)
    Range: bytes=0-0 を指定して無駄なデータ転送を抑制する。
    """
    try:
        cookies_dict: dict[str, str] = {}
        if cookie_str:
            cookie_jar = cookies.SimpleCookie()
            cookie_jar.load(cookie_str)
            for key, morsel in cookie_jar.items():
                cookies_dict[key] = morsel.value

        req_headers = dict(headers or {})
        if "Range" not in req_headers:
            req_headers["Range"] = "bytes=0-0"

        timeout = aiohttp.ClientTimeout(total=5)
        async with (
            aiohttp.ClientSession(headers=req_headers, cookies=cookies_dict, timeout=timeout) as session,
            session.get(url) as response,
        ):
            return response.status in (200, 206)
    except Exception:
        return False
