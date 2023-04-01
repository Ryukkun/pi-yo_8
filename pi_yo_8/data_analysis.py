import datetime


def int_analysis(arg):
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


def date_difference(arg:str):
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