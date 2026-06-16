# Blue Protocol 简体中文汉化补丁 (BPTranslateFiles - Simplified Chinese)

本项目是针对 Blue Protocol 客户端与服务端制作的简体中文本地化版本，旨在为玩家提供自然、地道的简体中文剧情与文本体验。

本项目的本地化工作直接基于日文原版文本进行翻译与精校，使用了GPT5.5和Opus4.8进行翻译，校对。

## 致谢 (Acknowledgements)

特别感谢以下项目和作者在技术架构上的支持：
* **[mountaindewritos/BPTranslateFiles](https://github.com/mountaindewritos/BPTranslateFiles/)**：本项目参考了其补丁的打包架构与目录结构（如挂载注入文件）。
* **Dewritos & mce & Team Blast**：感谢他们在解包/打包及服务器补丁挂载技术上提供的杰出方案。

---

## 📂 补丁包结构

* `client-patch/`：客户端汉化补丁。
  * `Binaries/Win64/dinput8.dll`：绕过客户端签名校验的 DLL。
  * `Content/Paks/~mods/DStars_client_patch_zh-cn_1_P.PAK`：包含 UI、武器等客户端核心资产文本的 `.pak` 汉化包。
* `server-patch/`：服务端汉化补丁。
  * `loc.json`：简体中文定位翻译数据主文件。
* `deploy.bat`：一键部署简中汉化向导工具。

---

## 🚀 安装与使用指南

### 使用一键部署工具
* 推荐直接双击运行补丁包根目录下的 **`deploy.bat`** 脚本，跟随提示即可完成客户端补丁的自动安装。

### 手动安装说明

#### 1. 客户端补丁安装
1. 将 `client-patch/Binaries/Win64/dinput8.dll` 复制到你的游戏安装目录：
   `...\BLUEPROTOCOL\BLUEPROTOCOL\Binaries\Win64\`
2. 将 `client-patch/Content/Paks/~mods` 文件夹复制到你的游戏安装目录：
   `...\BLUEPROTOCOL\BLUEPROTOCOL\Content\Paks\`
   *(若已有 `~mods` 文件夹，只需将 `DStars_client_patch_zh-cn_1_P.PAK` 放入其中)*

#### 2. 服务端补丁安装
* 将 `server-patch/loc.json` 替换至本地服务端指定的汉化数据目录中（或者如果是其他本地 Patcher，可以直接将 `server-patch` 文件夹放在 patcher 运行工具的同级目录）。
