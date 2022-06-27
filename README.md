# ピーよ8号

## 簡単なせつめー

※Loopが二種類あるの 俺か俺以外か<br>
　　　　　　　　　　　うそ 曲単体ループ と プレイリストのループ

※初期設定で Loop True<br>
　　　　　　 Loop PlayList True

※プレイリスト呼び出し時に自動的に Loop False<br>
※プレイリスト再生中でも、曲単体のループが可能<br>

## こまんどぅ

,join :使う機会無いけど一応
,bye :いつもの

,skip(,s) :次の曲へ

,stop :一時停止

,playing :再生中の曲のURL

,loop(,l) :loop切り替え [False,True]<br>
,loop(,l) playlist(p or pl) :プレイリストのループを切り替え [False,True,Random]<br>
,loop(,l) 適当な文字列 :上記に当てはまらなければ 現在の Loop の状態を返してくれる。 ライフハックだね

,play(,p) :一時停止していた場合 再生開始させる<br>
,play(,p) URL :URL先を即再生 プレイリスト内の動画が指定されたら、動画だけ [〇 Youtube , 〇 Twitter , × ニコニコ動画 , その他不明]<br>
,play(,p) 文字列 :Youtubeから検索して即再生 文字列にスペースおけ

,queue(,q) :次に再生てきなやつ 即再生を除けば ',play' とほぼ同じことが可能

,playlist(,pl) URL :プレイリスト再生 プレイリスト内の動画のURLが指定されたら、そこからプレイリストを再生
,playlist(,pl) 文字列 :ヒットしたやつ何個かプレイリスト形式で再生 文字列にスペースおけ


# 手抜きでごめんあそばせ
