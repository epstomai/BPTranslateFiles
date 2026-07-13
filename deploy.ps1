[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$GamePath,

    [switch]$Elevated
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# Windows PowerShell 5.1 needs a BOM to read this file reliably.  The launcher is
# deliberately ASCII-only because some cmd.exe versions misparse UTF-8 batch files.
try {
    & "$env:SystemRoot\System32\chcp.com" 65001 | Out-Null
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
} catch {
    # Console encoding is cosmetic; deployment can continue if it cannot be changed.
}

$ScriptRoot = $PSScriptRoot
$SourceDll = Join-Path $ScriptRoot 'client-patch\Binaries\Win64\dinput8.dll'
$SourceMods = Join-Path $ScriptRoot 'client-patch\Content\Paks\~mods'
$SourceTexts = Join-Path $ScriptRoot 'server-patch\texts.json'

function Write-Banner {
    Write-Host '======================================================' -ForegroundColor Cyan
    Write-Host '         Blue Protocol 简中汉化一键部署工具' -ForegroundColor Cyan
    Write-Host '======================================================' -ForegroundColor Cyan
}

function Test-GameRoot {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }

    $win64Candidate = [IO.Path]::Combine($Path, 'Binaries\Win64')
    $paksCandidate = [IO.Path]::Combine($Path, 'Content\Paks')

    return (
        (Test-Path -LiteralPath $win64Candidate -PathType Container) -and
        (Test-Path -LiteralPath $paksCandidate -PathType Container)
    )
}

function Resolve-GameRoot {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }

    $cleanPath = [Environment]::ExpandEnvironmentVariables($Path.Trim().Trim('"').Trim("'"))

    try {
        $item = Get-Item -LiteralPath $cleanPath -ErrorAction Stop
        if (-not $item.PSIsContainer) {
            $cleanPath = $item.Directory.Parent.Parent.FullName
        }
    } catch {
        # GetFullPath below gives a consistent absolute candidate and validation rejects it.
    }

    try {
        $absolutePath = [IO.Path]::GetFullPath($cleanPath)
    } catch {
        return $null
    }

    $candidates = @(
        $absolutePath,
        ([IO.Path]::Combine($absolutePath, 'BLUEPROTOCOL')),
        ([IO.Path]::Combine($absolutePath, 'BLUEPROTOCOL\BLUEPROTOCOL'))
    )

    foreach ($candidate in $candidates) {
        if (Test-GameRoot $candidate) {
            return (Get-Item -LiteralPath $candidate).FullName.TrimEnd('\')
        }
    }

    return $null
}

function Get-AutoDetectedGameRoot {
    $candidates = New-Object System.Collections.Generic.List[string]

    if (-not [string]::IsNullOrWhiteSpace($env:BLUEPROTOCOL_GAME_PATH)) {
        $candidates.Add($env:BLUEPROTOCOL_GAME_PATH)
    }

    $candidates.Add((Join-Path $ScriptRoot '..\BLUEPROTOCOL\BLUEPROTOCOL'))

    foreach ($drive in Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue) {
        if ([string]::IsNullOrWhiteSpace($drive.Root)) {
            continue
        }

        $candidates.Add((Join-Path $drive.Root 'games\BandaiNamcoLauncherGames\BLUEPROTOCOL\BLUEPROTOCOL'))
        $candidates.Add((Join-Path $drive.Root 'BandaiNamcoLauncherGames\BLUEPROTOCOL\BLUEPROTOCOL'))
    }

    foreach ($candidate in $candidates) {
        $resolved = Resolve-GameRoot $candidate
        if ($null -ne $resolved) {
            return $resolved
        }
    }

    return $null
}

function Test-DirectoryWritable {
    param([string]$Path)

    $probe = Join-Path $Path ('.zhhans-write-test-{0}.tmp' -f ([Guid]::NewGuid().ToString('N')))
    try {
        [IO.File]::WriteAllText($probe, 'test')
        Remove-Item -LiteralPath $probe -Force
        return $true
    } catch {
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        return $false
    }
}

function Quote-PowerShellLiteral {
    param([string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Restart-Elevated {
    param([string]$ResolvedGamePath)

    $hostExe = (Get-Process -Id $PID).Path
    $scriptLiteral = Quote-PowerShellLiteral $PSCommandPath
    $pathLiteral = Quote-PowerShellLiteral $ResolvedGamePath
    $command = "& $scriptLiteral -GamePath $pathLiteral -Elevated"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))

    Write-Host '[提示] 游戏目录不可写，即将请求管理员权限。' -ForegroundColor Yellow
    try {
        $process = Start-Process -FilePath $hostExe -Verb RunAs -Wait -PassThru -ArgumentList @(
            '-NoLogo',
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-EncodedCommand', $encoded
        )
        return $process.ExitCode
    } catch {
        Write-Host '[失败] 未获得管理员权限，无法写入游戏目录。' -ForegroundColor Red
        return 20
    }
}

function Copy-VerifiedFile {
    param(
        [string]$Source,
        [string]$Destination
    )

    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    $sourceInfo = Get-Item -LiteralPath $Source
    $destinationInfo = Get-Item -LiteralPath $Destination

    if ($sourceInfo.Length -ne $destinationInfo.Length) {
        throw "复制后文件大小不一致：$($destinationInfo.Name)"
    }
}

try {
    Write-Banner
    Write-Host

    $missingSources = @()
    foreach ($requiredSource in @($SourceDll, $SourceMods, $SourceTexts)) {
        if (-not (Test-Path -LiteralPath $requiredSource)) {
            $missingSources += $requiredSource
        }
    }

    if ($missingSources.Count -gt 0) {
        throw "补丁包不完整，请先完整解压后再运行。缺少：`n$($missingSources -join "`n")"
    }

    $pakFiles = @(Get-ChildItem -LiteralPath $SourceMods -File -Filter '*.pak')
    if ($pakFiles.Count -eq 0) {
        throw '补丁包不完整：client-patch\Content\Paks\~mods 中没有 .pak 文件。'
    }

    $modFiles = New-Object System.Collections.Generic.List[System.IO.FileInfo]
    foreach ($pak in $pakFiles) {
        $signaturePath = [IO.Path]::ChangeExtension($pak.FullName, '.sig')
        if (-not (Test-Path -LiteralPath $signaturePath -PathType Leaf)) {
            throw "补丁包不完整：$($pak.Name) 缺少同名 .sig 文件。"
        }
        $modFiles.Add($pak)
        $modFiles.Add((Get-Item -LiteralPath $signaturePath))
    }

    $resolvedGamePath = $null
    if ([string]::IsNullOrWhiteSpace($GamePath)) {
        $resolvedGamePath = Get-AutoDetectedGameRoot
    } else {
        $resolvedGamePath = Resolve-GameRoot $GamePath
        if ($null -eq $resolvedGamePath) {
            Write-Host '[无效] 传入的位置不是有效的游戏目录。' -ForegroundColor Red
        }
    }

    while ($null -eq $resolvedGamePath) {
        Write-Host '未自动找到游戏目录。' -ForegroundColor Yellow
        Write-Host '可输入 BLUEPROTOCOL-Win64-Shipping.exe、游戏目录或它的上级目录。'
        $inputPath = Read-Host '游戏路径（直接回车取消）'
        if ([string]::IsNullOrWhiteSpace($inputPath)) {
            Write-Host '[取消] 未进行任何修改。' -ForegroundColor Yellow
            exit 2
        }

        $resolvedGamePath = Resolve-GameRoot $inputPath
        if ($null -eq $resolvedGamePath) {
            Write-Host '[无效] 该位置下未找到 Binaries\Win64 和 Content\Paks，请重新输入。' -ForegroundColor Red
        }
    }

    Write-Host ("游戏目录：{0}" -f $resolvedGamePath) -ForegroundColor Green

    $runningGame = Get-Process -Name 'BLUEPROTOCOL-Win64-Shipping' -ErrorAction SilentlyContinue
    if ($null -ne $runningGame) {
        throw '检测到游戏正在运行。请完全退出游戏后重新部署，以免文件被占用。'
    }

    $win64Path = Join-Path $resolvedGamePath 'Binaries\Win64'
    $paksPath = Join-Path $resolvedGamePath 'Content\Paks'
    $modsPath = Join-Path $paksPath '~mods'

    if (-not (Test-DirectoryWritable $win64Path) -or -not (Test-DirectoryWritable $paksPath)) {
        if (-not $Elevated) {
            exit (Restart-Elevated $resolvedGamePath)
        }
        throw '即使以管理员身份运行，游戏目录仍不可写。请检查文件夹权限或安全软件拦截。'
    }

    New-Item -ItemType Directory -Path $modsPath -Force | Out-Null

    Write-Host
    Write-Host '[1/3] 正在部署 dinput8.dll...'
    Copy-VerifiedFile $SourceDll (Join-Path $win64Path 'dinput8.dll')

    Write-Host ("[2/3] 正在部署 {0} 个 PAK/签名文件..." -f $modFiles.Count)
    foreach ($modFile in $modFiles) {
        Copy-VerifiedFile $modFile.FullName (Join-Path $modsPath $modFile.Name)
        Write-Host ("      已复制 {0}" -f $modFile.Name)
    }

    Write-Host '[3/3] 正在部署 texts.json...'
    Copy-VerifiedFile $SourceTexts (Join-Path $win64Path 'texts.json')

    Write-Host
    Write-Host '======================================================' -ForegroundColor Green
    Write-Host '             简中汉化补丁部署成功！' -ForegroundColor Green
    Write-Host '======================================================' -ForegroundColor Green
    Write-Host ("已安装 {0} 个 PAK，并验证全部同名 .sig。" -f $pakFiles.Count)
    Write-Host 'texts.json 已复制到 Binaries\Win64。'
    if ($Elevated) {
        Read-Host '按回车键关闭管理员窗口' | Out-Null
    }
    exit 0
} catch {
    Write-Host
    Write-Host ("[部署失败] {0}" -f $_.Exception.Message) -ForegroundColor Red
    Write-Host '未显示“部署成功”即表示安装不完整；修正上述问题后可安全地重新运行。' -ForegroundColor Yellow
    if ($Elevated) {
        Read-Host '按回车键关闭管理员窗口' | Out-Null
    }
    exit 1
}
