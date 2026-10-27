$ErrorActionPreference = 'Stop'

$controller = (Resolve-Path (Join-Path $PSScriptRoot '..\scripts\framepack.ps1')).Path
$downloader = (Resolve-Path (Join-Path $PSScriptRoot '..\scripts\download_models.py')).Path
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("framepack-controller-test-" + [guid]::NewGuid().ToString('N'))
$framepackRoot = Join-Path $temporaryRoot 'FramePack & Test'

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "ASSERTION FAILED: $Message" }
}

function Invoke-ControllerExpectFailure([string[]]$Arguments, [string]$ExpectedText) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller @Arguments 2>&1 | Out-String
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    Assert-True ($LASTEXITCODE -ne 0) "controller unexpectedly succeeded: $($Arguments -join ' ')"
    Assert-True ($output -like "*$ExpectedText*") "expected error '$ExpectedText', got: $output"
}

try {
    New-Item -ItemType Directory -Path (Join-Path $framepackRoot 'webui') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $framepackRoot 'system\python') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $framepackRoot 'system\python\python.exe') -Value 'test fixture' -Encoding ascii

    $missingRoot = Join-Path $temporaryRoot 'missing-install'
    $missingStatus = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller -Action status -Root $missingRoot | ConvertFrom-Json
    Assert-True ($missingStatus.rootExists -eq $false) 'status must diagnose a missing root without throwing'
    Assert-True ($missingStatus.modelsComplete -eq $false) 'missing root cannot have complete models'

    Invoke-ControllerExpectFailure @('-Action', 'status', '-Root', 'relative-root') 'absolute path'
    Invoke-ControllerExpectFailure @('-Action', 'download', '-Root', $framepackRoot) '-ApproveDownload'
    Invoke-ControllerExpectFailure @('-Action', 'start', '-Root', $framepackRoot) '-ApproveGeneration'
    Invoke-ControllerExpectFailure @('-Action', 'stop-download', '-Root', $framepackRoot) '-ApproveStopDownload'

    Set-Content -LiteralPath (Join-Path $framepackRoot 'framepack-model-download.complete') -Value '{broken json' -Encoding utf8
    $brokenStatus = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller -Action status -Root $framepackRoot | ConvertFrom-Json
    Assert-True ($brokenStatus.modelsComplete -eq $false) 'corrupt marker must not report complete models'

    $scriptHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $downloader).Hash.ToLowerInvariant()
    $marker = [ordered]@{
        modelsVerified = $true
        downloaderScriptSha256 = $scriptHash
        revisions = @{ fixture = 'pinned' }
    }
    $marker | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $framepackRoot 'framepack-model-download.complete') -Encoding utf8
    $validStatus = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller -Action status -Root $framepackRoot | ConvertFrom-Json
    Assert-True ($validStatus.modelsComplete -eq $true) 'matching verified marker must report complete models'

    Set-Content -LiteralPath (Join-Path $framepackRoot 'run.bat') -Value '@echo off' -Encoding ascii
    Invoke-ControllerExpectFailure @('-Action', 'start', '-Root', $framepackRoot, '-ApproveGeneration', '-WebUiHost', '0.0.0.0') 'loopback'

    $batchRoot = Join-Path $temporaryRoot 'batch & path'
    New-Item -ItemType Directory -Path $batchRoot -Force | Out-Null
    $batch = Join-Path $batchRoot 'safe launch.bat'
    Set-Content -LiteralPath $batch -Value @('@echo off', '> "%~dp0started.txt" echo ok') -Encoding ascii
    $batchOut = Join-Path $batchRoot 'stdout.log'
    $batchErr = Join-Path $batchRoot 'stderr.log'
    $process = Start-Process -FilePath $batch -WorkingDirectory $batchRoot -WindowStyle Hidden -RedirectStandardOutput $batchOut -RedirectStandardError $batchErr -PassThru -Wait
    Assert-True ($process.ExitCode -eq 0) 'direct Start-Process batch invocation must succeed'
    Assert-True (Test-Path -LiteralPath (Join-Path $batchRoot 'started.txt')) 'special-character batch path must not be reinterpreted as a command'

    Write-Output 'PASS: FramePack PowerShell controller offline tests'
} finally {
    $resolvedTemporary = [System.IO.Path]::GetFullPath($temporaryRoot)
    $resolvedSystemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedTemporary.StartsWith($resolvedSystemTemp, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedTemporary) -like 'framepack-controller-test-*' -and
        (Test-Path -LiteralPath $resolvedTemporary)) {
        [System.IO.Directory]::Delete($resolvedTemporary, $true)
    }
}
