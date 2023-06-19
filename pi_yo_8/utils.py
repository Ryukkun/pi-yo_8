import datetime
import logging
from discord.utils import _ColourFormatter

def int_analysis(arg):
    '''
    数字を見やすく変換
    12345 -> 1万
    '''
    arg = str(arg)
    ketas = ['万', '億', '兆', '京']
    arg_list = []
    while arg:
        if 4 < len(arg):
            arg_list.insert(0, arg[-4:])
            arg = arg[:-4]
        else:
            arg_list.insert(0, arg)
            break
    
    if len(arg_list) == 1:
        return arg_list[0]
    
    num = arg_list[0]
    if len(arg_list[0]) == 1 and arg_list[1][0] != '0':
        num = f'{num}.{arg_list[1][0]}'
    return f'{num}{ketas[ len(arg_list)-2 ]}'


def date_difference(arg:str) -> str:
    """何日前の日付か計算

    Parameters
    ----------
    arg : str
        YYYY/MM/DD

    Returns
    -------
    str
        
    """
    up_date = arg.split("/")

    diff = datetime.datetime.now() - datetime.datetime(year=int(up_date[0]), month=int(up_date[1]), day=int(up_date[2]))
    diff = diff.days 
    year_days = 365.24219
    month_days = year_days / 12
    if _ := diff // year_days:
        res = f'{int(_)}年前'

    elif _ := diff // month_days:
        res = f'{int(_)}ヵ月前'

    elif diff:
        res = f'{diff}日前'

    else:
        res = '今日'
        
    return res



def calc_time(Time:int) -> str:
    """秒から分と時間を計算

    Parameters
    ----------
    Time : int
        sec

    Returns
    -------
    str
        HH:MM:SS
    """
    Sec = Time % 60
    Min = Time // 60 % 60
    Hour = Time // 3600
    if Sec <= 9:
        Sec = f'0{Sec}'
    if Hour == 0:
        Hour = ''
    else:
        Hour = f'{Hour}:'
        if Min <= 9:
            Min = f'0{Min}'
    
    return f'{Hour}{Min}:{Sec}'



def set_logger():
    library, _, _ = __name__.partition('.')
    logger = logging.getLogger(library)
    handler = logging.StreamHandler()
    handler.setFormatter(_ColourFormatter())
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)