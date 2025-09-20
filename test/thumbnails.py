import asyncio

import aiohttp


thumbnails = [
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/3.jpg",
            "preference": -37,
            "id": "0"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/3.webp",
            "preference": -36,
            "id": "1"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/2.jpg",
            "preference": -35,
            "id": "2"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/2.webp",
            "preference": -34,
            "id": "3"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/1.jpg",
            "preference": -33,
            "id": "4"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/1.webp",
            "preference": -32,
            "id": "5"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/mq3.jpg",
            "preference": -31,
            "id": "6"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/mq3.webp",
            "preference": -30,
            "id": "7"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/mq2.jpg",
            "preference": -29,
            "id": "8"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/mq2.webp",
            "preference": -28,
            "id": "9"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/mq1.jpg",
            "preference": -27,
            "id": "10"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/mq1.webp",
            "preference": -26,
            "id": "11"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/hq3.jpg",
            "preference": -25,
            "id": "12"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/hq3.webp",
            "preference": -24,
            "id": "13"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/hq2.jpg",
            "preference": -23,
            "id": "14"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/hq2.webp",
            "preference": -22,
            "id": "15"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/hq1.jpg",
            "preference": -21,
            "id": "16"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/hq1.webp",
            "preference": -20,
            "id": "17"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/sd3.jpg",
            "preference": -19,
            "id": "18"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/sd3.webp",
            "preference": -18,
            "id": "19"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/sd2.jpg",
            "preference": -17,
            "id": "20"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/sd2.webp",
            "preference": -16,
            "id": "21"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/sd1.jpg",
            "preference": -15,
            "id": "22"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/sd1.webp",
            "preference": -14,
            "id": "23"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/default.jpg",
            "preference": -13,
            "id": "24"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/default.webp",
            "preference": -12,
            "id": "25"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/mqdefault.jpg",
            "preference": -11,
            "id": "26"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/mqdefault.webp",
            "preference": -10,
            "id": "27"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/0.jpg",
            "preference": -9,
            "id": "28"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/0.webp",
            "preference": -8,
            "id": "29"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/hqdefault.jpg",
            "height": 360,
            "width": 480,
            "preference": -7,
            "id": "30",
            "resolution": "480x360"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/hqdefault.webp",
            "preference": -6,
            "id": "31"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/sddefault.jpg",
            "height": 480,
            "width": 640,
            "preference": -5,
            "id": "32",
            "resolution": "640x480"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/sddefault.webp",
            "preference": -4,
            "id": "33"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/hq720.jpg",
            "preference": -3,
            "id": "34"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/hq720.webp",
            "preference": -2,
            "id": "35"
        },
        {
            "url": "https://i.ytimg.com/vi/gsVPPwAlVYE/maxresdefault.jpg",
            "preference": -1,
            "id": "36"
        },
        {
            "url": "https://i.ytimg.com/vi_webp/gsVPPwAlVYE/maxresdefault.webp",
            "preference": 0,
            "id": "37"
        }
    ]

async def check_thumbnails():
    for thumb in thumbnails:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb["url"]) as resp:
                print(resp.status)
                # data = await resp.read()
                # assert data


if __name__ == "__main__":
    asyncio.run(check_thumbnails())