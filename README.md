# ピーよ8号

## こまんどぅ

- `,join` つかわん
- `,bye` つかわん　誰もいなくなったら自動で抜ける<br><br>

- `,skip(,s)` 次の曲へ 
- `,skip(,s) 数字` 正の値だったらn秒スキップとなる。負の値だったら巻き戻しとなる。<br>
               例)`,s 30` => 30秒 スキップ | `,s -60m` => 60分 巻き戻し | `,s 3:43:88` ここの時間から再生<br><br>
               
- `,playing` 再生中の曲のURL<br><br>

- Play(,p ,pl)
  - `,play(,p) 文字列` Youtubeから検索して即再生 例) `,p in love with a fox`
  - `,play(,p) URL` URL先を即再生
    - とりま いい感じに再生するから安心して
    - [〇 Youtube , 〇 Twitter , × ニコニコ動画 , その他不明]<br><br>

- `,queue(,q)` 次に再生てきなやつ 即再生を除けば ',play' とほぼ同じことが可能 使わん デバックもそんなしてない 何なら使わんで 俺は完璧<br><br>
    
- `,download(,dl) URL or 文字列` URL先の動画 または ヒットした動画 から、'動画をダウンロードすることができるURL' を抽出し、表形式で表示する。
- `/download URL or 文字列` 他人に表示されない。機能は上記と同じ<br><br>


## ☆ 開発頑張った偉いね
- Python 3.8.10にて制作
- ffmpeg (スピード、ピッチの調節に **rubberband** を使用したため、有効化必須)
- OS : Windows MacOS Linux(Ubuntu) にて動作確認済み<br><br>


# 基本的に GUI操作
music bot用のチャットチャンネルを、作っておいた方がいいよー！
### 作ったやつ天才か！？
### 天才すぎてハルマゲドンおきそーー！！
