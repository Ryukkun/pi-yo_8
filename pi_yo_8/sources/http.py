from http import cookies

import aiohttp


async def is_url_accessible(url: str, headers: dict | None = None, cookie_str: str | None = None) -> bool:
    """
    指定したURLに接続可能かどうかを判定する (ストリーム有効性確認等)
    """
    try:
        cookies_dict = {}
        if cookie_str:
            cookie_jar = cookies.SimpleCookie()
            cookie_jar.load(cookie_str)
            for key, morsel in cookie_jar.items():
                cookies_dict[key] = morsel.value
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(headers=headers, cookies=cookies_dict, timeout=timeout) as session:
            async with session.get(url) as response:
                return response.status == 200
    except Exception:
        return False
