param([ValidateSet('Copy','Verify','Finalize')][string]$Mode = 'Copy')
$ErrorActionPreference = 'Stop'
$sourceRoot = 'C:\Users\22502\Documents\Codex\2026-10-02\ban'
$destinationRoot = 'D:\语音大作业'
$recordDir = Join-Path $destinationRoot '迁移记录'
$pairs = @(
    @{ Source = Join-Path $sourceRoot 'outputs\ChineseASR'; Destination = Join-Path $destinationRoot 'ChineseASR'; Key='project' },
    @{ Source = Join-Path $sourceRoot 'work'; Destination = Join-Path $destinationRoot '工作记录'; Key='work' }
)

function Get-Inventory([string]$Root) {
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $stack = [Collections.Generic.Stack[string]]::new()
    $stack.Push($rootPath)
    while ($stack.Count -gt 0) {
        $directory = $stack.Pop()
        foreach ($item in Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
            if ($item.PSIsContainer) {
                if ($item.Name -ne '.pytest_cache') { $stack.Push($item.FullName) }
            } else {
                [pscustomobject]@{
                    RelativePath = $item.FullName.Substring($rootPath.Length + 1)
                    Length = $item.Length
                    SHA256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash
                }
            }
        }
    }
}

function Verify-Pair($Pair) {
    $sourceFiles = @(Get-Inventory $Pair.Source)
    $destinationFiles = @(Get-Inventory $Pair.Destination)
    $lookup = @{}
    foreach ($file in $destinationFiles) { $lookup[$file.RelativePath] = $file }
    $mismatches = @()
    foreach ($file in $sourceFiles) {
        $copy = $lookup[$file.RelativePath]
        if ($null -eq $copy -or $copy.Length -ne $file.Length -or $copy.SHA256 -ne $file.SHA256) {
            $mismatches += $file.RelativePath
        }
    }
    $sourceFiles | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $recordDir ($Pair.Key + '_source_sha256.json')) -Encoding utf8
    $destinationFiles | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $recordDir ($Pair.Key + '_destination_sha256.json')) -Encoding utf8
    if ($mismatches.Count) { throw "Hash mismatches: $($mismatches -join ', ')" }
    [pscustomobject]@{Key=$Pair.Key;Files=$sourceFiles.Count;Bytes=($sourceFiles|Measure-Object Length -Sum).Sum;SHA256Match=$true}
}

function Remove-SourceTreeWithoutFollowingLinks([string]$Path, [string]$Boundary) {
    $absolute = [IO.Path]::GetFullPath($Path)
    if ($absolute -ne $Boundary -and -not $absolute.StartsWith($Boundary + '\',[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Removal escaped the checked retired-source boundary.'
    }
    $item = Get-Item -LiteralPath $absolute -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        [IO.Directory]::Delete($absolute)
        return
    }
    if (-not $item.PSIsContainer) { Remove-Item -LiteralPath $absolute -Force; return }
    try { $children = @(Get-ChildItem -LiteralPath $absolute -Force -ErrorAction Stop) }
    catch { Write-Warning "Retained inaccessible historic cache: $absolute"; return }
    foreach ($child in $children) { Remove-SourceTreeWithoutFollowingLinks $child.FullName $Boundary }
    try { [IO.Directory]::Delete($absolute) }
    catch { Write-Warning "Retained non-empty historic cache directory: $absolute" }
}

if ($Mode -eq 'Copy') {
    if (Test-Path -LiteralPath $destinationRoot) { throw 'Destination exists; inspect it before proceeding.' }
    New-Item -ItemType Directory -Path $destinationRoot | Out-Null
    New-Item -ItemType Directory -Path $recordDir,(Join-Path $destinationRoot '交接报告') | Out-Null
    foreach ($pair in $pairs) {
        & robocopy.exe $pair.Source $pair.Destination /E /XJ /XD .pytest_cache /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NP /NFL /NDL "/LOG:$(Join-Path $recordDir ($pair.Key + '_robocopy.log'))"
        if ($LASTEXITCODE -ge 8) { throw "Robocopy failed: $LASTEXITCODE" }
    }
    Copy-Item -LiteralPath (Join-Path $destinationRoot '工作记录\migration_assets\README.md'),(Join-Path $destinationRoot '工作记录\migration_assets\启动联合界面.cmd') -Destination $destinationRoot
    $verification = @($pairs | ForEach-Object { Verify-Pair $_ })
    $verification | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $recordDir 'copy_verification.json') -Encoding utf8
    $verification | ConvertTo-Json -Depth 3
    exit 0
}

if ($Mode -eq 'Verify') {
    $verification = @($pairs | ForEach-Object { Verify-Pair $_ })
    $verification | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $recordDir 'copy_verification.json') -Encoding utf8
    $verification | ConvertTo-Json -Depth 3
    exit 0
}

if ($Mode -eq 'Finalize') {
    # Recheck every source file before removing its redundant C-drive copy.
    $verification = @($pairs | ForEach-Object { Verify-Pair $_ })
    $remaining = @()
    foreach ($pair in $pairs) {
        $resolvedSource = [IO.Path]::GetFullPath($pair.Source)
        $resolvedDestination = [IO.Path]::GetFullPath($pair.Destination)
        if ($resolvedSource -notin @((Join-Path $sourceRoot 'outputs\ChineseASR'),(Join-Path $sourceRoot 'work'))) { throw 'Unexpected source deletion target.' }
        if (-not $resolvedDestination.StartsWith($destinationRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected destination.' }
        if ((Get-Item -LiteralPath $resolvedSource).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Source is already a link.' }
        # Retain the old cache directories if their historic ACL prevents removal.
        $retired = $resolvedSource + '_迁移余留'
        if (Test-Path -LiteralPath $retired) { throw 'Retired directory already exists.' }
        Move-Item -LiteralPath $resolvedSource -Destination $retired
        New-Item -ItemType Junction -Path $resolvedSource -Target $resolvedDestination | Out-Null
        try {
            Remove-SourceTreeWithoutFollowingLinks $retired $retired
            if (Test-Path -LiteralPath $retired) { $remaining += @{Path=$retired;Reason='Historic cache permissions prevent removal; all business files were copied and verified.'} }
        }
        catch { $remaining += @{Path=$retired;Reason=$_.Exception.Message} }
    }
    $links = @(
        @{Path=Join-Path $destinationRoot '工作记录\submission-verify\model';Target=Join-Path $destinationRoot 'ChineseASR\submission\model'},
        @{Path=Join-Path $destinationRoot '工作记录\submission-verify\source_code\models\asr_model';Target=Join-Path $destinationRoot 'ChineseASR\models\asr_model'},
        @{Path=Join-Path $sourceRoot 'outputs\交接报告';Target=Join-Path $destinationRoot '交接报告'}
    )
    foreach ($link in $links) {
        if (-not (Test-Path -LiteralPath $link.Path)) { New-Item -ItemType Junction -Path $link.Path -Target $link.Target | Out-Null }
    }
    @{Verified=$verification;Remaining=$remaining;Destination=$destinationRoot;Date=(Get-Date).ToString('o')} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $recordDir 'migration_receipt.json') -Encoding utf8
    Get-Content -LiteralPath (Join-Path $recordDir 'migration_receipt.json')
}
