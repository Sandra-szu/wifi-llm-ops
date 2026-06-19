@echo off
cd /d "%~dp0"
set "PROJ=%cd%"
title 校园WiFi体验保障与LLM运维助手
color 0A

echo ========================================
echo   校园WiFi体验保障与LLM运维助手
echo ========================================
echo.

:: ===== 第0步：清理上次残留的 Streamlit 进程 =====
echo [0/4] 清理 8501 端口残留进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r ":8501.*LISTENING" 2^>nul') do (
    echo 发现 PID=%%a 正占用 8501 端口，强制结束...
    taskkill /F /PID %%a >nul 2>nul
)
timeout /t 1 /nobreak >nul
echo [OK] 端口已释放

:: ===== 第1步：检查 Python =====
echo.
echo [1/4] 检查 Python...
set "PY="
python --version >nul 2>nul && set "PY=python"
if not defined PY py --version >nul 2>nul && set "PY=py"
if not defined PY python3 --version >nul 2>nul && set "PY=python3"
if not defined PY (
    echo [错误] 没找到 Python！
    echo.
    echo 请去 https://www.python.org/downloads/ 下载安装
    echo 安装时一定要勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
%PY% --version
echo [OK] Python 已就绪

:: ===== 第2步：安装依赖 =====
echo.
echo [2/4] 安装依赖包...
%PY% -m pip install -r "%PROJ%\requirements.txt" -q
if %errorlevel% neq 0 (
    echo [提示] 默认源失败，换清华镜像源重试...
    %PY% -m pip install -r "%PROJ%\requirements.txt" -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo [错误] pip 安装依赖失败！请检查网络连接
        pause
        exit /b 1
    )
)
echo [OK] 依赖安装完成

:: ===== 第3步：检查数据文件 =====
echo.
echo [3/4] 检查数据文件...
if not exist "%USERPROFILE%\Desktop	rainingData.csv" (
    echo [警告] trainingData.csv 不在桌面！
    echo 请把 trainingData.csv 放到桌面，或修改 config.py 里的 DATA_PATH
    echo.
    echo 数据下载地址: https://archive.ics.uci.edu/dataset/310/ujiindoorloc
    echo.
    pause
    exit /b 1
)
echo [OK] 数据文件已找到

:: ===== 第4步：数据处理 =====
echo.
echo [4/4] 处理数据...
%PY% "%PROJ%\data_processor.py"
if %errorlevel% neq 0 (
    echo.
    echo [错误] 数据处理失败！可能原因:
    echo   1. trainingData.csv 文件损坏
    echo   2. 磁盘空间不足
    echo   3. pandas/numpy 版本不兼容
    echo.
    pause
    exit /b 1
)
echo [OK] 数据处理完成

:: ===== 启动 Streamlit =====
echo.
echo ========================================
echo   正在启动服务，请稍候...
echo   服务就绪后浏览器将自动打开
echo   地址: http://localhost:8501
echo   按 Ctrl+C 可停止
echo ========================================
echo.

:: 创建 Streamlit 配置文件
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    echo [general] > "%USERPROFILE%\.streamlit\credentials.toml"
    echo email = "" >> "%USERPROFILE%\.streamlit\credentials.toml"
    echo [OK] Streamlit 配置文件已初始化
)

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
echo ========================================
echo   服务运行中！
echo   关闭此窗口不会停止服务。
echo   如需停止，请关闭 "Streamlit Server" 窗口。
echo ========================================
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
echo 建议：再次双击运行本批处理（已自动清理端口残留）
echo.
pause
exit /b 1
