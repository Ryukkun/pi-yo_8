from discord import Embed, Colour


class EmBase:
    @staticmethod
    def no_perm():
        '''
        権限がない時のEmbed
        '''
        return Embed(title=f'権限がありません 🥲', colour=Colour.red())

    @staticmethod
    def failed():
        '''
        失敗した時のEmbed
        '''
        return Embed(title=f'失敗 🤯', colour=Colour.red())

    @staticmethod
    def main_color():
        '''
        bot ベースカラー
        '''
        return Colour.from_str('#e1bd5c')

    @staticmethod
    def player_color():
        '''
        自作Player の カラー
        '''
        return Colour.from_str('#e1bd5b')

    @staticmethod
    def dont_replace_color():
        '''
        playingに上書きされないカラー
        '''
        return Colour.from_str('#e1bd5a')