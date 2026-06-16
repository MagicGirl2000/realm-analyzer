# -*- coding: utf-8 -*-
"""gen_flags.py — 预渲染各维度「分界模拟图」PNG，打包进安卓 assets/realmflags/。
悬浮窗按算出的维度直接加载对应旗子，和电脑版一致。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realm_data as rd
import analyzer

OUT = r"C:\Users\victo\AndroidStudioProjects\RealmAnalyzer\app\src\main\assets\realmflags"
os.makedirs(OUT, exist_ok=True)
SIZE = (180, 108)   # 5:3 旗形

n = 0
for num in range(0, 201):
    name = rd.realm_name(num)
    img = analyzer.make_realm_thumbnail(num, name, size=SIZE)
    img.save(os.path.join(OUT, "r%d.png" % num))
    n += 1
print("生成 %d 张分界旗 → %s" % (n, OUT))
