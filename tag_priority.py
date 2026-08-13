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
    """priority.jsonを読み込む。存在しない/不正な場合はビルトインデフォルトで有効動作させる（フェイルセーフ）。

    JSON構文エラーだけでなく、groups内の不正な正規表現（re.error）や
    想定外の型（TypeError）が混じっていた場合もここで吸収し、
    モジュールロード自体が失敗して起動が止まることがないようにする。
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
