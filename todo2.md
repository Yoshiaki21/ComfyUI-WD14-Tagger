# 指示書：ComfyUI-WD14-Tagger（フォーク版）へのタグ優先度並べ替え機能追加

## 目的
WD14 Taggerが出力するgeneralタグに対し、キャラクター名タグとの合成**前**に、
優先度グループ順（hair等のキャラクター特徴タグを先頭寄りに）で並べ替える処理を追加する。
並べ替えのON/OFFおよびグループ定義は `priority.json` で管理し、UIには一切変更を加えない。

対象リポジトリ: https://github.com/Yoshiaki21/ComfyUI-WD14-Tagger

作業前に、実際のファイル構成・変数名がこの指示書の前提と一致しているか、
まず対象ファイル（`wd14tagger.py`等）の該当箇所を読み込んで確認すること。
差異があれば、この指示書の意図を踏まえて適宜読み替えて実装すること。

---

## 設計方針の確定事項（ユーザー確認済み）

1. **キャラクター名タグは常に最優先・先頭固定**。並べ替え対象は general タグのみ。
   キャラ要素（hair, eyes等）はキャラ名の直後に来るようにする。
2. **処理を入れる位置**：現状の実装は `character + general` を合成した後に
   タグ除去（ワイルドカード対応exclude_tags）が入る構造。この除去処理の順序自体は
   変更しない。並べ替えは **generalタグ単体に対して、character との合成前**に適用する
   （除去はタグ名でのフィルタなので、合成前にgeneralだけ並べ替えても最終的な
   タグの集合・除去結果には影響しない）。
3. **設定はUIに出さない**。`priority.json` に「有効/無効」と「グループ定義」を書き、
   起動時（モジュールロード時）に読み込む。デフォルトは有効。
   ファイルが無い/壊れている場合はビルトインのデフォルト設定で有効動作する
   （フェイルセーフ。処理全体を止めない）。
4. **`INPUT_TYPES` やノードの入出力は一切変更しない**。既存ワークフローへの影響なし。

---

## 1. 新規ファイル `priority.json`

`wd14tagger.py` と同じディレクトリに配置。ユーザーが直接編集して調整する運用。

```json
{
  "enabled": true,
  "groups": [
    {"name": "hair", "patterns": ["hair", "twintails?", "ponytail", "braid", "bun\\b", "bangs?", "ahoge", "drill", "sidelocks?", "hime cut"]},
    {"name": "eyes", "patterns": ["eye"]},
    {"name": "face_expression", "patterns": ["blush", "smile", "expression", "open mouth", "closed mouth", "tears?"]},
    {"name": "body", "patterns": ["breast", "skin", "body", "muscular", "thigh"]},
    {"name": "clothing", "patterns": ["dress", "shirt", "skirt", "uniform", "jacket", "pants", "shorts", "swimsuit", "bikini", "clothes", "clothing", "wear", "costume"]},
    {"name": "accessory", "patterns": ["ribbon", "bow", "hat", "glasses", "earrings?", "necklace", "gloves", "socks", "shoes", "boots"]},
    {"name": "pose_action", "patterns": ["standing", "sitting", "lying", "pose", "looking", "hand", "arm"]},
    {"name": "background_scene", "patterns": ["background", "sky", "indoors", "outdoors", "room", "scenery"]},
    {"name": "quality_meta", "patterns": ["^masterpiece$", "^best quality$", "^high quality$", "^highres$", "^absurdres$", "^rating:", "^official art$"]}
  ]
}
```

`enabled: false` にすれば並べ替え処理は一切スキップされ、既存の出力と完全に一致する。

---

## 2. 新規ファイル `tag_priority.py`

`wd14tagger.py` と同じディレクトリに新規作成。

**要件：**
- モジュールロード時に `priority.json` を読み込み、グローバルに設定を保持する
  （リクエストの都度ファイルI/Oしない）。
- 入力・出力とも `[(tag_name: str, prob: float), ...]` のリスト（**generalタグのみ**、
  character名は扱わない）。
- グループ判定は正規表現（`re.search`、`re.IGNORECASE`）。
  比較用に `tag_name.replace("_", " ").lower()` で正規化してから判定する
  （`replace_underscore` 設定の有無どちらでも正しく動くようにするため）。
- 同一グループ内は元の並び順を維持（安定ソート。Pythonの`list.sort`はデフォルトで安定）。
- どのグループにも一致しないタグは最後尾に、元の順序を保って配置する。

**実装例：**

```python
import json
import os
import re

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "priority.json")

_DEFAULT_GROUPS = [
    ("hair", [r"hair", r"twintails?", r"ponytail", r"braid", r"bun\b",
              r"bangs?", r"ahoge", r"drill", r"sidelocks?", r"hime cut"]),
    ("eyes", [r"eye"]),
    ("face_expression", [r"blush", r"smile", r"expression", r"open mouth",
                          r"closed mouth", r"tears?"]),
    ("body", [r"breast", r"skin", r"body", r"muscular", r"thigh"]),
    ("clothing", [r"dress", r"shirt", r"skirt", r"uniform", r"jacket",
                  r"pants", r"shorts", r"swimsuit", r"bikini", r"clothes",
                  r"clothing", r"wear", r"costume"]),
    ("accessory", [r"ribbon", r"bow", r"hat", r"glasses", r"earrings?",
                   r"necklace", r"gloves", r"socks", r"shoes", r"boots"]),
    ("pose_action", [r"standing", r"sitting", r"lying", r"pose", r"looking",
                      r"hand", r"arm"]),
    ("background_scene", [r"background", r"sky", r"indoors", r"outdoors",
                           r"room", r"scenery"]),
    ("quality_meta", [r"^masterpiece$", r"^best quality$", r"^high quality$",
                       r"^highres$", r"^absurdres$", r"^rating:",
                       r"^official art$"]),
]


def _compile_groups(groups):
    return [(name, [re.compile(p, re.IGNORECASE) for p in patterns]) for name, patterns in groups]


_DEFAULT_COMPILED_GROUPS = _compile_groups(_DEFAULT_GROUPS)


def _load_config():
    """priority.jsonを読み込む。存在しない/不正な場合はビルトインデフォルトで有効動作。

    JSON構文エラーだけでなく、groups内の不正な正規表現（re.error）や
    想定外の型（TypeError）が混じっていた場合もここで吸収する。
    _compile_groups をこの try ブロックの外（モジュールトップレベル）で
    呼び出すと、壊れたpatternsがそのまま例外として起動処理まで伝播し、
    フェイルセーフの意図（処理全体を止めない）が崩れるので注意。
    """
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        enabled = bool(data.get("enabled", True))
        raw_groups = data.get("groups")
        if raw_groups:
            groups = [(g["name"], g["patterns"]) for g in raw_groups]
            compiled = _compile_groups(groups)
        else:
            compiled = _DEFAULT_COMPILED_GROUPS
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, re.error):
        # 設定ファイルが無い/壊れている場合はフェイルセーフでデフォルト有効動作
        enabled = True
        compiled = _DEFAULT_COMPILED_GROUPS
    return enabled, compiled


_ENABLED, _COMPILED_GROUPS = _load_config()


def is_reorder_enabled() -> bool:
    """priority.jsonのenabled設定を返す"""
    return _ENABLED


def _normalize(tag: str) -> str:
    return tag.strip().replace("_", " ").lower()


def _group_index(tag_name: str) -> int:
    norm = _normalize(tag_name)
    for idx, (_name, patterns) in enumerate(_COMPILED_GROUPS):
        for pat in patterns:
            if pat.search(norm):
                return idx
    return len(_COMPILED_GROUPS)  # どのグループにも属さない = 最後尾


def reorder_general_tags(general_tags):
    """
    generalタグ（[(tag_name, prob), ...]）を優先度グループ順に並べ替える。
    character名タグはこの関数の対象外（呼び出し側で先頭に別途結合すること）。
    同一グループ内の順序は元の順序を維持する。
    """
    if not general_tags:
        return general_tags
    indexed = [(_group_index(item[0]), pos, item) for pos, item in enumerate(general_tags)]
    indexed.sort(key=lambda x: (x[0], x[1]))
    return [item for _g, _p, item in indexed]
```

---

## 3. `wd14tagger.py` の変更

**変更箇所A：import追加**（ファイル冒頭のimport群に追加）
```python
from .tag_priority import reorder_general_tags, is_reorder_enabled
```

**変更箇所B：`tag()` 関数内、character/generalの合成部分**

現状の該当メソッド一式を確認の上、`general` が確定した直後・`character` との合成前に
以下のように並べ替えを挟む（変数名は実際のフォーク版実装に合わせること）：

```python
# generalタグ確定後、characterとの合成前に優先度並べ替えを適用
# (キャラ名は最優先固定のため、reorder対象はgeneralのみ)
if is_reorder_enabled():
    general = reorder_general_tags(general)

all = character + general
# この後の除去処理（ワイルドカード対応exclude_tags）・res生成は変更しない
```

**変更箇所C：以降の処理は無変更**
タグ除去（ワイルドカード対応）、`res` 文字列生成、`INPUT_TYPES`、
`WD14Tagger` クラスのメソッドシグネチャ等は**一切変更しない**。

---

## テスト手順

1. `tag_priority.py` を単体で動作確認する（簡単なスクリプトで可）：
   - `general_tags` に `[("long hair", 0.9), ("red dress", 0.8), ("blush", 0.7), ("twintails", 0.85)]`
     等を渡し、hair系（long hair, twintails）が先頭グループに来ること、
     グループ内の相対順序が元の順序と一致することを確認する。
   - `priority.json` の `enabled` を `false` にした場合、`is_reorder_enabled()` が
     `False` を返し、`general` が並べ替えられずそのまま返ることを確認する。
2. ComfyUI上で実画像をタグ付けし、出力タグの先頭にキャラ名→hair/eyes系→その他、
   の順になっていることを目視確認する。
3. `priority.json` の `enabled` を `false` にして再度タグ付けし、
   この機能追加前の出力と完全に一致する（挙動が変わらない）ことを確認する。
4. `priority.json` を削除した状態でも起動・タグ付けがエラーなく動作すること
   （デフォルト設定で有効動作）を確認する。

## 注意点（実装時に見落としやすい点）

- `general` の除去処理（ワイルドカード対応exclude_tags）が、現状どのタイミングで
  `character` と合成された `all` に対して行われているか、必ず実装を確認すること。
  合成前のgeneralに対して除去がまだ行われていない場合、この並べ替え処理は
  除去前のgeneralに対して動く形になるが、除去はタグ名フィルタのみで順序に依存しないため、
  最終的な出力タグの集合には影響しない（順序だけが変わる）。
- タグ名のマッチングは `replace_underscore` の設定に関わらず動くよう、
  比較用文字列は都度normalizeすること（元のタグ文字列自体・確信度は変更しない）。
- 括弧のエスケープ（`\(`, `\)`）は `res` 生成時にのみ行われる。並べ替え処理内では
  エスケープ前の生タグ名を扱うこと。
- `priority.json` の読み込みはモジュールロード時の1回のみとし、
  タグ付けリクエストのたびにファイルI/Oしない（パフォーマンス配慮）。
  設定変更を反映するにはComfyUI再起動が必要になる旨、READMEに一言添えておくと親切。
- バッチ処理（複数画像を一度にタグ付け）の場合も、画像ごとに独立して
  正しく並べ替えが適用されることを確認する（グローバル状態を書き換えない）。
