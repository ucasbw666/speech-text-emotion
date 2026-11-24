@echo off
cd /d "%~dp0ChineseASR"
if not exist "D:\Anaconda\envs\chinese-asr\python.exe" (
  echo Please create the chinese-asr environment from environment.yml.
  pause
  exit /b 1
)
set "PATH=D:\Anaconda\envs\chinese-asr\Library\bin;D:\Anaconda\envs\chinese-asr;%PATH%"
set "GRADIO_ANALYTICS_ENABLED=False"
"D:\Anaconda\envs\chinese-asr\python.exe" app.py --inbrowser
pause
