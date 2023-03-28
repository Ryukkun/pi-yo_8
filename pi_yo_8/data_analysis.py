import datetime

ketas = ['万', '億', '兆', '京']
def int_analysis(arg):
    arg = str(arg)
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
    now = datetime.datetime.now().strftime('%Y/%m/%d')
    arg = arg.split('/')
    now = now.split('/')
    names = ['年前', 'ヶ月前', '日前']
    for count, (_now, _arg) in enumerate( zip(now, arg)):
        if _now == _arg:
            if count == 2:
                return '今日'
            continue
        
        return f'{int(_now)-int(_arg)}{names[count]}'