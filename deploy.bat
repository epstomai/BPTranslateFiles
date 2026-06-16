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

:: 2. 复制 PAK 补丁包
echo 正在复制 客户端简中 PAK 补丁...
if not exist "%GAME_PATH%\Content\Paks\~mods" mkdir "%GAME_PATH%\Content%\Paks\~mods"
copy /y "client-patch\Content\Paks\~mods\DStars_client_patch_zh-cn_1_P.PAK" "%GAME_PATH%\Content\Paks\~mods\DStars_client_patch_zh-cn_1_P.PAK"

echo.
echo ======================================================
echo           简中汉化补丁一键部署成功！
echo ======================================================
echo 提示:
echo 1. 服务端补丁 (server-patch/loc.json) 请手动覆盖至你的本地服务端对应目录。
echo 2. 如需卸载，直接删除游戏目录下的 dinput8.dll 与 ~mods/DStars_client_patch_zh-cn_1_P.PAK 即可。
echo ======================================================
pause
exit
