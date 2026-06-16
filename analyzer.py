# -*- coding: utf-8 -*-
"""
analyzer.py  —  界域分析引擎
导入图片 → 提取主色 → 颜色解析 / 数字解析 / 字母解析 → 综合判定所属界
并计算「连接危险指数」（武秀琴安全阀门用）。
"""
import colorsys
import hashlib
import math
import re
from collections import Counter

from PIL import Image, ImageDraw

import realm_data as rd


# ---------------------------------------------------------------------------
# 颜色分类：把一个 RGB 归到 白/红/绿/浅绿/蓝/黑/黄/金/紫/灰/橙/青 之一
# ---------------------------------------------------------------------------
def classify_color(rgb):
    r, g, b = [c / 255.0 for c in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    hue = h * 360.0

    if v < 0.18:
        return "黑"
    if s < 0.15:
        return "白" if v > 0.72 else "灰"
    # 有彩色，按色相分
    if hue < 18 or hue >= 330:
        return "红"
    if hue < 40:
        return "橙"
    if hue < 52:
        # 金：偏暗/中饱和的黄橙（金属金）；亮而纯的归黄
        if 0.45 <= s <= 0.92 and 0.45 <= v <= 0.92:
            return "金"
        return "黄"
    if hue < 70:
        return "黄"
    if hue < 160:
        # 浅绿：高明度低饱和的粉绿（魔小孩）
        if v > 0.70 and s < 0.50:
            return "浅绿"
        return "绿"
    if hue < 200:
        return "青"
    if hue < 255:
        return "蓝"
    if hue < 295:
        return "紫"
    return "红"  # 295~330 偏紫红，归红


# ---------------------------------------------------------------------------
# 像素显著性权重：抓主体，而非数面积
#   主体通常 = 居中 + 鲜艳(高饱和) 的物体；
#   背景通常 = 边角 + 灰扑扑(低饱和)。
#   权重 = 中心权重 × 饱和度显著性 × 类别修正。
# ---------------------------------------------------------------------------
def pixel_weight(rgb, x, y, w, h, cat):
    r, g, b = [c / 255.0 for c in rgb]
    _, s, v = colorsys.rgb_to_hsv(r, g, b)

    # 1) 中心加权：正中=1.0，四角≈0.30
    dx = (x / (w - 1) - 0.5) if w > 1 else 0.0
    dy = (y / (h - 1) - 0.5) if h > 1 else 0.0
    dist = math.sqrt(dx * dx + dy * dy) / 0.7071          # 0~1
    center = max(0.30, 1.0 - 0.70 * dist)

    # 2) 饱和度显著性：鲜艳的主体标签远比灰背景抢眼
    sat = 0.30 + 1.7 * s                                  # 灰≈0.30，鲜艳≈2.0

    # 3) 类别修正：灰是典型背景色，再压一档；纯黑(暗角/阴影)也压
    fix = 1.0
    if cat == "灰":
        fix = 0.45
    elif cat == "黑" and v < 0.10:
        fix = 0.55
    elif cat == "白" and v > 0.95 and s < 0.05:
        fix = 0.85                                        # 过曝纯白略压，避免反光抢主体

    return center * sat * fix


# ---------------------------------------------------------------------------
# 提取主色：缩小 + 按显著性加权统计（抓主体，而非整幅面积）
# ---------------------------------------------------------------------------
def extract_palette(path, max_side=160):
    img = Image.open(path).convert("RGB")
    w0, h0 = img.size
    scale = max_side / max(w0, h0)
    if scale < 1:
        img = img.resize((max(1, int(w0 * scale)), max(1, int(h0 * scale))))
    w, h = img.size

    pixels = list(img.getdata())
    cat_weight = Counter()          # 加权显著性（决定占比/主色）
    cat_rgb_sum = {}                # 加权平均 RGB（色块展示用鲜艳的代表色）
    for i, px in enumerate(pixels):
        x, y = i % w, i // w
        cat = classify_color(px)
        wt = pixel_weight(px, x, y, w, h, cat)
        cat_weight[cat] += wt
        s = cat_rgb_sum.setdefault(cat, [0.0, 0.0, 0.0, 0.0])
        s[0] += px[0] * wt; s[1] += px[1] * wt; s[2] += px[2] * wt; s[3] += wt

    total = sum(cat_weight.values()) or 1.0
    palette = []
    for cat, wsum in cat_weight.most_common():
        s = cat_rgb_sum[cat]
        d = s[3] or 1.0
        avg = (int(s[0] / d), int(s[1] / d), int(s[2] / d))
        palette.append({
            "cat": cat,
            "ratio": wsum / total,
            "rgb": avg,
            "meaning": rd.COLOR_MEANING.get(cat, ""),
        })
    return palette, img.size


# ---------------------------------------------------------------------------
# 数字解析：逐位解码任意整数（如银行卡尾号 4022）
# ---------------------------------------------------------------------------
def decode_number(n):
    s = str(abs(int(n)))
    lines = []
    dirty = 0
    for ch in s:
        meaning = rd.DIGIT_MEANING.get(ch, "未知")
        flag = "  ⚠不平衡" if ch in rd.DIRTY_DIGITS else ""
        if ch in rd.DIRTY_DIGITS:
            dirty += 1
        lines.append("  {} → {}{}".format(ch, meaning, flag))
    verdict = "含 {} 个偶数位（2/4/6/8）→ ".format(dirty)
    verdict += "偏混乱·不平衡界" if dirty else "无偶位浊数，偏清"
    return "\n".join(lines), verdict


# 中文数位单位（用于「9万压5千」式的逐级相压）
_CN_UNITS = ["", "十", "百", "千", "万", "十万", "百万", "千万",
             "亿", "十亿", "百亿", "千亿", "兆", "十兆", "百兆", "千兆"]


def _place_unit(pos):
    return _CN_UNITS[pos] if pos < len(_CN_UNITS) else "·10^{}".format(pos)


def _digit_realm(d, phone):
    """单数字 → 界名。电话语境下 1=真界、0=假界。"""
    if phone and d == 1:
        return "真界"
    if phone and d == 0:
        return "假界"
    return rd.REALMS.get(d, "?") if d != 0 else "外循环·大循环"


def _digit_short(d, phone):
    if phone and d == 1:
        return "真"
    if phone and d == 0:
        return "假"
    return rd.DIGIT_SHORT.get(str(d), "?")


def pressing_chain(s, phone=False):
    """最大的数逐步压最小的数，并融合成一个完整界名：
       95022 → 9万(超高维仙佛) 压 5千(高维机械) 压 0百(大循环) 压 末22(永恒带女丧尸)
       融合 → 超高维仙佛高维机械大循环天上永恒低魔界。
       高位数字是该数字界的「高维版」，最高位「超高维」，逐级下压；最后两位按字典读。
       phone=True 时按电话语境：首位 1=真、0=假。"""
    L = len(s)
    lead, tail = s[:-2], s[-2:]
    parts, lab, segs = [], [], []
    for i, ch in enumerate(lead):
        unit = _place_unit(L - 1 - i)
        d = int(ch)
        prefix = "超高维" if i == 0 else "高维"        # 最高位为超高维
        if d == 0 and not phone:
            realm_full, seg = "外循环·大循环", "大循环"
        else:
            realm_full = prefix + "·" + _digit_realm(d, phone)
            seg = prefix + _digit_short(d, phone)
        parts.append("{}{}→{}".format(ch, unit, realm_full))
        lab.append("{}{}".format(ch, unit))
        segs.append(seg)
    tail_n = int(tail)
    tail_name = rd.realm_name(tail_n)
    parts.append("末{}→{}（字典）".format(tail, tail_name))
    lab.append("末" + tail)
    segs.append(tail_name[:-1] if tail_name.endswith("界") else tail_name)

    fused = "".join(segs) + "界"
    lead0 = int(lead[0])
    primary_name = _digit_realm(lead0, phone)
    primary_txt = "{}{}→超高维·{}（逐级下压一切）".format(
        lead[0], _place_unit(L - 1), primary_name)
    return {"text": " 压 ".join(parts), "compact": "压".join(lab), "fused": fused,
            "primary_name": primary_name, "primary_txt": primary_txt}


# ---------------------------------------------------------------------------
# 数字串解析：最大的数逐步压最小的数
#   规律（武秀琴/胡思乱想体系）：
#     · 0~MAX_REALM：直接套用完整界字典（含推理界标注）。
#     · 大数（电话/卡号/身份证 95022）：不取模！高位数字逐级下压低位 ——
#       9万(高维仙佛)压5千(高维机械)压0(外循环)压末22(字典)。
#     · 地狱底色由 0（外循环）带来，不是首位本身。
# ---------------------------------------------------------------------------
def decode_ocr_number(s, phone=False):
    s = "".join(ch for ch in s if ch.isdigit())
    if not s:
        return None
    inline = " ".join("{}{}".format(ch, _digit_short(int(ch), phone)) for ch in s)
    dirty = sum(1 for ch in s if ch in rd.DIRTY_DIGITS)
    has_zero = "0" in s
    n = int(s)

    inferred = False
    if 0 <= n <= rd.MAX_REALM and not phone:
        # 字典范围内：直接套用完整界字典（0~303）
        whole = "{} {}".format(n, rd.realm_name(n))
        primary_name = rd.realm_name(n)
        primary_txt = "{} {}".format(n, primary_name)
        fused = rd.realm_name(n)
        inferred = rd.is_inferred(n)
    else:
        # 超范围大数（或电话）：逐级相压 + 融合界名（末两位仍查字典）
        ch = pressing_chain(s, phone=phone)
        whole = ch["text"]
        primary_name = ch["primary_name"]
        primary_txt = ch["primary_txt"]
        fused = ch["fused"]

    ratio = dirty / len(s)
    if ratio >= 0.5:
        verdict = "浊重（{}/{} 位不平衡）→ 混乱/肮脏倾向".format(dirty, len(s))
    elif dirty == 0:
        verdict = "清（无 2/4/6/8）→ 偏平衡"
    else:
        verdict = "半浊（{}/{} 位不平衡）→ 需谨慎".format(dirty, len(s))
    if has_zero:
        verdict += " · 含 0：外循环大循环（人世间，带地狱沉沦底色）"
    return {"digits": s, "inline": inline, "whole": whole, "fused": fused,
            "primary_name": primary_name, "primary_txt": primary_txt,
            "inferred": inferred, "dirty": dirty, "verdict": verdict}


# ---------------------------------------------------------------------------
# 综合解码：字母 + 数字混合（如 BN1234）一起解析
#   字母走精神探索字母界，数字走十进制界，最后各自整合 + 合并判语。
# ---------------------------------------------------------------------------
def decode_mixed(text):
    text = (text or "").strip()
    if not text:
        return "（请输入字母/数字，如 BN1234）"

    tokens = re.findall(r"[A-Za-z]+|\d+|[^A-Za-z\d]+", text)
    lines = ["综合解码：{}".format(text), "", "【按出现顺序】"]
    letters_all, digits_all = "", ""

    for tok in tokens:
        if tok.isalpha():
            for ch in tok.upper():
                if ch in rd.LETTERS:
                    tag = "·偏真/善" if ch in rd.LETTER_GOOD else (
                          "·偏暗/反" if ch in rd.LETTER_DARK else "")
                    lines.append("  字母 {} → {} {}".format(ch, rd.LETTERS[ch], tag))
                    letters_all += ch
        elif tok.isdigit():
            digits_all += tok
            inline = " ".join("{}{}".format(c, rd.DIGIT_SHORT.get(c, "?")) for c in tok)
            lines.append("  数字 {} → {}".format(tok, inline))
        # 其它符号忽略

    dec = None
    if digits_all:
        dec = decode_ocr_number(digits_all)
        lines += ["", "【数字整合】{} → {}".format(dec["digits"], dec["whole"]),
                  "  " + dec["verdict"]]

    good = dark = 0
    lean = ""
    if letters_all:
        good = sum(1 for c in letters_all if c in rd.LETTER_GOOD)
        dark = sum(1 for c in letters_all if c in rd.LETTER_DARK)
        lean = "偏真善" if good > dark else ("偏暗反" if dark > good else "真假相杂")
        lines += ["", "【字母整合】{} —— 真善 {} / 暗反 {} → {}".format(
            letters_all, good, dark, lean)]

    # ---------------- 结论（始终给出） ----------------
    lines += ["", "══════ 结论 ══════"]

    # 融合界名（逐级相压拼成的完整界名）+ 主导界
    primary_name = ""
    if dec:
        primary_name = dec["primary_name"]
        lines.append("★ 融合界名：{}".format(dec["fused"]))
        lines.append("主导界：{}".format(dec["primary_txt"]))
    if letters_all:
        lines.append("字母倾向：{}（真善 {} / 暗反 {}）".format(lean, good, dark))

    # 危险等级：界名关键词 + 数字浊位 + 暗字母
    score = 0
    for kw in rd.RISK_KEYWORDS:
        if kw in primary_name:
            score += 14
    for kw in rd.SAFE_KEYWORDS:
        if kw in primary_name:
            score -= 16
    if dec:
        score += int(dec["dirty"] / max(1, len(dec["digits"])) * 40)
        if "0" in dec["digits"]:
            score += 6           # 0 带地狱沉沦底色
    score += dark * 8 - good * 6
    score = max(0, min(100, score))
    lines.append("危险等级：{}/100 —— {}".format(score, danger_level(score)))

    # 一句话总判 + 武秀琴提醒
    if score < 33:
        tip = "清净近真，可安心；但真的也不要追。"
    elif score < 66:
        tip = "半浊，连接前务必先如如不动、化掉欲望。"
    else:
        tip = "重浊伤身，非如如不动不可连接；假的永远不要信。"
    lines.append("一句话：{}".format(tip))
    lines.append("武秀琴：化掉一切自身的假的，剩下的全是真的、高的。")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 电话号码解析：叠加「真假签名」层
#   电话语境特规：开头 1 = 真（以真为根）、0 = 假；10 / 01 = 真假混合。
#   1 真、0 假 构成号码的真假二进制；2~9 是「实数字」（界的肉身）。
# ---------------------------------------------------------------------------
def decode_phone(raw):
    s = "".join(ch for ch in (raw or "") if ch.isdigit())
    if not s:
        return "（请输入电话号码，如 13010320000）"

    lines = ["电话号码：{}".format(s), ""]

    # —— 真假层 ——
    seq = " ".join("真" if c == "1" else ("假" if c == "0" else c + "实") for c in s)
    zhen = s.count("1")
    jia = s.count("0")
    mixed = sum(1 for i in range(len(s) - 1) if s[i:i + 2] in ("10", "01"))
    lead = s[0]
    lead_tf = ("真（以真为根）" if lead == "1" else
               "假（以假为根，根虚）" if lead == "0" else lead + "实（实数起头）")
    if zhen > jia:
        tf_verdict = "偏真（真 {} > 假 {}）".format(zhen, jia)
    elif jia > zhen:
        tf_verdict = "偏假（假 {} > 真 {}，虚浮）".format(jia, zhen)
    else:
        tf_verdict = "真假相当（真 {} = 假 {}）".format(zhen, jia)
    if mixed:
        tf_verdict += "，{} 处真假交界（10/01 混合）".format(mixed)

    lines += [
        "【真假签名】（电话规：1=真、0=假、2~9=实）",
        "  首位：{}".format(lead_tf),
        "  序列：" + seq,
        "  真 {} ｜ 假 {} ｜ 真假交界 {} → {}".format(zhen, jia, mixed, tf_verdict),
        "",
    ]

    # —— 界层（电话语境压制链：1=真界、0=假界） ——
    dec = decode_ocr_number(s, phone=True)
    lines += [
        "【界层·逐级相压】（电话语境）",
        "  " + dec["whole"],
        "  ★ 融合界名：" + dec["fused"],
        "  " + dec["verdict"],
        "",
    ]

    # —— 结论 ——
    score = 0
    for kw in rd.RISK_KEYWORDS:
        if kw in dec["primary_name"]:
            score += 14
    for kw in rd.SAFE_KEYWORDS:
        if kw in dec["primary_name"]:
            score -= 16
    score += int(jia / max(1, len(s)) * 50)        # 假越多越虚浮
    score -= int(zhen / max(1, len(s)) * 20)        # 真打底，降浊
    score += int(dec["dirty"] / max(1, len(s)) * 25)
    score = max(0, min(100, score))

    tf_tag = "真打底，根稳" if (lead == "1" and zhen >= jia) else \
             ("假根虚浮，慎" if jia > zhen else "真假相杂")
    lines += [
        "══════ 结论 ══════",
        "主导界：{}".format(dec["primary_txt"]),
        "真假底色：{} —— {}".format(tf_verdict, tf_tag),
        "危险等级：{}/100 —— {}".format(score, danger_level(score)),
        "武秀琴：真的不要追，假的不要信；如如不动，化掉假的，剩下全是真。",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 字母解析：把一串字母翻成精神探索字母界
# ---------------------------------------------------------------------------
def decode_letters(text):
    lines = []
    for ch in text.upper():
        if ch in rd.LETTERS:
            tag = ""
            if ch in rd.LETTER_GOOD:
                tag = "  ·偏真/善"
            elif ch in rd.LETTER_DARK:
                tag = "  ·偏暗/反"
            lines.append("  {} → {}{}".format(ch, rd.LETTERS[ch], tag))
    return "\n".join(lines) if lines else "  （无可识别字母）"


# 灰是典型背景色/中间态，判界时当背景剔除（展示调色板仍照实保留）
BACKGROUND_CATS = {"灰"}


def subject_palette(palette):
    """抓主体：剔除背景灰与零碎噪点，留下真正定界的主体色。
    若全是背景（整幅灰），则回退用原始调色板。"""
    subj = [p for p in palette
            if p["cat"] not in BACKGROUND_CATS and p["ratio"] >= 0.04]
    return subj if subj else (palette[:] or [])


# ---------------------------------------------------------------------------
# 由图片主色推一个「界号」+ 字母（基于主体色，而非背景面积）
# ---------------------------------------------------------------------------
def _norm_cat(cat):
    """把 浅绿 归并到 绿 来参与组合判定（魔小孩仍是绿系魔）。"""
    return "绿" if cat == "浅绿" else cat

def realm_from_palette(palette, path):
    subj = subject_palette(palette)
    if not subj:
        return 3, "N", "白", "默认人间"

    top_cats = [p["cat"] for p in subj[:4]]
    main = top_cats[0]
    norm_top = {_norm_cat(c) for c in top_cats}
    dom = _norm_cat(main)

    # 1) 按有序颜色规则逐条匹配（先具体后宽泛，支持主导色 dom）
    for rule in rd.COLOR_RULES:
        if rule["need"].issubset(norm_top):
            if rule.get("dom") and rule["dom"] != dom:
                continue
            letter = rd.COLOR_TO_LETTER.get(main, "N")
            return rule["realm"], letter, main, rule["desc"]

    # 2) 没命中组合：按主体主色家族 + 图片指纹挑子界
    base, candidates = rd.COLOR_FAMILY.get(main, (3, [3]))
    digest = hashlib.md5(path.encode("utf-8", "ignore")).hexdigest()
    idx = int(digest[:8], 16) % len(candidates)
    num = candidates[idx]
    letter = rd.COLOR_TO_LETTER.get(main, "N")
    desc = "{}（{}）单主色 → {}".format(main, rd.COLOR_MEANING.get(main, ""), rd.realm_name(num))
    return num, letter, main, desc


# ---------------------------------------------------------------------------
# 危险指数：连接此界有多伤身（0~100）
# ---------------------------------------------------------------------------
def danger_index(realm_num, palette):
    name = rd.realm_name(realm_num)
    score = 0
    hits = []

    # 名称关键词
    for kw in rd.RISK_KEYWORDS:
        if kw in name:
            score += 14
            hits.append("界名含「{}」".format(kw))
    for kw in rd.SAFE_KEYWORDS:
        if kw in name:
            score -= 18
            hits.append("界名含「{}」(+安)".format(kw))

    # 偶数位规律：带 2/4/6/8 的界 = 不平衡
    for d in str(realm_num):
        if d in rd.DIRTY_DIGITS:
            score += 8
    if any(d in rd.DIRTY_DIGITS for d in str(realm_num)):
        hits.append("界号含 2/4/6/8 → 不平衡")

    # 颜色：黑越多越危，灰=阳丧尸亦浊，白越多越安
    for p in palette:
        if p["cat"] == "黑":
            score += int(p["ratio"] * 40)
            if p["ratio"] > 0.2:
                hits.append("黑色占比高 → 丧尸/法老气（一切集合·主阴）")
        elif p["cat"] == "灰":
            score += int(p["ratio"] * 22)
            if p["ratio"] > 0.3:
                hits.append("灰色占比高 → 阳丧尸浊气")
        elif p["cat"] == "白":
            score -= int(p["ratio"] * 25)
        elif p["cat"] == "金":
            hits.append("金 → 主财之界（中性，不增浊）")

    score = max(0, min(100, score))
    return score, hits


# ---------------------------------------------------------------------------
# 维度分析：把图片显著颜色翻成维度数字串（如 1122），再整合解码
#   规律沿用十进制：含 2/4/6/8 的位 = 不平衡；0 = 外循环（人世间）。
# ---------------------------------------------------------------------------
def dimension_analysis(palette):
    prominent = [p for p in palette if p["ratio"] >= 0.08][:5]
    if not prominent:
        prominent = palette[:1]

    rows, digits = [], []
    for p in prominent:
        d = rd.COLOR_TO_DIGIT.get(p["cat"])
        if d is None:
            continue
        digits.append(str(d))
        rows.append({
            "cat": p["cat"], "digit": d, "ratio": p["ratio"],
            "meaning": rd.DIGIT_MEANING.get(str(d), "未知"),
        })

    num_str = "".join(digits) or "0"
    num_int = int(num_str)
    dim_count = len(rows)                       # 颜色维度数（几维）
    dirty = sum(1 for ch in num_str if ch in rd.DIRTY_DIGITS)
    has_zero = "0" in num_str

    # 整体维度落界：1~150 查字典；大数则最大位（最显著色）压最小位
    if 0 <= num_int <= rd.MAX_REALM:
        whole = "{} {}".format(num_int, rd.realm_name(num_int))
    else:
        lead = num_str[0]
        whole = "首位 {}→{} 主导（最显著色压一切）｜{}维".format(
            lead, rd.REALMS.get(int(lead), "未知"), dim_count)

    if dirty >= max(2, dim_count - 1):
        verdict = "{}维·浊重（{}个不平衡位）—— 混乱/肮脏界倾向".format(dim_count, dirty)
    elif dirty == 0:
        verdict = "{}维·清（无 2/4/6/8）—— 偏平衡".format(dim_count)
    else:
        verdict = "{}维·半浊（{}个不平衡位）—— 需谨慎".format(dim_count, dirty)
    if has_zero:
        verdict += " · 含 0：外循环大循环（人世间）"

    return {
        "rows": rows, "num_str": num_str, "num_int": num_int,
        "dim_count": dim_count, "dirty": dirty,
        "whole_realm": whole, "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# 合并结论：颜色合并界 + 维度整合 + 危险等级
# ---------------------------------------------------------------------------
def danger_level(score):
    if score < 33:
        return "清净 · 近人间（可安心，化掉即连）"
    if score < 66:
        return "有浊 · 需谨慎（务必先如如不动）"
    return "重浊 · 伤身（非如如不动不可连接）"


def build_conclusion(res):
    dim = res["dimension"]
    lines = [
        "物品所属：{} {}".format(res["realm_num"], res["realm_name"]),
        "颜色合并界：{}".format(res["realm_desc"]),
        "维度数：{}（{}维）→ {}".format(dim["num_str"], dim["dim_count"], dim["whole_realm"]),
        "维度判语：{}".format(dim["verdict"]),
        "危险等级：{}/100 —— {}".format(res["danger"], danger_level(res["danger"])),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 总入口：分析一张图片，返回结构化结果
# ---------------------------------------------------------------------------
def analyze_image(path):
    palette, size = extract_palette(path)
    realm_num, letter, subject_cat, realm_desc = realm_from_palette(palette, path)
    realm_nm = rd.realm_name(realm_num)
    num_detail, num_verdict = decode_number(realm_num)
    # 危险只看主体色（剔除背景灰），与判界一致
    subj = subject_palette(palette)
    danger, hits = danger_index(realm_num, subj or palette)
    dim = dimension_analysis(palette)
    ocr_info = ocr_extract(path)

    res = {
        "size": size,
        "palette": palette,
        "subject_cat": subject_cat,
        "realm_num": realm_num,
        "realm_name": realm_nm,
        "realm_desc": realm_desc,
        "letter": letter,
        "letter_name": rd.LETTERS.get(letter, ""),
        "num_detail": num_detail,
        "num_verdict": num_verdict,
        "danger": danger,
        "danger_hits": hits,
        "dimension": dim,
        "ocr": ocr_info,
    }
    res["conclusion"] = build_conclusion(res)
    return res


# ---------------------------------------------------------------------------
# OCR：读图中真实的数字与字母，并各自解码
# ---------------------------------------------------------------------------
def ocr_extract(path):
    try:
        import ocr as _ocr
    except Exception:
        return {"available": False, "numbers": [], "letters": [], "raw": ""}
    if not _ocr.available():
        return {"available": False, "numbers": [], "letters": [], "raw": ""}

    text = _ocr.ocr_text(path, "en")
    tok = _ocr.extract_tokens(text)

    numbers = []
    for n in tok["numbers"]:
        dec = decode_ocr_number(n)
        if dec:
            numbers.append(dec)

    letter_lines = decode_letters(tok["single_letters"]) if tok["single_letters"] else ""

    return {
        "available": True,
        "raw": tok["raw"],
        "numbers": numbers,
        "letters": tok["letters"],
        "single_letters": tok["single_letters"],
        "letter_decode": letter_lines,
    }


# ===========================================================================
# 界域字典帮助：每界自动生成「模拟色带」缩略图
# ===========================================================================

# 颜色类 -> 代表 RGB（与主程序的颜色体系一致）
_CAT_RGB = {
    "白":   (245, 245, 245),
    "红":   (200, 35, 35),
    "绿":   (35, 160, 60),
    "浅绿": (175, 230, 175),
    "蓝":   (50, 100, 200),
    "黑":   (22, 22, 22),
    "黄":   (240, 215, 60),
    "金":   (212, 175, 55),
    "紫":   (140, 80, 180),
    "灰":   (135, 135, 135),
    "橙":   (230, 130, 40),
    "青":   (60, 180, 180),
    "粉":   (230, 160, 180),
}

# 关键词 -> (颜色, 权重)：按界名的语义味道推主色
#   注：魔界单独处理（绿黑红 / 完整版绿白红），见 realm_color_recipe。
_KW_RULES = [
    (("地狱", "鬼", "丧尸", "僵尸", "诅咒", "法老"), "黑", 0.55),
    (("机械",),                                     "灰", 0.50),
    (("虚拟", "想象"),                              "青", 0.50),
    (("天使",),                                     "白", 0.50),     # 天使 = 白
    (("龙兽", "异兽", "仙兽"),                      "橙", 0.50),
    (("仙佛", "佛"),                                "紫", 0.50),
    (("人间", "均衡", "天堂"),                      "白", 0.50),
    (("女", "母", "阴"),                            "粉", 0.30),
    (("财", "文星", "文曲"),                        "金", 0.45),
    (("太阳", "阳"),                                "黄", 0.30),
    (("假", "诈"),                                  "灰", 0.30),
    (("乱", "战"),                                  "红", 0.35),
    (("永恒",),                                     "红", 0.30),
    (("无色",),                                     "白", 0.85),
    (("无情",),                                     "蓝", 0.25),
    (("雷", "雷暴", "雷神"),                         "黑", 0.35),     # 雷云压顶
    (("雨", "雨水", "雨神"),                         "蓝", 0.40),     # 雨色
    (("拯救",),                                     "蓝", 0.20),
]


def _renjian_fade(num):
    """人间淡化系数：界号越大（越高维）越接近 1（全彩越淡，向白褪）。
       基础人间(3)=0；天上人间(13)≈0.22；真天堂人间(33)≈0.42；真天人间(13x)≈0.9。"""
    if num <= 9:
        return 0.0
    return min(0.9, ((num - 3) / 130.0) ** 0.6)


def realm_color_recipe(num, name):
    """根据界号 + 界名，推出一组 (颜色类, 占比) —— 用于画模拟色带。"""
    w = {}
    for kws, cat, weight in _KW_RULES:
        if any(k in name for k in kws):
            w[cat] = w.get(cat, 0) + weight

    # 魔界三色：默认 绿黑红（暗魔界本色）；
    #   若界名含 白/完整/美好/Amelie，则为完整版 绿白红（如 43 Amelie 界）。
    if "魔" in name:
        w["绿"] = w.get("绿", 0) + 0.45
        w["红"] = w.get("红", 0) + 0.22
        if any(k in name for k in ("白", "完整", "美好", "Amelie", "amelie")):
            w["白"] = w.get("白", 0) + 0.25     # 绿白红
        else:
            w["黑"] = w.get("黑", 0) + 0.25     # 绿黑红

    # 数字规律叠色
    s = str(num)
    for d in s:
        if d == "0":
            w["白"] = w.get("白", 0) + 0.12       # 外循环 = 人世间灰白底
        elif d in "2468":
            w["黑"] = w.get("黑", 0) + 0.07       # 浊
        elif d == "1":
            w["白"] = w.get("白", 0) + 0.05       # 真之根
    # 真天/天上系列加白
    if any(p in name for p in ("真天", "真仙", "真假真", "天上")):
        w["白"] = w.get("白", 0) + 0.10

    # 带3=人：电视检测信号（人间/人界/人性，地狱除外）。越高维全彩越淡，向天道白光褪
    if ("地狱" not in name) and any(k in name for k in ("人间", "人界", "人性", "均衡")):
        f = _renjian_fade(num)
        base = max(0.05, 1 - f)
        w = {"白": 1 + 6 * f}
        for c in ("黄", "青", "绿", "红", "蓝"):
            w[c] = base
        if f > 0.45:
            w["黑"] = 0.12                                   # 高维露出底部黑参考块
    # 地狱 = 黑红，无白（黑底红点）
    if "地狱" in name:
        w.pop("白", None)
        w["黑"] = w.get("黑", 0) + 0.6
        w["红"] = w.get("红", 0) + 0.3

    if num == 0:
        w = {"白": 0.6, "灰": 0.4}                # 外循环
    if not w:
        w["白"] = 1.0

    total = sum(w.values())
    items = [(c, v / total) for c, v in w.items()]
    items.sort(key=lambda x: -x[1])
    return items


# 主题 -> 象征图标：按界名关键词挑一个母题画在图上
_MOTIF_RULES = [
    (("雷", "雨", "雷暴", "雷神", "雨神"), "storm"),    # 真天无情界：雷雨雷暴 + 闪电
    (("Amelie", "amelie"),             "amelie"),     # 绿白红 + 小全色检测 + 小黑方块
    (("地狱",),                        "hell"),       # 黑底红点
    (("人间", "人界", "人性", "均衡"), "testcard"),   # 带3=人：电视检测信号（最中·均衡）
    (("法老", "诅咒"),                 "pharaoh"),
    (("丧尸", "僵尸", "鬼"),           "curse"),
    (("机械",),                        "gear"),
    (("虚拟", "想象"),                 "pixel"),
    (("天使",),                        "wing"),
    (("太阳", "阳"),                   "sun"),
    (("龙兽", "异兽", "仙兽"),         "scale"),
    (("仙佛", "佛"),                   "halo"),
    (("魔",),                          "flame"),
    (("女", "母", "阴"),               "curve"),
    (("财", "文星", "文曲"),           "coin"),
    (("无色", "九九"),                 "void"),
]


def _realm_motif(name):
    for kws, key in _MOTIF_RULES:
        if any(k in name for k in kws):
            return key
    return "calm"


def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _draw_badge(d, num):
    label = str(num)
    d.rectangle([0, 0, 8 + 7 * len(label), 13], fill=(255, 255, 255))
    d.text((3, 1), label, fill=(20, 20, 20))


def _draw_mini_testcard(d, x0, y0, w, h):
    """在 (x0,y0,w,h) 内画一小块电视全色检测（含底部小黑方块）。"""
    bars = [(235, 235, 235), (230, 225, 50), (40, 220, 220), (40, 200, 60),
            (220, 60, 210), (220, 50, 50), (50, 70, 220)]
    th = int(h * 0.68)
    bw = w / len(bars)
    for i, c in enumerate(bars):
        d.rectangle([x0 + int(i * bw), y0, x0 + int((i + 1) * bw), y0 + th], fill=c)
    d.rectangle([x0, y0 + th, x0 + w, y0 + h], fill=(235, 235, 235))   # 底白
    sq = max(4, int(h * 0.20))
    d.rectangle([x0 + w // 2 - sq // 2, y0 + h - sq - 1,
                 x0 + w // 2 + sq // 2, y0 + h - 1], fill=(12, 12, 12))  # 小黑方块
    d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], outline=(50, 50, 50))


def make_realm_thumbnail(num, name, size=(120, 70)):
    """画一张该界的「模拟图」：竖向渐变背景 + 主题象征图标。
       人间 → 电视全色检测彩条；地狱 → 黑底红点。"""
    W, H = size
    motif0 = _realm_motif(name)

    # —— Amelie 界：主调绿白红 + 角落小全色检测 + 小黑方块（小人间藏其中） ——
    if motif0 == "amelie":
        img = Image.new("RGB", size, (245, 245, 245))
        d = ImageDraw.Draw(img)
        third = W // 3
        d.rectangle([0, 0, third, H], fill=_CAT_RGB["绿"])
        d.rectangle([third, 0, 2 * third, H], fill=(245, 245, 245))
        d.rectangle([2 * third, 0, W, H], fill=_CAT_RGB["红"])
        mw, mh = int(W * 0.34), int(H * 0.52)               # 右下角小全色检测
        _draw_mini_testcard(d, W - mw - 5, H - mh - 5, mw, mh)
        d.rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0))
        _draw_badge(d, num)
        return img

    # —— 人间：电视全色检测信号；越高维全彩越淡（向天道白光褪） ——
    if motif0 == "testcard":
        f = _renjian_fade(num)
        white = (248, 248, 246)
        img = Image.new("RGB", size, white)
        d = ImageDraw.Draw(img)
        bars = [(235, 235, 235), (230, 225, 50), (40, 220, 220), (40, 200, 60),
                (220, 60, 210), (220, 50, 50), (50, 70, 220)]   # 白黄青绿品红蓝
        topH = int(H * 0.72)
        bw = W / len(bars)
        for i, c in enumerate(bars):
            d.rectangle([int(i * bw), 0, int((i + 1) * bw), topH],
                        fill=_lerp(c, white, f))                # 越高维越淡
        # 底栏：暗 PLUGE → 随 f 褪成白；中央始终一个黑参考方块
        botc = _lerp((22, 22, 30), white, f)
        d.rectangle([0, topH, W, H], fill=botc)
        sq = 14
        by = topH + (H - topH - sq) // 2
        d.rectangle([int(W / 2 - sq / 2), by, int(W / 2 + sq / 2), by + sq], fill=(12, 12, 12))
        d.rectangle([0, 0, W - 1, H - 1],
                    outline=(180, 180, 178) if f > 0.5 else (0, 0, 0))
        _draw_badge(d, num)
        return img

    # —— 地狱：黑底红点 ——
    if motif0 == "hell":
        img = Image.new("RGB", size, (12, 8, 8))
        d = ImageDraw.Draw(img)
        # 确定性散布的红点（用界号做种子，避免 random）
        seed = (num * 2654435761) & 0xFFFFFFFF
        for _ in range(16):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            px = 6 + seed % (W - 12)
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            py = 14 + seed % (H - 20)
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            r = 1 + seed % 3
            d.ellipse([px - r, py - r, px + r, py + r], fill=(200, 30, 30))
        d.rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0))
        _draw_badge(d, num)
        return img

    recipe = realm_color_recipe(num, name)
    top = _CAT_RGB.get(recipe[0][0], (200, 200, 200))
    bot = _CAT_RGB.get(recipe[1][0], None) if len(recipe) > 1 else None
    if bot is None:
        bot = tuple(max(0, int(c * 0.55)) for c in top)   # 单色 → 自身压暗作渐变

    img = Image.new("RGB", size, top)
    d = ImageDraw.Draw(img)
    # 竖向渐变
    for y in range(H):
        d.line([(0, y), (W, y)], fill=_lerp(top, bot, y / max(1, H - 1)))
    # 若有第三色，右侧一道窄竖带点缀
    if len(recipe) > 2:
        c3 = _CAT_RGB.get(recipe[2][0], (180, 180, 180))
        d.rectangle([W - 10, 0, W, H], fill=c3)

    cx, cy = int(W * 0.62), int(H * 0.52)
    motif = _realm_motif(name)
    light = (250, 248, 235)
    dark = (15, 15, 15)

    if motif == "storm":
        # 真天无情界：乌云压顶 + 雨丝 + 黄色闪电
        d.rectangle([0, 0, W, int(H * 0.40)], fill=(38, 46, 62))
        for rx in range(6, W, 9):
            d.line([(rx, int(H * 0.42)), (rx - 4, H - 4)], fill=(120, 150, 205), width=1)
        bolt = [(cx, cy - 15), (cx - 8, cy + 2), (cx - 1, cy + 2), (cx - 6, cy + 16),
                (cx + 10, cy - 4), (cx + 2, cy - 4)]
        d.polygon(bolt, fill=(252, 226, 70))
        d.rectangle([0, 0, W - 1, H - 1], outline=(10, 12, 20))
        _draw_badge(d, num)
        return img
    elif motif == "sun":
        d.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(255, 225, 90))
        for a in range(0, 360, 45):
            import math
            dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
            d.line([(cx + dx * 14, cy + dy * 14), (cx + dx * 20, cy + dy * 20)],
                   fill=(255, 225, 90), width=2)
    elif motif == "wing":
        wcol = (150, 175, 220)   # 天使界=白底，翼用淡蓝才看得见
        d.ellipse([cx - 14, cy - 10, cx + 2, cy + 10], outline=wcol, width=2)
        d.ellipse([cx - 2, cy - 10, cx + 14, cy + 10], outline=wcol, width=2)
        d.ellipse([cx - 3, cy - 14, cx + 3, cy - 8], fill=(225, 200, 120))  # 金头光
    elif motif == "halo":
        for r in (16, 11, 6):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(245, 235, 200), width=1)
        d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 245, 210))
    elif motif == "gear":
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], outline=(225, 225, 225), width=3)
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(60, 60, 60))
        for a in range(0, 360, 45):
            import math
            dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
            d.rectangle([cx + dx * 13 - 2, cy + dy * 13 - 2,
                         cx + dx * 13 + 2, cy + dy * 13 + 2], fill=(225, 225, 225))
    elif motif == "pixel":
        for gx in range(cx - 14, cx + 15, 7):
            for gy in range(cy - 14, cy + 15, 7):
                if (gx + gy) % 14 == 0:
                    d.rectangle([gx, gy, gx + 5, gy + 5], fill=(150, 240, 240))
    elif motif == "flame":
        d.polygon([(cx, cy - 16), (cx + 10, cy + 12), (cx - 10, cy + 12)], fill=(40, 180, 70))
        d.polygon([(cx, cy - 6), (cx + 5, cy + 12), (cx - 5, cy + 12)], fill=(210, 60, 60))
    elif motif == "pharaoh":
        # 金面具 + 裂纹
        d.polygon([(cx - 11, cy - 12), (cx + 11, cy - 12), (cx + 8, cy + 14),
                   (cx, cy + 18), (cx - 8, cy + 14)], fill=(212, 175, 55))
        d.line([(cx - 5, cy - 2), (cx - 5, cy + 8)], fill=dark, width=1)
        d.line([(cx + 5, cy - 2), (cx + 5, cy + 8)], fill=dark, width=1)
        d.line([(cx - 14, cy - 14), (cx - 4, cy + 16)], fill=(0, 0, 0), width=1)  # 裂纹
    elif motif == "curse":
        d.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(35, 35, 35))
        d.line([(cx - 7, cy - 5), (cx - 2, cy)], fill=(200, 40, 40), width=2)
        d.line([(cx + 7, cy - 5), (cx + 2, cy)], fill=(200, 40, 40), width=2)
        d.arc([cx - 6, cy + 2, cx + 6, cy + 12], 200, 340, fill=(200, 40, 40), width=1)
    elif motif == "scale":
        for ry in range(cy - 12, cy + 13, 7):
            for rx in range(cx - 12, cx + 13, 10):
                d.arc([rx, ry, rx + 10, ry + 10], 180, 360, fill=(120, 70, 30), width=2)
    elif motif == "curve":
        d.arc([cx - 12, cy - 6, cx, cy + 14], 0, 200, fill=(235, 170, 190), width=3)
        d.arc([cx, cy - 6, cx + 12, cy + 14], 340, 180, fill=(235, 170, 190), width=3)
    elif motif == "coin":
        d.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(212, 175, 55),
                  outline=(160, 120, 20), width=2)
        d.text((cx - 3, cy - 6), "金", fill=(120, 80, 10))
    elif motif == "void":
        d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], outline=(210, 210, 210), width=2)
    else:  # calm / 人间
        d.line([(cx - 16, cy + 4), (cx + 16, cy + 4)], fill=light, width=1)
        d.ellipse([cx + 4, cy - 14, cx + 14, cy - 4], outline=light, width=1)

    # 立体感 + 界号角标
    d.rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0))
    label = str(num)
    d.rectangle([0, 0, 8 + 7 * len(label), 13], fill=(255, 255, 255))
    d.text((3, 1), label, fill=(20, 20, 20))
    return img
