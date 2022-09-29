# ピーよ8号

## 簡単なせつめー

- Loopが二種類あるの `曲単体ループ` と `プレイリストのループ` 覚えておいてね

- 初期設定
  - Loop True 
  - Loop PlayList True

- プレイリスト呼び出し時に自動的に Loop False
- プレイリスト再生中でも、曲単体のループが可能
- 一応 動画ごとに音量のばらつきがないようにしてる

## こまんどぅ

- `,join` 使う機会無いけど一応<br>
- `,bye` いつもの

- `,skip(,s)` 次の曲へ

- `,stop` 一時停止

- `,playing` 再生中の曲のURL

- Loop
  - `,loop(,l)` loop切り替え [False,True]<br>
  - `,loop(,l) playlist(p or pl)` :プレイリストのループを切り替え [False,True,Random]<br>
  -` ,loop(,l) 適当な文字列` :上記に当てはまらなければ 現在の Loop の状態を返してくれる。 ライフハックだね

- Play
  - `,play(,p)` 一時停止していた場合 再生開始させる
  - `,play(,p) 文字列` Youtubeから検索して即再生 文字列にスペースおけ
  - `,play(,p) URL` URL先を即再生
    - プレイリスト内の動画が指定されたら、動画だけ読み込み
    - プレイリスト自体が指定された場合、自動的に ’,playlist’ に渡される
    - [〇 Youtube , 〇 Twitter , × ニコニコ動画 , その他不明]

- `,queue(,q)` 次に再生てきなやつ 即再生を除けば ',play' とほぼ同じことが可能

- PlayList
  - `,playlist(,pl) 文字列' ヒットしたやつ何個かプレイリスト形式で再生 文字列にスペースおけ
  - `,playlist(,pl) URL` プレイリスト再生 
    - プレイリスト内の動画のURLが指定されたら、そこからプレイリストを再生<br>
    - プレイリスト自体が指定されたら、最初から再生
    - [ Youtube のみ対応]


# 手抜きでごめんあそばせ
