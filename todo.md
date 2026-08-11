# Claude Code 実行指示書：ComfyUI-WD14-Tagger の exclude_tags ワイルドカード対応

## 目的
`exclude_tags` パラメータが現在「完全一致」でしか判定されていない問題を修正し、
`fnmatch` によるワイルドカードマッチ（`*`, `?`, `[seq]`）に対応させる。

例：`* hair` と指定すると `brown hair` / `long hair` / `blue hair` など
「hair」で終わる全タグが除外されるようにする。

※ リポジトリのクローンは実施済みの前提。カレントディレクトリはリポジトリのルートとする。

---

## 対象ファイル
`wd14tagger.py`

---

## 修正内容

### 1. import追加
ファイル冒頭のimport群（`import csv` 付近）に以下を追加する。

```python
import fnmatch
```

### 2. `tag()` 関数内のフィルタ処理を変更

**変更前：**
```python
remove = [s.strip() for s in exclude_tags.lower().split(",")]
all = [tag for tag in all if tag[0] not in remove]
```

**変更後：**
```python
# exclude_tagsをワイルドカード対応（fnmatch）でフィルタする
# 例: "* hair" -> "brown hair", "long hair" などを除外
remove = [s.strip() for s in exclude_tags.lower().split(",") if s.strip()]
all = [
    tag for tag in all
    if not any(fnmatch.fnmatch(tag[0].lower(), pattern) for pattern in remove)
]
```

---

## 動作確認
以下を確認すること。

- `exclude_tags` を空欄にした場合、既存の動作（フィルタなし）が変わらないこと
- `exclude_tags = "1girl"` のような完全一致指定が従来通り機能すること（後方互換性）
- `exclude_tags = "* hair"` を指定した場合、`brown hair` 等の「hair」で終わるタグが除外されること
- `exclude_tags = "hair*"` のように前方一致でも機能すること
- カンマ区切りで複数パターン（例: `"* hair, * eyes"`）を指定した場合も正しく動作すること

可能であれば、ComfyUIを起動しWD14 Taggerノードで実画像を使い、上記パターンを実際に入力して結果を確認する。

---

## コミット
```bash
git add wd14tagger.py
git commit -m "feat: exclude_tagsでワイルドカード(fnmatch)マッチに対応"
```

## 差分の最終確認
```bash
git diff main -- wd14tagger.py
```
上記diffが「importの追加1行」「フィルタ処理2〜3行の変更」のみであることを確認して完了とする。

---

## 補足（Claude Codeへの注意事項）
- 既存の完全一致の挙動を壊さないこと（`fnmatch` はワイルドカードが含まれない文字列に対しては完全一致と同じ挙動になるため、通常は問題ないはずだが念のため確認する）
- `tag[0]` は元々 `replace_underscore` の設定によってアンダースコアがスペースに変換されている場合があるため、`exclude_tags` 側の入力例もそれに合わせて確認すること
- README.md内の `exclude_tags` の説明文があれば、ワイルドカード対応した旨を追記すること（任意）
