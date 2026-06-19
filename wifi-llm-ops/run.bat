@echo off
cd /d "%~dp0"
set "PROJ=%cd%"
title 校园WiFi体验保障与LLM运维助手

echo ========================================
echo   校园WiFi体验保障与LLM运维助手
echo   参考 Juniper Mist AI / Marvis AI
echo ========================================
echo.

:: ===== 检查 Python =====
echo [0/3] 检查 Python...
set "PY="
python --version >nul 2>nul && set "PY=python"
if not defined PY py --version >nul 2>nul && set "PY=py"
if not defined PY python3 --version >nul 2>nul && set "PY=python3"
if not defined PY (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)
%PY% --version
echo [OK] Python 已就绪

:: ===== 安装依赖 =====
echo.
echo [1/3] 安装依赖包...
%PY% -m pip install -r "%PROJ%\requirements.txt" -q
if %errorlevel% neq 0 (
    echo [警告] pip 安装失败，尝试使用国内镜像...
    %PY% -m pip install -r "%PROJ%\requirements.txt" -q -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo [OK] 依赖安装完成

:: ===== 检查数据文件 =====
echo.
echo [2/3] 检查数据文件...
if not exist "%USERPROFILE%\Desktop	rainingData.csv" (
    echo [提示] trainingData.csv 未在桌面找到
    echo 请确保 trainingData.csv 放在桌面，或修改 config.py 中的 DATA_PATH
    echo 数据下载: https://archive.ics.uci.edu/dataset/310/ujiindoorloc
) else (
    echo [OK] 数据文件已找到
)

:: ===== 数据处理 =====
echo.
echo [2/3] 处理数据...
%PY% "%PROJ%\data_processor.py"
if %errorlevel% neq 0 (
    echo [错误] 数据处理失败，请检查数据文件路径
    pause
    exit /b 1
)
echo [OK] 数据处理完成

:: ===== 启动 Streamlit =====
echo.
echo [3/3] 启动前端应用...

:: 创建 Streamlit 配置文件
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    echo [general] > "%USERPROFILE%\.streamlit\credentials.toml"
    echo email = "" >> "%USERPROFILE%\.streamlit\credentials.toml"
    echo [OK] Streamlit 配置文件已初始化
)
echo.
echo ========================================
echo   正在启动服务，请稍候...
echo   服务就绪后浏览器将自动打开
echo   地址: http://localhost:8501
echo   按 Ctrl+C 可停止应用
echo ========================================
echo.

:: 后台启动 Streamlit
start "Streamlit Server" cmd /c "cd /d %PROJ% && %PY% -m streamlit run app.py --server.port 8501"

:: 等待端口就绪（最多 60 秒）
echo 正在等待服务启动...
setlocal enabledelayedexpansion
set /a count=0
:wait_loop
timeout /t 2 /nobreak >nul
set /a count+=2
powershell -Command "try {$c=New-Object Net.Sockets.TcpClient('localhost',8501);$c.Close();exit 0}catch{exit 1}" >nul 2>nul
if !errorlevel! equ 0 goto server_ready
if !count! geq 60 goto timeout
goto wait_loop

:server_ready
echo [OK] 服务已就绪，正在打开浏览器...
start http://localhost:8501
echo.
echo 服务运行中。关闭此窗口不会停止服务。
echo 如需停止，请关闭 "Streamlit Server" 窗口或按 Ctrl+C。
echo.
pause
exit /b 0

:timeout
echo [警告] 服务启动超时（已等待 60 秒）
echo.
echo 可能原因：
echo   1. 首次冷启动 Python 较慢，再试一次通常能解决
echo   2. 防火墙阻止了 Python 监听 8501 端口
echo   3. 其他程序占用了 8501 端口
echo.
echo 请手动打开浏览器访问 http://localhost:8501
echo 如果仍无法打开，请运行 启动.bat（含端口清理）
echo.
pause
exit /b 1
