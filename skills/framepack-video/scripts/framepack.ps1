param(
    [ValidateSet('status', 'download', 'start', 'stop-download')]
    [string]$Action = 'status',
    [string]$Root = $env:FRAMEPACK_ROOT,
    [string]$WebUiHost = $(if ([string]::IsNullOrWhiteSpace($env:FRAMEPACK_WEBUI_HOST)) { '127.0.0.1' } else { $env:FRAMEPACK_WEBUI_HOST }),
    [switch]$ApproveDownload,
    [switch]$ApproveGeneration,
    [switch]$ApproveStopDownload
)

$ErrorActionPreference = 'Stop'
$root = $Root
if ([string]::IsNullOrWhiteSpace($root)) { throw 'Specify -Root or set FRAMEPACK_ROOT.' }
if (-not [System.IO.Path]::IsPathRooted($root)) { throw 'FramePack root must be an absolute path.' }
$root = [System.IO.Path]::GetFullPath($root)
$webui = Join-Path $root 'webui'
$python = Join-Path $root 'system\python\python.exe'
$runBat = Join-Path $root 'run.bat'
$downloadScript = Join-Path $PSScriptRoot 'download_models.py'
$pidFile = Join-Path $root 'framepack-model-download.process.json'
$statusFile = Join-Path $root 'framepack-model-download.status.json'
$completeFile = Join-Path $root 'framepack-model-download.complete'
$downloadOut = Join-Path $root 'framepack-model-download.log'
$downloadErr = Join-Path $root 'framepack-model-download.err.log'
$appOut = Join-Path $root 'framepack-app.log'
$appErr = Join-Path $root 'framepack-app.err.log'
$downloadStartGuard = Join-Path $root 'framepack-model-download.starting.lock'
$modelLockFile = Join-Path $root 'framepack-model-download.lock'

function Get-NormalizedPath([string]$Path) {
    return [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
}

function Test-SamePath([string]$Left, [string]$Right) {
    return [string]::Equals((Get-NormalizedPath $Left), (Get-NormalizedPath $Right), [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-NoReparsePoint([string]$Path) {
    $full = Get-NormalizedPath $Path
    $current = [System.IO.Path]::GetPathRoot($full)
    $relative = $full.Substring($current.Length)
    foreach ($part in $relative.Split([System.IO.Path]::DirectorySeparatorChar, [System.StringSplitOptions]::RemoveEmptyEntries)) {
        $current = Join-Path $current $part
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -Force -LiteralPath $current
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Symlink or reparse point is not allowed: $current"
            }
        }
    }
}

function Get-DownloadScriptHash {
    if (-not (Test-Path -LiteralPath $downloadScript -PathType Leaf)) { return $null }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $downloadScript).Hash.ToLowerInvariant()
}

function Get-VerifiedDownloadProcess {
    if (-not (Test-Path -LiteralPath $pidFile -PathType Leaf)) { return $null }
    try { $record = Get-Content -Raw -LiteralPath $pidFile | ConvertFrom-Json } catch { return $null }
    if ($null -eq $record.processId -or [string]$record.processId -notmatch '^\d+$') { return $null }
    if ([string]::IsNullOrWhiteSpace([string]$record.executablePath) -or
        [string]::IsNullOrWhiteSpace([string]$record.processStartTimeUtc) -or
        [string]::IsNullOrWhiteSpace([string]$record.downloaderScriptSha256) -or
        [string]::IsNullOrWhiteSpace([string]$record.framepackRoot)) { return $null }
    if (-not (Test-SamePath ([string]$record.executablePath) $python)) { return $null }
    if (-not (Test-SamePath ([string]$record.framepackRoot) $root)) { return $null }
    $scriptHash = Get-DownloadScriptHash
    if ($null -eq $scriptHash -or $scriptHash -ne ([string]$record.downloaderScriptSha256).ToLowerInvariant()) { return $null }
    $process = Get-Process -Id ([int]$record.processId) -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $null }
    try { $path = $process.Path } catch { return $null }
    if (-not (Test-SamePath $path $python)) { return $null }
    try { $started = $process.StartTime.ToUniversalTime().ToString('o') } catch { return $null }
    if ($started -ne [string]$record.processStartTimeUtc) { return $null }
    try {
        $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)" -ErrorAction Stop).CommandLine
    } catch { return $null }
    if ([string]::IsNullOrWhiteSpace($commandLine) -or $commandLine.IndexOf($downloadScript, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) { return $null }
    return $process
}

function Get-VerifiedCompletionMarker {
    if (-not (Test-Path -LiteralPath $completeFile -PathType Leaf)) {
        return [PSCustomObject]@{ valid = $false; reason = 'completion marker is missing'; marker = $null }
    }
    try { $marker = Get-Content -Raw -LiteralPath $completeFile | ConvertFrom-Json } catch {
        return [PSCustomObject]@{ valid = $false; reason = 'completion marker is not valid JSON'; marker = $null }
    }
    $scriptHash = Get-DownloadScriptHash
    if ($marker.modelsVerified -ne $true) {
        return [PSCustomObject]@{ valid = $false; reason = 'completion marker does not assert verified models'; marker = $marker }
    }
    if ($null -eq $scriptHash -or ([string]$marker.downloaderScriptSha256).ToLowerInvariant() -ne $scriptHash) {
        return [PSCustomObject]@{ valid = $false; reason = 'completion marker does not match the current downloader'; marker = $marker }
    }
    return [PSCustomObject]@{ valid = $true; reason = 'verified marker matches the current downloader'; marker = $marker }
}

function Get-FramePackStatus {
    $downloadProcess = Get-VerifiedDownloadProcess
    $completion = Get-VerifiedCompletionMarker
    $incomplete = @()
    $cacheBytes = 0
    $localModelBytes = 0
    $cache = Join-Path $webui 'hf_download'
    if (Test-Path -LiteralPath $cache) {
        $files = Get-ChildItem -File -Recurse -LiteralPath $cache -ErrorAction SilentlyContinue
        $cacheBytes = ($files | Measure-Object -Property Length -Sum).Sum
        $incomplete = @($files | Where-Object { $_.Name -like '*.incomplete' } | ForEach-Object {
            [PSCustomObject]@{ path = $_.FullName; bytes = $_.Length; modified = $_.LastWriteTime }
        })
    }
    $localModels = Join-Path $webui 'local_models'
    if (Test-Path -LiteralPath $localModels) {
        $localFiles = Get-ChildItem -File -Recurse -LiteralPath $localModels -ErrorAction SilentlyContinue
        $localModelBytes = ($localFiles | Measure-Object -Property Length -Sum).Sum
    }
    $detail = $null
    if (Test-Path -LiteralPath $statusFile) {
        try { $detail = Get-Content -Raw -LiteralPath $statusFile | ConvertFrom-Json } catch { $detail = $null }
    }
    [PSCustomObject]@{
        rootExists = Test-Path -LiteralPath $root
        webuiExists = Test-Path -LiteralPath $webui -PathType Container
        pythonExists = Test-Path -LiteralPath $python
        runBatExists = Test-Path -LiteralPath $runBat -PathType Leaf
        modelsComplete = [bool]$completion.valid
        modelsCompleteReason = $completion.reason
        downloaderRunning = $null -ne $downloadProcess
        downloaderPid = if ($null -ne $downloadProcess) { $downloadProcess.Id } else { $null }
        cachedBytes = [long]$cacheBytes
        localModelBytes = [long]$localModelBytes
        incompleteFiles = $incomplete
        detail = $detail
        completionMarker = $completion.marker
        downloadLog = $downloadOut
        downloadErrorLog = $downloadErr
    }
}

function Assert-FramePackInstall([switch]$RequireRunBat) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { throw "FramePack root not found: $root" }
    Assert-NoReparsePoint $root
    if (-not (Test-Path -LiteralPath $webui -PathType Container)) { throw "FramePack webui directory not found: $webui" }
    Assert-NoReparsePoint $webui
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "FramePack Python not found: $python" }
    Assert-NoReparsePoint $python
    if (-not (Test-Path -LiteralPath $downloadScript -PathType Leaf)) { throw "Model downloader not found: $downloadScript" }
    Assert-NoReparsePoint $downloadScript
    if ($RequireRunBat) {
        if (-not (Test-Path -LiteralPath $runBat -PathType Leaf)) { throw "FramePack launcher not found: $runBat" }
        Assert-NoReparsePoint $runBat
    }
}

switch ($Action) {
    'status' {
        Get-FramePackStatus | ConvertTo-Json -Depth 8
    }
    'download' {
        if (-not $ApproveDownload) { throw 'Model download requires the explicit -ApproveDownload switch.' }
        Assert-FramePackInstall
        try {
            $startGuardStream = [System.IO.File]::Open($downloadStartGuard, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        } catch [System.IO.IOException] {
            throw "A downloader start guard already exists. Verify that no controller is starting, then remove only this stale guard: $downloadStartGuard"
        }
        try {
        $existing = Get-VerifiedDownloadProcess
        if ($null -ne $existing) {
            Write-Output "Downloader already running with PID $($existing.Id)."
            Get-FramePackStatus | ConvertTo-Json -Depth 8
            break
        }
        if (Test-Path -LiteralPath $modelLockFile -PathType Leaf) {
            throw "An unverified or stale downloader lock exists. Verify no downloader is running before removing it manually: $modelLockFile"
        }
        if (Test-Path -LiteralPath $pidFile -PathType Leaf) {
            try { $staleRecord = Get-Content -Raw -LiteralPath $pidFile | ConvertFrom-Json } catch {
                throw "The downloader process record is invalid and will not be overwritten automatically: $pidFile"
            }
            if ($null -eq $staleRecord.processId -or [string]$staleRecord.processId -notmatch '^\d+$') {
                throw "The downloader process record is invalid and will not be overwritten automatically: $pidFile"
            }
            $unverifiedProcess = Get-Process -Id ([int]$staleRecord.processId) -ErrorAction SilentlyContinue
            if ($null -ne $unverifiedProcess) {
                throw "The recorded downloader PID is live but could not be verified; refusing to overwrite or stop it: $($staleRecord.processId)"
            }
        }
        $env:HF_HOME = Join-Path $webui 'hf_download'
        if ([string]::IsNullOrWhiteSpace($env:FRAMEPACK_HF_ENDPOINT)) { $env:FRAMEPACK_HF_ENDPOINT = 'https://huggingface.co' }
        $env:HF_ENDPOINT = $env:FRAMEPACK_HF_ENDPOINT
        $env:FRAMEPACK_ROOT = $root
        $env:FRAMEPACK_DOWNLOAD_APPROVED = 'YES'
        if ([string]::IsNullOrWhiteSpace($env:FRAMEPACK_MAX_DOWNLOAD_ATTEMPTS)) { $env:FRAMEPACK_MAX_DOWNLOAD_ATTEMPTS = '3' }
        $env:HF_HUB_DISABLE_XET = '1'
        $env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
        $downloadArgument = '"' + $downloadScript + '"'
        $process = Start-Process -FilePath $python -ArgumentList @($downloadArgument) -WorkingDirectory $webui -WindowStyle Hidden -RedirectStandardOutput $downloadOut -RedirectStandardError $downloadErr -PassThru
        try {
            $record = [ordered]@{
                processId = $process.Id
                executablePath = Get-NormalizedPath $python
                processStartTimeUtc = $process.StartTime.ToUniversalTime().ToString('o')
                downloaderScriptSha256 = Get-DownloadScriptHash
                framepackRoot = Get-NormalizedPath $root
                createdAt = [DateTimeOffset]::UtcNow.ToString('o')
            }
            $pidTemp = "$pidFile.$PID.tmp"
            $record | ConvertTo-Json | Set-Content -LiteralPath $pidTemp -Encoding utf8
            Move-Item -LiteralPath $pidTemp -Destination $pidFile -Force
        } catch {
            Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
            throw
        }
        Start-Sleep -Milliseconds 800
        Get-FramePackStatus | ConvertTo-Json -Depth 8
        } finally {
            if ($null -ne $startGuardStream) { $startGuardStream.Dispose() }
            Remove-Item -LiteralPath $downloadStartGuard -Force -ErrorAction SilentlyContinue
        }
    }
    'start' {
        if (-not $ApproveGeneration) { throw 'Starting FramePack requires the explicit -ApproveGeneration switch.' }
        Assert-FramePackInstall -RequireRunBat
        if ($WebUiHost -notin @('127.0.0.1', 'localhost', '::1')) { throw 'WebUI host must be loopback: 127.0.0.1, localhost, or ::1.' }
        $completion = Get-VerifiedCompletionMarker
        if (-not $completion.valid) { throw "FramePack models are not verified: $($completion.reason). Run -Action download first." }
        $existing = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
            try { Test-SamePath $_.Path $python } catch { $false }
        }
        if ($existing) {
            throw 'FramePack embedded Python is already running; the controller will not start a duplicate or terminate it.'
        }
        $env:GRADIO_SERVER_NAME = '127.0.0.1'
        $env:FRAMEPACK_WEBUI_HOST = '127.0.0.1'
        $process = Start-Process -FilePath $runBat -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $appOut -RedirectStandardError $appErr -PassThru
        [PSCustomObject]@{ started = $true; pid = $process.Id; url = 'http://127.0.0.1:7860'; log = $appOut; errorLog = $appErr } | ConvertTo-Json
    }
    'stop-download' {
        if (-not $ApproveStopDownload) { throw 'Stopping the downloader requires the explicit -ApproveStopDownload switch.' }
        Assert-FramePackInstall
        $process = Get-VerifiedDownloadProcess
        if ($null -eq $process) {
            Write-Output 'No verified FramePack downloader is running.'
            break
        }
        Stop-Process -Id $process.Id
        Write-Output "Stopped FramePack downloader PID $($process.Id). Partial files were preserved."
    }
}
