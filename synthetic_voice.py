import asyncio
from wanakana import to_kana
import alkana
import re
import os
import wave
import configparser


def custam_text(text,path):

    text_out = text
    format_num = 0
    replace_list = []

    with open(path, 'r') as f:
        while (line := f.readline().strip().split(',')) != [""]:
            if line[0] in text:
                text_out = text_out.replace(line[0], '{0['+str(format_num)+']}')
                format_num += 1
                replace_list.append(line[1])

    return text_out.format(replace_list)


#------------------------------------------------------
def costom_voice(text,config):
    
    htsvoice=['-m',config['Open_Jtalk']['Voice']+'mei_normal.htsvoice']
    
    if r := re.findall(r'voice:\w*\s|voice:\w*\Z', text):
        r = re.sub(r'\s',"",r[0])
        text = re.sub(r,'',text)
        r = re.sub('voice:','',r)
        htsvoice = ['-m',config['Open_Jtalk']['Voice']+f'{r}.htsvoice']
        
    return text,f"{htsvoice[0]} {htsvoice[1]}"
    
#------------------------------------------------------

def costom_status(text,default,prefix,search_r):
    
    if r := re.findall(search_r, text):
        r = re.sub(r'\s',"",r[0])
        text = re.sub(r,'',text)
        default[1] = re.sub(prefix,'',r)
    
    if default[1] == "auto":
        return text,""
    else:
        return text,f"{default[0]} {default[1]}"


#-----------------------------------------------------------
def replace_english_kana(text):

    temp_text = text
    output = ""

    # 先頭から順番に英単語を検索しカタカナに変換
    while word := re.search(r'(^|[^a-zA-Z])([a-zA-Z\-]+)($|[^a-zA-Z])', temp_text):
        #print(f"{temp_text} : {word}")

        if word.start() != 0 or re.compile(r'[^a-zA-Z\-]').search(temp_text[0]):    # 文字のスタート位置修復
            output += temp_text[:word.start()+1]

        if kana := alkana.get_kana(word.group(2).lower()):      # 英語変換
            output += kana
        elif word.group(2).lower() == "i":
            output += "あい"
        elif re.search(r'[A-Z]',word.group(2)):
            output += word.group(2)
        else:
            output += to_kana(word.group(2).lower())   # ローマ字 → カナ 変換
        
        if word.end() != len(temp_text) or re.compile(r'[^a-zA-Z\-]').search(temp_text[-1]):    # 文字の末尾を修復
            temp_text = temp_text[word.end()-1:]
        else:
            temp_text = ""

    output += temp_text

    return output


# ************************************************


async def creat_voice(Itext,guild_id,now_time,config):

    Itext = Itext.replace('\n',' ')
    Itext = re.sub(r'^[,./?!].*','',Itext)                                                              # コマンドは読み上げない
    Itext = re.sub(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+','ユーアールエルは省略するのです！ ',Itext)    # URL省略
    Itext = re.sub(r'<:.+:[0-9]+>','',Itext)                                                            # 絵文字IDは読み上げない
    Itext = re.sub(r'<(@&|@)\d+>','メンションは省略するのです！ ',Itext)
    Itext = custam_text(Itext,config['DEFAULT']['Admin_dic'])                                           # ユーザ登録した文字を読み替える
    Itext = custam_text(Itext,config['DEFAULT']['User_dic'] + guild_id + '.txt')


    ItextTemp = re.finditer(r'(voice:\w*\s|speed:\S*\s|a:\S*\s|tone:\S*\s|jf:\S*\s)+.+?((?= voice:\w*($|\s))|(?= speed:\S*($|\s))|(?= a:\S*($|\s))|(?= tone:\S*($|\s))|(?= jf:\S*($|\s))|$)',Itext)
    ItextTemp = [nemuii.group() for nemuii in ItextTemp]

    if ItextTemp == []:

        Itext = replace_english_kana(Itext)
        Itext = re.sub(r'ww+|ｗｗ+','わらわら',Itext)
        print(f"変換後:{Itext}")
        
        cmd = f'open_jtalk -x "{config["Open_Jtalk"]["Dic"]}" -m "{config["Open_Jtalk"]["Voice"]}mei_normal.htsvoice" -r 1.2 -ow "{config["Open_Jtalk"]["Output"]}{guild_id}-{now_time}.wav"'

        prog = await asyncio.create_subprocess_shell(f'echo {Itext} | {cmd}',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        await prog.wait()


    else:
        FileNum = 0
        gather_wav = []
        for Itext in ItextTemp:
            gather_wav.append(split_voice(Itext,FileNum,f'{guild_id}-{now_time}',config))
            FileNum += 1
        await asyncio.gather(*gather_wav)

        with wave.open(config['Open_Jtalk']['Output']+guild_id+"-"+now_time+".wav", 'wb') as wav_out:
            for Num in range(FileNum):
                path = f"{config['Open_Jtalk']['Output']}{guild_id}-{now_time}-{str(Num)}.wav"
                with wave.open(path, 'rb') as wav_in:
                    if not wav_out.getnframes():
                        wav_out.setparams(wav_in.getparams())
                    wav_out.writeframes(wav_in.readframes(wav_in.getnframes()))
                if os.path.isfile(path):
                    os.remove(path)


async def split_voice(Itext,FileNum,id_time,config):
    Itext,hts = costom_voice(Itext,config)      #voice
    Itext,speed = costom_status(Itext,['-r','1.2'],"speed:",r'speed:\S*\s|speed:\S*\Z')     #speed
    Itext,a = costom_status(Itext,['-a','auto'],"a:",r'a:\S*\s|a:\S*\Z')                    #AllPath
    Itext,tone = costom_status(Itext,['-fm','auto'],"tone:",r'tone:\S*\s|tone:\S*\Z')       #tone
    Itext,jf = costom_status(Itext,['-jf','auto'],"jf:",r'jf:\S*\s|jf:\S*\Z')               #jf

    Itext = replace_english_kana(Itext)
    Itext = re.sub(r'ww+|ｗｗ+','わらわら',Itext)
    print(f"変換後 ({FileNum+1}) :{Itext}")

    FileName = config['Open_Jtalk']['Output']+id_time+"-"+str(FileNum)+".wav"
    cmd=f'open_jtalk -x "{config["Open_Jtalk"]["Dic"]}" -ow "{FileName}" {hts} {speed} {tone} {jf} {a}'
    
    prog = await asyncio.create_subprocess_shell(f'echo {Itext} | {cmd}',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    await prog.wait()