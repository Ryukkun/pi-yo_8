import datetime
from discord import Embed, Colour





def format_large_number(number_value):
    '''
    数字を見やすく変換
    12345 -> 1万
    '''
    raw_str = str(number_value)
    unit_labels = ['万', '億', '兆', '京']
    digit_groups = []
    while raw_str:
        if 4 < len(raw_str):
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
    """何日前の日付か計算

    Parameters
    ----------
    date_string : str
        YYYY/MM/DD

    Returns
    -------
    str
        
    """
    date_parts = date_string.split("/")

    diff_days = (datetime.datetime.now() - datetime.datetime(year=int(date_parts[0]), month=int(date_parts[1]), day=int(date_parts[2]))).days
    year_days = 365.24219
    month_days = year_days / 12
    if years := diff_days // year_days:
        result_text = f'{int(years)}年前'

    elif months := diff_days // month_days:
        result_text = f'{int(months)}ヵ月前'

    elif diff_days:
        result_text = f'{diff_days}日前'

    else:
        result_text = '今日'
        
    return result_text


def format_seconds_to_time(total_seconds: int | float) -> str:
    """秒から分と時間を計算

    Parameters
    ----------
    total_seconds : int | float
        sec

    Returns
    -------
    str
        HH:MM:SS
    """
    total_sec_int = int(total_seconds)
    seconds: str | int = total_sec_int % 60
    minutes: str | int = total_sec_int // 60 % 60
    hours: str | int = total_sec_int // 3600
    if seconds <= 9:
        seconds = f'0{seconds}'
    if hours == 0:
        hours_str = ''
    else:
        hours_str = f'{hours}:'
        if minutes <= 9:
            minutes = f'0{minutes}'
    
    return f'{hours_str}{minutes}:{seconds}'


class EmbedTemplates:
    @staticmethod
    def create_no_permission_embed():
        '''権限がない時のEmbed'''
        return Embed(title='権限がありません 🥲', colour=Colour.red())

    @staticmethod
    def create_failure_embed(title: str = '失敗', description: str = '') -> Embed:
        '''失敗した時のEmbed'''
        return Embed(title=title, description=description, colour=Colour.red())

    @staticmethod
    def get_main_color():
        '''bot ベースカラー'''
        return Colour.from_str('#e1bd5c')

    @staticmethod
    def get_player_color():
        '''自作Player の カラー'''
        return Colour.from_str('#e1bd5b')

    @staticmethod
    def get_persistent_color():
        '''playingに上書きされないカラー'''
        return Colour.from_str('#e1bd5a')