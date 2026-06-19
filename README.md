# Blue Protocol 简体中文汉化补丁 (BPTranslateFiles - Simplified Chinese)

本项目是针对 Blue Protocol 客户端与服务端制作的简体中文本地化版本，旨在为玩家提供自然、地道的简体中文剧情与文本体验。

本项目的本地化工作直接基于日文原版文本进行翻译与精校，使用了GPT5.5和Opus4.8进行翻译，校对。

## 致谢 (Acknowledgements)

特别感谢以下项目和作者在技术架构上的支持：
* **[mountaindewritos/BPTranslateFiles](https://github.com/mountaindewritos/BPTranslateFiles/)**：本项目参考了其补丁的打包架构与目录结构（如挂载注入文件）。
* **Dewritos & mce & Team Blast**：感谢他们在解包/打包及服务器补丁挂载技术上提供的杰出方案。
* 字库使用 **[ButTaiwan/源泉圆体 GenSenRounded](https://github.com/ButTaiwan/gensen-font)**（SIL OFL）。

---

## 📂 补丁包结构

* `client-patch/`：客户端汉化补丁。
  * `Binaries/Win64/dinput8.dll`：绕过客户端签名校验的 DLL（**必需**，否则带 `.pak` 进游戏会闪退）。
  * `Content/Paks/~mods/`：三个汉化 `.pak`，**每个都配同名 `.sig`，缺一不可**：
    * `DStars_client_patch_zh-cn_1_P.PAK`：UI、武器等客户端核心资产文本。
    * `DStars_font_zh-cn_1_P.pak`：**简中字库补丁**（换全覆盖泛 CJK 圆体，解决简体专用字不显示 + 文字下沉）。
    * `DStars_maps_zh-cn_9_P.pak`：**地图/区域/传送点/NPC名 等文本表补全**（修复大量 blank / `NotFoundZoneName`）。
* `server-patch/`：服务端汉化补丁（master-data）：`texts.json`（部署到 `Binaries/Win64/`，由 Hoshi.dll 读取注入）。
* `tools/`：维护者用的构建工具（见文末）。
* `deploy.bat`：一键部署向导。

---

## 🚀 安装与使用指南

### 使用一键部署工具
* 推荐直接双击运行根目录下的 **`deploy.bat`**，按提示完成客户端补丁的自动安装（会复制 dinput8.dll 和 `~mods` 内全部 `.pak`/`.sig`）。

### 手动安装说明

#### 1. 客户端补丁安装
1. 将 `client-patch/Binaries/Win64/dinput8.dll` 复制到你的游戏安装目录：
   `...\BLUEPROTOCOL\BLUEPROTOCOL\Binaries\Win64\`
2. 将 `client-patch/Content/Paks/~mods` 文件夹复制到你的游戏安装目录：
   `...\BLUEPROTOCOL\BLUEPROTOCOL\Content\Paks\`
   *(若已有 `~mods` 文件夹，把里面**所有 `.pak` 和同名 `.sig`**一起放入)*

> ⚠️ **每个 `.pak` 都必须有同名 `.sig`**。`.sig` 内容不会被校验（dinput8.dll 已绕过签名内容校验），
> 但引擎要求 `.sig` 文件存在才会挂载该 `.pak`。任意一个有效的 564B `.sig` 改成对应包名即可。

#### 2. 服务端补丁安装（master-data）
* 将 `server-patch/texts.json` 复制到游戏 `...\BLUEPROTOCOL\BLUEPROTOCOL\Binaries\Win64\`（由 Hoshi.dll 读取注入 master-data）；
  若用其他本地 Patcher，可把 `server-patch` 文件夹放在 patcher 工具同级目录。
  *(`deploy.bat` 已自动完成此步)*

---

## 🆕 本次更新内容

### 1. 简中字库（字体）
原版 UI 用日文字体（Fontworks Seurat 等），**简体专用字（们/这/说/电/开/戏…）没有字形，直接不显示**；
直接换字体又会因竖直度量不同导致**文字在按钮里下沉、被裁切**。本补丁把 3 个日文复合字体的主脸换成
**源泉圆体 GenSenRounded2（圆体，最贴原版观感，覆盖简中+日文）**，并把字体竖直度量对齐原字体，解决缺字与下沉。
重建工具与全部要点见 `tools/replace_font.py`。

### 2. 地图/区域/NPC/提示等文本补全（修 blank）
**根因**：旧版大量地图名、传送点、NPC 名显示空白或 `Warning:NotFoundZoneName` —— 是因为汉化包把这些
`SBTextTableAsset` 打包成了"只含已译条目"的**残缺版**（丢了 40%~65% 条目），引擎按 ID 查不到就显示空。
（原版与英文包都没有此问题，它们保留了完整条目。）本补丁把
`LocationName / ZoneName / ZoneShortName / WarpPointName / CharacterName / LoadingTips /
AdventureBoard / TutorialHelp / LibraryEnemyDesc / InteractNotice / MyCharacterMenu` 等表
**用官方完整表打底 + 并入译文**重建，blank 全部消除。

---

## 🛠 维护者：构建工具与注意事项

### 字体替换 `tools/replace_font.py`
重建简中字库包：先用 repak+AES 把 3 个原始字体脸抽到 `tools/orig/`，源字体放 `tools/src/`，然后
`python tools/replace_font.py [--deploy <游戏~mods目录>]`。脚本头部记录了全部踩坑要点（务必读）：
`.ufont` 整文件读取、下沉真凶是 `head.yMax/yMin`、CFF 字体保存须 `recalcBBoxes=False`、每包须配 `.sig`。

### ⚠️ 打文本表包的铁律（避免再出 blank）
**必须从"官方完整表"出发、就地把日文替换成中文重建表，绝不能"导出已译条目再打包"**
（那样会丢未译条目 → 引擎查不到 → blank / NotFound）。做法：repak 抽官方完整 `.uasset/.uexp` →
并入已有译文 → **二进制原地等长替换**（中文≤日文则补空格，更长则暂留日文；**关键：保持 uexp 字节数不变**，
否则破坏 `SBTextTableAsset` 结构、游戏不认——UAssetAPI `fromjson` 会改坏此类资产，务必避开）→ 打包。
> 译名风格：有词义意译，纯造名才音译且挑顺口的字、不加间隔号。
