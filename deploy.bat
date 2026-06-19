@echo off
chcp 65001 >nul
title Blue Protocol 简中汉化一键部署工具

set "DEFAULT_PATH=F:\games\BandaiNamcoLauncherGames\BLUEPROTOCOL\BLUEPROTOCOL"
echo ======================================================
echo          Blue Protocol 简中汉化一键部署工具
echo ======================================================
echo.

:CHECK_PATH
if exist "%DEFAULT_PATH%" (
    set "GAME_PATH=%DEFAULT_PATH%"
    echo 检测到默认游戏路径: %DEFAULT_PATH%
    goto DO_INSTALL
)

echo 未能在默认路径检测到游戏。
set /p "GAME_PATH=请输入你的游戏目录 (例如 D:\Games\BLUEPROTOCOL\BLUEPROTOCOL): "

:VALIDATE
if not exist "%GAME_PATH%" (
    echo 输入的路径不存在，请重新输入。
    echo.
    goto CHECK_PATH
)
if not exist "%GAME_PATH%\Binaries" (
    echo [警告] 该目录下未检测到 Binaries 文件夹，请确认是否为正确的 BLUEPROTOCOL 子文件夹。
)

:DO_INSTALL
echo.
echo 开始部署简中汉化补丁...
echo.

:: 1. 复制 dinput8.dll
echo 正在复制 dinput8.dll...
if not exist "%GAME_PATH%\Binaries\Win64" mkdir "%GAME_PATH%\Binaries\Win64"
copy /y "client-patch\Binaries\Win64\dinput8.dll" "%GAME_PATH%\Binaries\Win64\dinput8.dll"

:: 2. 复制全部 PAK 补丁包 + .sig (文本/字库/地图; 关键: 每个 .pak 都必须有同名 .sig, 否则闪退!)
echo 正在复制 客户端简中 PAK 补丁 (文本 / 字库 / 地图)...
if not exist "%GAME_PATH%\Content\Paks\~mods" mkdir "%GAME_PATH%\Content\Paks\~mods"
copy /y "client-patch\Content\Paks\~mods\*.pak" "%GAME_PATH%\Content\Paks\~mods\"
echo 正在复制 PAK 签名文件 .sig (必需, 否则闪退)...
copy /y "client-patch\Content\Paks\~mods\*.sig" "%GAME_PATH%\Content\Paks\~mods\"

:: 3. 复制 texts.json 到 Win64 (master-data 中文, Hoshi 读取)
echo 正在复制 texts.json (云数据中文)...
copy /y "server-patch\texts.json" "%GAME_PATH%\Binaries\Win64\texts.json"

echo.
echo ======================================================
echo           简中汉化补丁一键部署成功！
echo ======================================================
echo 提示:
echo 1. 客户端 pak 必须与同名 .sig 一起存在 (PakSigningRequired), 缺 .sig 会闪退。
echo 2. texts.json 已复制到 Binaries\Win64, 由 Hoshi.dll 读取注入 master-data。
echo 3. 如需卸载，删除 dinput8.dll、~mods 下的 .PAK 与 .sig、以及 Win64\texts.json 即可。
echo ======================================================
pause
exit
