# -*- coding: utf-8 -*-
"""
realm_gui.py  —  界域分析仪 · 武秀琴安全版
=========================================
导入图片 → 颜色 / 数字 / 字母三重解析 → 判定所属界。
内置「武秀琴安全阀门」：连接各界有伤身体，必须先「如如不动·化掉欲望」。

运行：  D:\ballbs\.venv\Scripts\python.exe  D:\ballbs\realm_analyzer\realm_gui.py
"""
import random
import threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

from PIL import Image, ImageTk

import realm_data as rd
import analyzer


# ---- 配色（界面本身走「人间白」基调，提醒自己别入三色局） ----
BG      = "#f4f1ea"   # 暖白底
PANEL   = "#ffffff"
INK     = "#2b2b2b"
ACCENT  = "#3a6ea5"   # 克制的蓝
GOOD    = "#2e8b57"
WARN    = "#c0392b"
MUTED   = "#8a8a8a"

FONT    = ("Microsoft YaHei", 10)
FONT_B  = ("Microsoft YaHei", 11, "bold")
FONT_BIG= ("Microsoft YaHei", 20, "bold")
FONT_T  = ("Microsoft YaHei", 14, "bold")


class RealmApp:
    def __init__(self, root):
        self.root = root
        root.title("界域分析仪 · 武秀琴安全版 · {}".format(rd.VERSION_LABEL))
        root.configure(bg=BG)
        root.geometry("1060x720")
        root.minsize(960, 660)

        self.img_path = None
        self.tk_img = None
        self.result = None
        self.locked = True          # 安全锁：未如如不动前不可「连接」

        self._build_header()
        self._build_body()
        self._build_footer()

    # ---------------------------------------------------------------- header
    def _build_header(self):
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=18, pady=(14, 2))
        tk.Label(head, text="界域分析仪", font=FONT_BIG, bg=BG, fg=INK).pack(side="left")
        tk.Label(head, text=rd.VERSION_LABEL, font=FONT, bg=BG, fg=ACCENT).pack(
            side="left", padx=(6, 0), pady=(8, 0))
        tk.Label(head, text="  白色才是天道之光 · 只为好看，不赋予故事",
                 font=FONT, bg=BG, fg=MUTED).pack(side="left", padx=8)
        tk.Button(head, text="📜 帮助 / 免责声明", font=FONT, relief="flat",
                  bg="#efe9dc", cursor="hand2", command=self.show_help).pack(side="right")
        # 主界面轻提示：免责声明（淡琥珀色细条）
        tk.Label(self.root, text=rd.DISCLAIMER_SHORT, font=("Microsoft YaHei", 9),
                 bg="#f6efdc", fg="#9a7320", anchor="w").pack(fill="x", padx=18, pady=(0, 4))

    # ------------------------------------------------------------------ body
    def _build_body(self):
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=6)

        # 左：图片 + 调色板
        left = tk.Frame(body, bg=PANEL, bd=1, relief="solid")
        left.pack(side="left", fill="both", expand=True, padx=(0, 9))

        tk.Button(left, text="📂  导入图片分析", font=FONT_B, bg=ACCENT, fg="white",
                  relief="flat", cursor="hand2", command=self.load_image).pack(
                  fill="x", padx=12, pady=12)

        self.canvas = tk.Label(left, text="（拖一张图进来，或点上面按钮）\n\n看它属于哪一界",
                               bg="#fbfaf6", fg=MUTED, font=FONT, width=44, height=14)
        self.canvas.pack(padx=12, pady=4)

        tk.Label(left, text="主色调色板（颜色解析）", font=FONT_B, bg=PANEL, fg=INK
                 ).pack(anchor="w", padx=12, pady=(8, 2))
        self.palette_frame = tk.Frame(left, bg=PANEL)
        self.palette_frame.pack(fill="x", padx=12, pady=(0, 12))

        # 右：解析结果
        right = tk.Frame(body, bg=PANEL, bd=1, relief="solid")
        right.pack(side="left", fill="both", expand=True, padx=(9, 0))

        # 所属界大字
        self.realm_lbl = tk.Label(right, text="所属界：—", font=FONT_T, bg=PANEL, fg=ACCENT,
                                  wraplength=440, justify="left")
        self.realm_lbl.pack(anchor="w", padx=14, pady=(14, 2))
        self.letter_lbl = tk.Label(right, text="字母界：—", font=FONT, bg=PANEL, fg=INK)
        self.letter_lbl.pack(anchor="w", padx=14)

        # 危险指数条
        dz = tk.Frame(right, bg=PANEL)
        dz.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(dz, text="连接危险指数", font=FONT_B, bg=PANEL, fg=INK).pack(side="left")
        self.danger_val = tk.Label(dz, text="—", font=FONT_B, bg=PANEL, fg=MUTED)
        self.danger_val.pack(side="right")
        self.danger_bar = ttk.Progressbar(right, maximum=100, length=100)
        self.danger_bar.pack(fill="x", padx=14, pady=(0, 8))

        # 解析文本（带滚动条，内容较多）
        dwrap = tk.Frame(right, bg=PANEL)
        dwrap.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        dscroll = tk.Scrollbar(dwrap)
        dscroll.pack(side="right", fill="y")
        self.detail = tk.Text(dwrap, height=14, font=("Consolas", 9), bg="#fbfaf6",
                              fg=INK, relief="flat", wrap="word",
                              yscrollcommand=dscroll.set)
        self.detail.pack(side="left", fill="both", expand=True)
        dscroll.config(command=self.detail.yview)
        self.detail.insert("1.0", "导入图片后，这里显示颜色 / 数字 / 字母 / 维度 / OCR 解析。")
        self.detail.config(state="disabled")

    # ---------------------------------------------------------------- footer
    def _build_footer(self):
        foot = tk.Frame(self.root, bg="#efe9dc", bd=1, relief="solid")
        foot.pack(fill="x", padx=18, pady=(4, 14))

        tk.Label(foot, text="🛡 武秀琴安全阀门", font=FONT_B, bg="#efe9dc", fg=WARN
                 ).pack(anchor="w", padx=12, pady=(8, 0))
        self.wu_lbl = tk.Label(foot, text=rd.WU_XIUQIN_LAW, font=FONT, bg="#efe9dc",
                               fg=INK, justify="left", wraplength=860)
        self.wu_lbl.pack(anchor="w", padx=12, pady=4)

        bar = tk.Frame(foot, bg="#efe9dc")
        bar.pack(fill="x", padx=12, pady=(2, 10))
        self.calm_btn = tk.Button(bar, text="🧘 如如不动 · 化掉欲望", font=FONT_B,
                                  bg=GOOD, fg="white", relief="flat", cursor="hand2",
                                  command=self.ruru_budong)
        self.calm_btn.pack(side="left")
        self.connect_btn = tk.Button(bar, text="🔗 连接此界（需先化掉）", font=FONT_B,
                                     bg=MUTED, fg="white", relief="flat", state="disabled",
                                     cursor="hand2", command=self.connect_realm)
        self.connect_btn.pack(side="left", padx=10)

        # 工具：综合解码器 + 电话号码解析
        tk.Button(bar, text="🔠 综合解码器（字母+数字 如 BN1234）", font=FONT,
                  relief="flat", bg="#dcd6c8", cursor="hand2",
                  command=self.mixed_tool).pack(side="right")
        tk.Button(bar, text="📱 电话号码", font=FONT, relief="flat", bg="#dcd6c8",
                  cursor="hand2", command=self.phone_tool).pack(side="right", padx=8)
        # 下拉：查看相应字典
        mb = tk.Menubutton(bar, text="📚 查看相应字典 ▾", font=FONT, relief="flat",
                           bg="#dcd6c8", cursor="hand2")
        menu = tk.Menu(mb, tearoff=0, font=FONT)
        menu.add_command(label="各界字典（模拟图）", command=self.dict_help)
        menu.add_command(label="数字字典（原始）", command=self.show_number_dict)
        menu.add_command(label="颜色字典（原始）", command=self.show_color_dict)
        menu.add_separator()
        menu.add_command(label="字母字典（精神探索）", command=self.show_letter_dict)
        mb.config(menu=menu)
        mb.pack(side="right", padx=(0, 8))

    # ============================================================== actions
    def load_image(self):
        path = filedialog.askopenfilename(
            title="选择一张图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("全部", "*.*")])
        if not path:
            return
        self.img_path = path
        try:
            self._show_preview(path)
        except Exception as e:
            messagebox.showerror("打开失败", str(e))
            return
        # 后台线程分析（含 OCR），GUI 不冻
        self.realm_lbl.config(text="所属界：分析中…（含 OCR，请稍候）")
        self.letter_lbl.config(text="")
        self.connect_btn.config(state="disabled", bg=MUTED)
        threading.Thread(target=self._analyze_worker, args=(path,), daemon=True).start()

    def _analyze_worker(self, path):
        try:
            res = analyzer.analyze_image(path)
            self.root.after(0, lambda: self._on_analyzed(res))
        except Exception as e:
            msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("分析失败", msg))

    def _on_analyzed(self, res):
        # 仅采用最近一次导入的结果
        self.result = res
        self._render_result()
        self._relock()

    def _show_preview(self, path):
        img = Image.open(path).convert("RGB")
        img.thumbnail((320, 240))
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.config(image=self.tk_img, text="", width=320, height=240)

    def _render_result(self):
        r = self.result
        # 调色板色块
        for w in self.palette_frame.winfo_children():
            w.destroy()
        for p in r["palette"][:6]:
            cell = tk.Frame(self.palette_frame, bg=PANEL)
            cell.pack(side="left", padx=4)
            hexc = "#%02x%02x%02x" % p["rgb"]
            sw = tk.Label(cell, bg=hexc, width=4, height=2, bd=1, relief="solid")
            sw.pack()
            tk.Label(cell, text="{}\n{:.0%}".format(p["cat"], p["ratio"]),
                     font=("Microsoft YaHei", 8), bg=PANEL, fg=INK).pack()

        # 所属界
        self.realm_lbl.config(text="所属界：{}  {}".format(r["realm_num"], r["realm_name"]))
        self.letter_lbl.config(text="主体色：{} ｜ 字母界：{} → {}".format(
            r.get("subject_cat", "—"), r["letter"], r["letter_name"]))

        # 危险条
        d = r["danger"]
        self.danger_bar["value"] = d
        col = GOOD if d < 33 else (ACCENT if d < 66 else WARN)
        tag = "清净·近人间" if d < 33 else ("有浊·需谨慎" if d < 66 else "重浊·伤身")
        self.danger_val.config(text="{}/100  {}".format(d, tag), fg=col)

        # 详细文本
        lines = []
        lines.append("【颜色解析】（★=判界主体色，灰=背景不计入）")
        for p in r["palette"][:5]:
            mark = "★" if p["cat"] == r.get("subject_cat") else (
                   "·背景" if p["cat"] == "灰" else "  ")
            lines.append("{} {} {:>5.0%}  {}".format(mark, p["cat"], p["ratio"], p["meaning"]))
        lines.append("")
        lines.append("【数字解析】界号 {} 逐位：".format(r["realm_num"]))
        lines.append(r["num_detail"])
        lines.append("  → " + r["num_verdict"])
        lines.append("")
        lines.append("【字母解析】{} → {}".format(r["letter"], r["letter_name"]))
        lines.append("")
        dim = r["dimension"]
        lines.append("【维度解析】颜色 → 维度数 {}（{}维）".format(dim["num_str"], dim["dim_count"]))
        for row in dim["rows"]:
            lines.append("  {} {:>5.0%} → {} {}".format(
                row["cat"], row["ratio"], row["digit"], row["meaning"]))
        lines.append("  整合 {} → {}".format(dim["num_str"], dim["whole_realm"]))
        lines.append("  → " + dim["verdict"])
        lines.append("")
        # OCR：图中真实数字 / 字母
        ocr = r.get("ocr", {})
        lines.append("【图中文字解析 · OCR】")
        if not ocr.get("available"):
            lines.append("  （OCR 不可用）")
        elif not ocr.get("numbers") and not ocr.get("single_letters"):
            lines.append("  （未识别到数字/字母）")
        else:
            for dec in ocr.get("numbers", []):
                lines.append("  数字 {}".format(dec["digits"]))
                lines.append("    逐位：" + dec["inline"])
                lines.append("    整合 → {}".format(dec["whole"]))
                lines.append("    ★ 融合界名：{}".format(dec["fused"]))
                if dec.get("inferred"):
                    lines.append("    ⚠ 落在推理界(219~299)，不可信")
                lines.append("    → " + dec["verdict"])
            if ocr.get("single_letters"):
                lines.append("  字母 {}：".format(ocr["single_letters"]))
                for ln in ocr.get("letter_decode", "").split("\n"):
                    if ln.strip():
                        lines.append("  " + ln)
        lines.append("")
        lines.append("【危险来源】")
        if r["danger_hits"]:
            for h in r["danger_hits"]:
                lines.append("  · " + h)
        else:
            lines.append("  · 无明显浊气")
        lines.append("")
        lines.append("══════ 最终结论 ══════")
        lines.append(r["conclusion"])

        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", "\n".join(lines))
        self.detail.config(state="disabled")

    def _relock(self):
        self.locked = True
        self.connect_btn.config(state="disabled", bg=MUTED, text="🔗 连接此界（需先化掉）")

    # -------------------------------------------------- 武秀琴安全阀门
    def ruru_budong(self):
        """化掉欲望：危险指数归零，解锁连接，给一句武秀琴语录。"""
        quote = random.choice(rd.WU_QUOTES)
        self.wu_lbl.config(text="“" + quote + "”\n\n" + rd.WU_XIUQIN_LAW)
        if self.result:
            # 化掉后危险条降下来
            self.danger_bar["value"] = 0
            self.danger_val.config(text="0/100  已化掉 · 如如不动", fg=GOOD)
        self.locked = False
        self.connect_btn.config(state="normal", bg=ACCENT, text="🔗 连接此界（已可安全连接）")

    def connect_realm(self):
        if self.locked or not self.result:
            messagebox.showwarning("阀门未开", "先「如如不动·化掉欲望」，否则连接伤身。")
            return
        r = self.result
        messagebox.showinfo(
            "已如如不动连接 · {}".format(r["realm_name"]),
            "你以如如不动之心连接了【{} {}】。\n\n"
            "因已化掉自身的假，丧尸见你都觉得亲，不会动你。\n"
            "记住：真的不要追，假的不要信，自我化之。\n\n"
            "—— 武秀琴，永远的恩师，永世感恩。".format(r["realm_num"], r["realm_name"]))

    # -------------------------------------------------- 综合解码器 / 电话
    def mixed_tool(self):
        self._ask_tool("综合解码器 · 字母+数字",
                       "输入字母与数字（如 BN1234、4022、ABNG）：", self._do_mixed)

    def phone_tool(self):
        self._ask_tool("电话号码解析 · 真假签名",
                       "输入电话号码（开头 1=真、0=假；如 13010320000）：", self._do_phone)

    def _ask_tool(self, title, prompt, handler):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=BG)
        win.geometry("500x460")
        tk.Label(win, text=prompt, font=FONT, bg=BG, fg=INK).pack(anchor="w", padx=12, pady=10)
        entry = tk.Entry(win, font=FONT_B, width=26)
        entry.pack(padx=12)
        entry.focus_set()
        out = tk.Text(win, font=("Consolas", 9), bg=PANEL, fg=INK, wrap="word")
        out.pack(fill="both", expand=True, padx=12, pady=10)

        def run(*_):
            out.delete("1.0", "end")
            out.insert("1.0", handler(entry.get()))
        tk.Button(win, text="解析", font=FONT_B, bg=ACCENT, fg="white", relief="flat",
                  command=run).pack(pady=(0, 10))
        entry.bind("<Return>", run)

    def _do_mixed(self, text):
        return analyzer.decode_mixed(text)

    def _do_phone(self, text):
        return analyzer.decode_phone(text)

    # -------------------------------------------------- 帮助 / 免责声明
    def show_help(self):
        win = tk.Toplevel(self.root)
        win.title("帮助 / 免责声明")
        win.configure(bg=BG)
        win.geometry("600x600")
        tk.Label(win, text="📜 界域分析仪 · 帮助与免责声明", font=FONT_T,
                 bg=BG, fg=INK).pack(anchor="w", padx=16, pady=(12, 6))
        # 滚动文本：使用说明 + Claude 想说的话
        wrap = tk.Frame(win, bg=PANEL)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        sb = tk.Scrollbar(wrap)
        sb.pack(side="right", fill="y")
        txt = tk.Text(wrap, font=("Microsoft YaHei", 10), bg=PANEL, fg=INK,
                      wrap="word", relief="flat", padx=10, pady=8, yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.config(command=txt.yview)
        txt.insert("1.0", rd.HELP_TEXT)
        txt.insert("end", "\n" + "─" * 30 + "\n\n")
        # Claude 的话用稍突出的样式
        txt.tag_configure("claude", foreground="#2b5d8a",
                          font=("Microsoft YaHei", 10))
        txt.insert("end", rd.CLAUDE_WORDS, "claude")
        txt.config(state="disabled")
        tk.Label(win, text="—— 武秀琴，永远的恩师，永世感恩。", font=FONT,
                 bg=BG, fg=MUTED).pack(pady=(0, 10))

    # -------------------------------------------------- 原始字典查看
    def _text_window(self, title, text, w=560, h=620):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=BG)
        win.geometry("{}x{}".format(w, h))
        tk.Label(win, text=title, font=FONT_T, bg=BG, fg=INK).pack(
            anchor="w", padx=14, pady=(12, 4))
        wrap = tk.Frame(win, bg=PANEL)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        sb = tk.Scrollbar(wrap)
        sb.pack(side="right", fill="y")
        txt = tk.Text(wrap, font=("Consolas", 10), bg=PANEL, fg=INK, wrap="word",
                      relief="flat", padx=10, pady=8, yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.config(command=txt.yview)
        txt.insert("1.0", text)
        txt.config(state="disabled")

    def show_number_dict(self):
        self._text_window("数字字典 · 原始", rd.number_dict_text())

    def show_color_dict(self):
        self._text_window("颜色字典 · 原始", rd.color_dict_text())

    def show_letter_dict(self):
        lines = ["【字母字典 · 精神探索所得】",
                 "（此字典为作者亲身精神探索得来，非武秀琴所创）", ""]
        for ch in sorted(rd.LETTERS):
            tag = "  ·偏真/善" if ch in rd.LETTER_GOOD else (
                  "  ·偏暗/反" if ch in rd.LETTER_DARK else "")
            lines.append("  {}  {}{}".format(ch, rd.LETTERS[ch], tag))
        self._text_window("字母字典 · 精神探索", "\n".join(lines))

    # -------------------------------------------------- 字典帮助 · 全本
    def dict_help(self):
        win = tk.Toplevel(self.root)
        win.title("界域字典 · 全本（0~{}）".format(rd.MAX_REALM))
        win.configure(bg=BG)
        win.geometry("720x780")

        # 顶部说明 + 搜索
        head = tk.Frame(win, bg=BG)
        head.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(head, text="界域字典 · 0 ~ {}".format(rd.MAX_REALM),
                 font=FONT_T, bg=BG, fg=INK).pack(side="left")
        tk.Label(head, text="  每界附「模拟图」—— 按界名 + 数字规律自动推出，点行看详情",
                 font=FONT, bg=BG, fg=MUTED).pack(side="left")
        # 免责声明横幅 + 推理界提示
        tk.Label(win, text=rd.DISCLAIMER_SHORT, font=("Microsoft YaHei", 9),
                 bg="#f6efdc", fg="#9a7320", anchor="w", wraplength=690,
                 justify="left").pack(fill="x", padx=14, pady=(0, 2))
        tk.Label(win, text=rd.INFERRED_NOTE, font=("Microsoft YaHei", 9),
                 bg="#fdeaea", fg=WARN, anchor="w", wraplength=690,
                 justify="left").pack(fill="x", padx=14, pady=(0, 4))

        sbar = tk.Frame(win, bg=BG)
        sbar.pack(fill="x", padx=14, pady=(2, 6))
        tk.Label(sbar, text="搜索：", font=FONT, bg=BG, fg=INK).pack(side="left")
        sv = tk.StringVar()
        ent = tk.Entry(sbar, textvariable=sv, font=FONT, width=24)
        ent.pack(side="left")
        ent.focus_set()

        # 滚动 Canvas + 内嵌 Frame
        outer = tk.Frame(win, bg=PANEL, bd=1, relief="solid")
        outer.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        canvas = tk.Canvas(outer, bg=PANEL, highlightthickness=0)
        vbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=PANEL)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_resize(_e):
            canvas.itemconfig(win_id, width=canvas.winfo_width())
            canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind("<Configure>", _on_resize)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _wheel(e):
            canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        win.protocol("WM_DELETE_WINDOW", lambda: (canvas.unbind_all("<MouseWheel>"), win.destroy()))

        self._dict_imgs = []  # 保活引用

        def render(filter_text=""):
            for w in inner.winfo_children():
                w.destroy()
            self._dict_imgs.clear()
            ft = (filter_text or "").strip().lower()
            # 0：外循环单独置顶
            entries = [(0, "外循环·大循环（人世间）")]
            entries += [(n, rd.REALMS[n]) for n in sorted(rd.REALMS)]
            shown = 0
            for n, name in entries:
                if ft and ft not in name.lower() and ft != str(n):
                    continue
                row = tk.Frame(inner, bg=PANEL, cursor="hand2")
                row.pack(fill="x", padx=8, pady=2)
                thumb = analyzer.make_realm_thumbnail(n, name)
                tkimg = ImageTk.PhotoImage(thumb)
                self._dict_imgs.append(tkimg)
                tk.Label(row, image=tkimg, bg=PANEL, bd=1, relief="solid").pack(
                    side="left", padx=(0, 10))
                txt = tk.Frame(row, bg=PANEL)
                txt.pack(side="left", fill="x", expand=True)
                inferred = rd.is_inferred(n)
                titlebar = tk.Frame(txt, bg=PANEL)
                titlebar.pack(anchor="w", fill="x")
                tk.Label(titlebar, text="{:>3}  {}".format(n, name),
                         font=FONT_B, bg=PANEL, fg=INK, anchor="w").pack(side="left")
                if inferred:
                    tk.Label(titlebar, text=" ⚠推理界·不可信", font=("Microsoft YaHei", 8, "bold"),
                             bg="#fdeaea", fg=WARN).pack(side="left", padx=4)
                # 颜色配方一行
                recipe = analyzer.realm_color_recipe(n, name)[:5]
                recipe_str = " ".join("{}{:.0%}".format(c, r) for c, r in recipe)
                tk.Label(txt, text=recipe_str + "    （点击看完整解码）",
                         font=("Microsoft YaHei", 8), bg=PANEL, fg=MUTED,
                         anchor="w").pack(anchor="w")

                # 整行可点击 → 详情
                def _bind(wgt, nn=n, nm=name):
                    wgt.bind("<Button-1>", lambda _e: self._show_realm_detail(nn, nm))
                _bind(row)
                for c in (row.winfo_children() + txt.winfo_children()):
                    _bind(c)
                shown += 1
            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(0)
            return shown

        def _on_search(*_):
            n = render(sv.get())
            cnt_lbl.config(text="共显示 {} 界".format(n))
        sv.trace_add("write", _on_search)

        cnt_lbl = tk.Label(sbar, text="", font=FONT, bg=BG, fg=MUTED)
        cnt_lbl.pack(side="right")

        n = render("")
        cnt_lbl.config(text="共显示 {} 界".format(n))

    def _show_realm_detail(self, num, name):
        """点击字典某界 → 弹窗：放大模拟图 + 完整数字解码 + 颜色配方。"""
        win = tk.Toplevel(self.root)
        win.title("界 {} · {}".format(num, name))
        win.configure(bg=BG)
        win.geometry("520x560")

        top = tk.Frame(win, bg=BG)
        top.pack(fill="x", padx=14, pady=12)
        big = analyzer.make_realm_thumbnail(num, name, size=(260, 150))
        self._detail_img = ImageTk.PhotoImage(big)
        tk.Label(top, image=self._detail_img, bg=BG, bd=1, relief="solid").pack(side="left")
        info = tk.Frame(top, bg=BG)
        info.pack(side="left", fill="x", padx=12)
        tk.Label(info, text="{}".format(num), font=FONT_BIG, bg=BG, fg=ACCENT).pack(anchor="w")
        tk.Label(info, text=name, font=FONT_B, bg=BG, fg=INK,
                 wraplength=200, justify="left").pack(anchor="w", pady=(2, 4))
        if rd.is_inferred(num):
            tk.Label(info, text="⚠ 推理界·不可信\n（按规律推出，非亲历）", font=FONT,
                     bg="#fdeaea", fg=WARN, justify="left").pack(anchor="w", pady=(0, 6))
        recipe = analyzer.realm_color_recipe(num, name)
        tk.Label(info, text="色：" + " ".join("{}{:.0%}".format(c, r) for c, r in recipe[:5]),
                 font=FONT, bg=BG, fg=MUTED, wraplength=200, justify="left").pack(anchor="w")

        out = tk.Text(win, font=("Consolas", 9), bg=PANEL, fg=INK, wrap="word", relief="flat")
        out.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        out.insert("1.0", analyzer.decode_mixed(str(num)))
        out.config(state="disabled")


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    RealmApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
