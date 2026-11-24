param([int]$Port=7860, [switch]$NoBrowser)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$condaCommand=Get-Command conda.exe,conda -ErrorAction SilentlyContinue|Select-Object -First 1
$candidates=@(
 'D:\Anaconda\Scripts\conda.exe',
 (Join-Path $env:USERPROFILE 'miniconda3\Scripts\conda.exe'),
 (Join-Path $env:USERPROFILE 'anaconda3\Scripts\conda.exe'),
 'C:\ProgramData\miniconda3\Scripts\conda.exe',
 'C:\ProgramData\anaconda3\Scripts\conda.exe'
)
$conda=if($condaCommand){$condaCommand.Source}else{$candidates|Where-Object {Test-Path -LiteralPath $_}|Select-Object -First 1}
if(-not $conda){throw 'Install Miniconda/Anaconda first, then run this launcher again. See README.md for manual Python setup.'}
$envs=(& $conda env list --json|ConvertFrom-Json).envs
$prefix=$envs|Where-Object {(Split-Path $_ -Leaf) -eq 'chinese-asr'}|Select-Object -First 1
if(-not $prefix){
 Write-Host 'Creating the chinese-asr environment. First-time setup requires Internet access.'
 & $conda env create -n chinese-asr -f (Join-Path $root 'ChineseASR\environment.yml')
 if($LASTEXITCODE -ne 0){throw 'Environment installation failed. See README.md.'}
 $prefix=(& $conda env list --json|ConvertFrom-Json).envs|Where-Object {(Split-Path $_ -Leaf) -eq 'chinese-asr'}|Select-Object -First 1
}
$python=Join-Path $prefix 'python.exe'
$env:PATH=(Join-Path $prefix 'Library\bin')+';'+$prefix+';'+$env:PATH
$env:GRADIO_ANALYTICS_ENABLED='False'
$env:GRADIO_TEMP_DIR=Join-Path $root '.runtime\gradio'
& $python (Join-Path $root 'ChineseASR\scripts\bootstrap_models.py')
if($LASTEXITCODE -ne 0){throw 'Model setup failed. Run the launcher again to resume.'}
Set-Location -LiteralPath (Join-Path $root 'ChineseASR')
$launchArgs=@('app.py','--port',[string]$Port)
if(-not $NoBrowser){$launchArgs+='--inbrowser'}
& $python @launchArgs
exit $LASTEXITCODE
