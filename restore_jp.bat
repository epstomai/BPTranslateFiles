@echo off
chcp 65001 >nul
title Blue Protocol 一键还原日文 (卸载简中汉化)

set "DEFAULT_PATH=F:\games\BandaiNamcoLauncherGames\BLUEPROTOCOL\BLUEPROTOCOL"
echo ======================================================
echo        Blue Protocol 一键还原日文 (卸载简中汉化)
echo ======================================================
echo.
echo 本工具会移除简中汉化的三个客户端包与 master-data, 游戏恢复日文。
echo (不删除 dinput8.dll —— 它只是签名绕过, 无汉化包时无害; 如需彻底清除见末尾提示)
echo.

:CHECK_PATH
if exist "%DEFAULT_PATH%" (
    set "GAME_PATH=%DEFAULT_PATH%"
    echo 检测到默认游戏路径: %DEFAULT_PATH%
    goto CONFIRM
)
echo 未能在默认路径检测到游戏。
set /p "GAME_PATH=请输入你的游戏目录 (例如 D:\Games\BLUEPROTOCOL\BLUEPROTOCOL): "
if not exist "%GAME_PATH%" (
    echo 输入的路径不存在，请重新运行。
    pause
    exit
)

:CONFIRM
echo.
set /p "OK=确认还原为日文? 将删除 ~mods 下的简中汉化包与 Win64\texts.json (Y/N): "
if /i not "%OK%"=="Y" (
    echo 已取消。
    pause
    exit
)

echo.
echo 开始还原...
set "MODS=%GAME_PATH%\Content\Paks\~mods"
set "WIN64=%GAME_PATH%\Binaries\Win64"

:: 1. 删除三个汉化 pak 及其 .sig (只删本汉化的, 不动你的其他 mod)
echo 正在移除 简中汉化 PAK / .sig...
for %%F in (DStars_client_patch_zh-cn_1_P DStars_font_zh-cn_1_P DStars_maps_zh-cn_9_P) do (
    if exist "%MODS%\%%F.PAK" del /f /q "%MODS%\%%F.PAK"
    if exist "%MODS%\%%F.pak" del /f /q "%MODS%\%%F.pak"
    if exist "%MODS%\%%F.sig" del /f /q "%MODS%\%%F.sig"
)

:: 2. 删除 master-data 汉化 texts.json (Hoshi 无注入 -> 服务端原始日文)
echo 正在移除 texts.json (master-data 汉化)...
if exist "%WIN64%\texts.json" del /f /q "%WIN64%\texts.json"

echo.
echo ======================================================
echo              已还原为日文！
echo ======================================================
echo 提示:
echo 1. 重新进入游戏即为日文。
echo 2. dinput8.dll 已保留(无害, 且重装汉化时仍需)。如要彻底清除, 手动删除:
echo      %WIN64%\dinput8.dll
echo 3. 重新安装汉化, 运行 deploy.bat 即可。
echo ======================================================
pause
exit
