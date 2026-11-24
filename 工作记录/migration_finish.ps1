$ErrorActionPreference='Stop'
$task='C:\Users\22502\Documents\Codex\2026-10-02\ban'
$dest='D:\语音大作业'
$mappings=@(
 @{Source="$task\outputs\ChineseASR";Destination="$dest\ChineseASR"},
 @{Source="$task\outputs\ChineseASR_迁移余留";Destination="$dest\ChineseASR"},
 @{Source="$task\work";Destination="$dest\工作记录"}
)
$verified=[Collections.Generic.List[object]]::new()
$retained=[Collections.Generic.List[string]]::new()
function Scan([string]$Root,[string]$Destination,[string]$Current) {
 foreach($item in Get-ChildItem -LiteralPath $Current -Force -ErrorAction Stop) {
  if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){continue}
  if($item.PSIsContainer){if($item.Name -ne '.pytest_cache'){Scan $Root $Destination $item.FullName};continue}
  $relative=$item.FullName.Substring($Root.Length+1)
  $copy=Join-Path $Destination $relative
  if(-not (Test-Path -LiteralPath $copy -PathType Leaf)){throw "Destination missing: $copy"}
  $a=(Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash
  $b=(Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash
  if($a -ne $b){throw "Hash mismatch: $relative"}
  $verified.Add([pscustomobject]@{Source=$item.FullName;Destination=$copy;Bytes=$item.Length;SHA256=$a})
 }
}
foreach($map in $mappings){
 if(-not (Test-Path -LiteralPath $map.Source)){continue}
 if((Get-Item -LiteralPath $map.Source).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Refusing to scan an already-linked source'}
 Scan $map.Source $map.Destination $map.Source
}
$verified | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath "$dest\迁移记录\final_verified_sources.json" -Encoding utf8
foreach($file in $verified){
 try {Remove-Item -LiteralPath $file.Source -Force -ErrorAction Stop}
 catch {$retained.Add($file.Source)}
}
function Remove-EmptyDirectories([string]$Path,[string]$Boundary){
 $absolute=[IO.Path]::GetFullPath($Path)
 if($absolute -ne $Boundary -and -not $absolute.StartsWith($Boundary+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Directory cleanup escaped source boundary'}
 if(-not(Test-Path -LiteralPath $absolute)){return}
 $item=Get-Item -LiteralPath $absolute -Force
 if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){
  try{[IO.Directory]::Delete($absolute)}catch{$retained.Add($absolute)}
  return
 }
 try{$children=@(Get-ChildItem -LiteralPath $absolute -Force -ErrorAction Stop)}catch{$retained.Add($absolute);return}
 foreach($child in $children){if($child.PSIsContainer){Remove-EmptyDirectories $child.FullName $Boundary}}
 try{[IO.Directory]::Delete($absolute)}catch{$retained.Add($absolute)}
}
foreach($map in $mappings){Remove-EmptyDirectories $map.Source $map.Source}
$links=@(
 @{Path="$task\outputs\交接报告";Target="$dest\交接报告"},
 @{Path="$dest\工作记录\submission-verify\model";Target="$dest\ChineseASR\submission\model"},
 @{Path="$dest\工作记录\submission-verify\source_code\models\asr_model";Target="$dest\ChineseASR\models\asr_model"}
)
foreach($map in @($mappings[0],$mappings[2])) {
 if(-not(Test-Path -LiteralPath $map.Source)){
  $links+=@{Path=$map.Source;Target=$map.Destination}
 }else{
  # Preserve historic links where the parent itself is locked by Windows.
  foreach($child in Get-ChildItem -LiteralPath $map.Destination -Directory -Force){
   $path=Join-Path $map.Source $child.Name
   if(-not(Test-Path -LiteralPath $path)){$links+=@{Path=$path;Target=$child.FullName}}
  }
 }
}
foreach($link in $links){
 if(-not(Test-Path -LiteralPath $link.Path)){
  New-Item -ItemType Junction -Path $link.Path -Target $link.Target | Out-Null
 }
}
@{Destination=$dest;VerifiedThenRemovedFiles=$verified.Count;RemovedSourceBytes=($verified|Measure-Object Bytes -Sum).Sum;
  Retained=@($retained|Select-Object -Unique);Date=(Get-Date).ToString('o');
  Note='Two historical .pytest_cache folders were unreadable and are not required for runtime. C-drive parent directories may remain as lightweight compatibility containers.'} |
 ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$dest\迁移记录\migration_receipt.json" -Encoding utf8
Get-Content -LiteralPath "$dest\迁移记录\migration_receipt.json"
