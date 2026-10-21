@echo off
chcp 65001 >nul
REM ============================================================
REM  航空发动机装配排产仿真系统 - 一键启动 / 重启脚本
REM  双击本文件即可：① 启动后端服务  ② 开启公网隧道
REM ============================================================

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PY=C:\Users\Administrator\miniconda3\envs\sim_engine\python.exe"
set "PROJ=C:\xjp\simpy2"

cd /d "%PROJ%"

echo.
echo [1/2] 正在启动后端服务 (uvicorn, 端口 8000) ...
start "AeroSim-Server" "%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

echo     等待服务就绪 ...
timeout /t 4 >nul

echo [2/2] 正在开启公网隧道 (cloudflared) ...
start "AeroSim-Tunnel" "%PROJ%\cloudflared.exe" tunnel --url http://localhost:8000

echo.
echo ============================================================
echo  已启动两个窗口：
echo    - AeroSim-Server : 后端服务 (勿关)
echo    - AeroSim-Tunnel : 公网隧道 (勿关)
echo.
echo  公网访问地址：请在 "AeroSim-Tunnel" 窗口里找到形如
echo      https://xxxx-xxxx-xxxx.trycloudflare.com  的那一行
echo  本地访问地址：http://localhost:8000
echo ============================================================
echo.
pause
