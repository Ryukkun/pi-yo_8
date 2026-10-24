import datetime
from typing import Final

from discord import Colour, Embed


def format_large_number(number_value: int | float | str) -> str:
    """
    数字を見やすく変換
    12345 -> 1.2万
    """
    raw_str = str(int(number_value) if isinstance(number_value, (int, float)) else number_value)
    unit_labels = ['万', '億', '兆', '京']
    digit_groups = []
    while raw_str:
        if len(raw_str) > 4:
            digit_groups.insert(0, raw_str[-4:])
            raw_str = raw_str[:-4]
        else:
            digit_groups.insert(0, raw_str)
            break

    if len(digit_groups) == 1:
        return digit_groups[0]

    main_digits = digit_groups[0]
    if len(digit_groups[0]) == 1 and digit_groups[1][0] != '0':
        main_digits = f'{main_digits}.{digit_groups[1][0]}'
    return f'{main_digits}{unit_labels[len(digit_groups) - 2]}'


def calculate_days_ago_text(date_string: str) -> str:
    """何日前の日付か計算 (YYYY/MM/DD)"""
    try:
        parts = [int(p) for p in date_string.split("/")]
        target_date = datetime.datetime(parts[0], parts[1], parts[2])
    except (ValueError, IndexError):
        return date_string

    diff_days = (datetime.datetime.now() - target_date).days
    year_days = 365.24219
    month_days = year_days / 12

    if years := int(diff_days // year_days):
        return f'{years}年前'
    if months := int(diff_days // month_days):
        return f'{months}ヵ月前'
    if diff_days > 0:
        return f'{diff_days}日前'
    return '今日'


def format_seconds_to_time(total_seconds: int | float) -> str:
    """秒から分と時間を計算 (HH:MM:SS または M:SS)"""
    total_sec = max(0, int(total_seconds))
    hours, remainder = divmod(total_sec, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class EmbedTemplates:
    MAIN_COLOR: Final[Colour] = Colour.from_str('#e1bd5c')
    PLAYER_COLOR: Final[Colour] = Colour.from_str('#e1bd5b')
    PERSISTENT_COLOR: Final[Colour] = Colour.from_str('#e1bd5a')

    @classmethod
    def create_no_permission_embed(cls) -> Embed:
        """権限がない時のEmbed"""
        return Embed(title='権限がありません 🥲', colour=Colour.red())

    @classmethod
    def create_failure_embed(cls, title: str = '失敗', description: str = '') -> Embed:
        """失敗した時のEmbed"""
        return Embed(title=title, description=description, colour=Colour.red())

    @classmethod
    def get_main_color(cls) -> Colour:
        """bot ベースカラー"""
        return cls.MAIN_COLOR

    @classmethod
    def get_player_color(cls) -> Colour:
        """自作Player の カラー"""
        return cls.PLAYER_COLOR

    @classmethod
    def get_persistent_color(cls) -> Colour:
        """playingに上書きされないカラー"""
        return cls.PERSISTENT_COLOR
