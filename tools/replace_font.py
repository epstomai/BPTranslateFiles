#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
replace_font.py — BLUE PROTOCOL 字体替换工具（简中字库补丁生成器）
================================================================

把游戏的日文复合字体主脸换成一个全覆盖泛 CJK 字体（默认源泉圆体 GenSenRounded2 JP，
OFL，圆体最贴原版 Seurat），解决两件事：
  1) 简体专用字（们/这/说/电/开/戏…）在日文字体里没有字形 → 显示不出来；
  2) 直接换字体后，因竖直度量不同导致文字在按钮里下沉、被裁切。

────────────────────────────────────────────────────────────────
逆向得来的关键要点（务必遵守，否则会踩坑）：
────────────────────────────────────────────────────────────────
1. **.ufont 整文件读取**：UFontFace 的字体负载是分离文件 `.ufont`（就是裸字体文件）。
   实测它的字节大小**不记录在 .uasset/.uexp 里** → 引擎按整个 .ufont 文件读取。
   所以换字体只需替换 `.ufont`，`.uasset`/`.uexp` 原样保留，无需改 asset、零风险。

2. **下沉的真凶 = 字体全局边界框 `head.yMax/yMin`**：UE（经 FreeType `face->bbox`）
   用它决定行高/基线，**不是 hhea**。替身必须把 head.yMax/yMin 改成原字体的值，
   否则文字下沉被裁。（hhea / OS-2 win/typo 也一并对齐以防万一。）

3. **保存 CFF/OTF 字体必须 `recalcBBoxes=False`**：否则 fontTools 在 save() 时会按字形
   轮廓重算 head 边界框，把我们克隆的值覆盖掉 → 下沉复发（CFF/OTF 字体会触发，glyf/TTF 不会）。

4. **游戏有 4 个复合字体**，前 3 个是日文 CJK 脸、需要替换；CenturyGothic 是拉丁脸，不动：
       Content/UI/Font/FontFace/UI_FOT_SeuratProN_DB_Font          (主体 UI, pakchunk0)
       Content/UI/Font/FontFace/UI_FOT-SkipStd-B_Font              (Skip 标题/按钮, pakchunk500)
       Content/UI/Font/FontFace/UI_FOT-UDKakugo_LargePr6-M_Font    (UD 角黑, pakchunk500)
   三脸 hhea/typo 都是 880/-120/1000（相同），仅 bbox(=win) 各不同（脚本会从 orig 读取并对齐）。

5. **生成的 .pak 必须配同名 .sig 才能加载**（dinput8.dll 绕过签名内容校验，但引擎仍要求
   .sig 文件存在）。复用现成的 564B .sig 改名即可，内容不被校验。

────────────────────────────────────────────────────────────────
使用前准备（从你自己的游戏里抽出原始字体脸，勿分发原版商业字体）：
────────────────────────────────────────────────────────────────
用 repak + 游戏 AES key，把 3 个原始脸（各 .uasset/.uexp/.ufont）抽到 ./orig/ ：
    repak --aes-key 0x<KEY> get pakchunk0-WindowsClient.pak  \
        "BLUEPROTOCOL/Content/UI/Font/FontFace/UI_FOT_SeuratProN_DB_Font.uasset" > orig/UI_FOT_SeuratProN_DB_Font.uasset
    （.uexp / .ufont 同理；Skip / UDKakugo 两脸在 pakchunk500-WindowsClient.pak）
源字体放 ./src/（默认找 GenSenRounded2JP-M.otf；OFL，可随补丁分发，
    https://github.com/ButTaiwan/gensen-font ）。

用法：
    python replace_font.py                      # 用默认源字体生成字体包
    python replace_font.py --src src/别的.otf   # 换字体（换 Bold 文件即换字重）
    python replace_font.py --deploy <游戏Paks/~mods目录>   # 生成后直接部署
"""
import os, sys, shutil, argparse, subprocess
from fontTools.ttLib import TTFont
try:
    from fontTools.varLib.instancer import instantiateVariableFont
except Exception:
    instantiateVariableFont = None

HERE   = os.path.dirname(os.path.abspath(__file__))
ORIG   = os.path.join(HERE, "orig")     # 原游戏字体脸(uasset/uexp/ufont), 自行用 repak 抽出
SRC    = os.path.join(HERE, "src")
BUILD  = os.path.join(HERE, "_build")
STAGE  = os.path.join(BUILD, "stage", "BLUEPROTOCOL", "Content", "UI", "Font", "FontFace")
PAKOUT = os.path.join(BUILD, "DStars_font_zh-cn_1_P.pak")
REPAK  = os.environ.get("REPAK") or os.path.expanduser("~/.cargo/bin/repak.exe")
if not os.path.exists(REPAK): REPAK = "repak"

# 需要替换的复合字体【主脸】(都是日文CJK脸, 缺简中)
FACES = [
    "UI_FOT_SeuratProN_DB_Font",
    "UI_FOT-SkipStd-B_Font",
    "UI_FOT-UDKakugo_LargePr6-M_Font",
]

def make_base(src, weight):
    f = TTFont(src)
    if "fvar" in f and instantiateVariableFont:   # 可变字体 -> 实例化到指定字重
        instantiateVariableFont(f, {"wght": weight}, inplace=True, updateFontNames=False)
    out = os.path.join(BUILD, "_cjk_base.ttf")
    os.makedirs(BUILD, exist_ok=True); f.save(out)
    return out

def clone_metrics(orig_ufont, base_ttf, out_ufont):
    """字形用 base，竖直度量克隆 orig（关键：recalcBBoxes=False）"""
    s = TTFont(orig_ufont, lazy=True)
    f = TTFont(base_ttf, recalcBBoxes=False)
    assert s["head"].unitsPerEm == f["head"].unitsPerEm, "upem 不一致, 需缩放(此处未实现)"
    f["head"].yMax = s["head"].yMax            # ← 决定行高/基线, 必须对齐
    f["head"].yMin = s["head"].yMin
    f["hhea"].ascent  = s["hhea"].ascent
    f["hhea"].descent = s["hhea"].descent
    f["hhea"].lineGap = s["hhea"].lineGap
    o, so = f["OS/2"], s["OS/2"]
    o.usWinAscent, o.usWinDescent   = so.usWinAscent, so.usWinDescent
    o.sTypoAscender, o.sTypoDescender, o.sTypoLineGap = so.sTypoAscender, so.sTypoDescender, so.sTypoLineGap
    o.fsSelection = (o.fsSelection | 0x80) if (so.fsSelection & 0x80) else (o.fsSelection & ~0x80)
    f.save(out_ufont)

def main():
    ap = argparse.ArgumentParser(description="BLUE PROTOCOL 简中字库补丁生成器")
    ap.add_argument("--src", default=os.path.join(SRC, "GenSenRounded2JP-M.otf"),
                    help="源字体(需覆盖 简中+日文假名汉字; OFL 的源泉圆体/思源黑体等)")
    ap.add_argument("--weight", type=int, default=580, help="字重(仅可变字体源生效)")
    ap.add_argument("--mount-point", default="../../../")
    ap.add_argument("--deploy", metavar="MODS_DIR", help="生成后复制 pak 到游戏 ~mods 目录")
    args = ap.parse_args()

    if not os.path.exists(args.src):
        sys.exit(f"缺少源字体 {args.src}（放进 src/，或用 --src 指定）")
    base = make_base(args.src, args.weight)
    os.makedirs(STAGE, exist_ok=True)
    for face in FACES:
        of = os.path.join(ORIG, f"{face}.ufont")
        if not os.path.exists(of):
            sys.exit(f"缺少原始脸 {of}（先用 repak+AES 从 pakchunk0/500 抽出 uasset/uexp/ufont 到 orig/）")
        clone_metrics(of, base, os.path.join(STAGE, f"{face}.ufont"))
        for ext in ("uasset", "uexp"):
            shutil.copy(os.path.join(ORIG, f"{face}.{ext}"), os.path.join(STAGE, f"{face}.{ext}"))
        print(f"  生成 {face}.ufont (度量已对齐原字体)")

    if os.path.exists(PAKOUT): os.remove(PAKOUT)
    subprocess.run([REPAK, "pack", "--version", "V11", "--mount-point", args.mount_point,
                    os.path.join(BUILD, "stage"), PAKOUT], check=True)
    print(f"已生成 {PAKOUT} ({os.path.getsize(PAKOUT)} B)")
    print("提醒：把同名 .sig（复用任意 564B 现成 sig 改名）和 .pak 一起放进 ~mods 才能加载。")

    if args.deploy:
        shutil.copy(PAKOUT, args.deploy)
        sig = PAKOUT[:-4] + ".sig"
        if os.path.exists(sig): shutil.copy(sig, args.deploy)
        print(f"已部署到 {args.deploy}")

if __name__ == "__main__":
    main()
