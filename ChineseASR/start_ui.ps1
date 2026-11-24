param([int]$Port = 7860, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = 'D:\Anaconda\envs\chinese-asr\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Please create the chinese-asr environment from environment.yml, then launch python app.py --inbrowser.'
}
$env:PATH = 'D:\Anaconda\envs\chinese-asr\Library\bin;D:\Anaconda\envs\chinese-asr;' + $env:PATH
$env:GRADIO_ANALYTICS_ENABLED = 'False'
$launchArgs = @('app.py', '--port', [string]$Port)
if (-not $NoBrowser) { $launchArgs += '--inbrowser' }
& $python @launchArgs
exit $LASTEXITCODE
