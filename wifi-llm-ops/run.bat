@echo off
chcp 65001 >nul 2>&1
title 校园WiFi体验保障与LLM运维助手

echo ========================================
echo   校园WiFi体验保障与LLM运维助手
echo   参考 Juniper Mist AI / Marvis AI
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)
echo [OK] Python 已就绪

:: 安装依赖
echo.
echo [1/3] 安装依赖包...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [警告] pip 安装失败，尝试使用国内镜像...
    pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo [OK] 依赖安装完成

:: 检查数据文件
echo.
echo [2/3] 检查数据文件...
if not exist "C:\Users\%USERNAME%\Desktop\trainingData.csv" (
    echo [提示] trainingData.csv 未在桌面找到
    echo 请确保 trainingData.csv 放在桌面，或修改 config.py 中的 DATA_PATH
    echo 数据下载: https://archive.ics.uci.edu/dataset/310/ujiindoorloc
) else (
    echo [OK] 数据文件已找到
)

:: 数据处理
echo.
echo [2/3] 处理数据...
python data_processor.py
if %errorlevel% neq 0 (
    echo [错误] 数据处理失败，请检查数据文件路径
    pause
    exit /b 1
)
echo [OK] 数据处理完成

:: 启动 Streamlit
echo.
echo [3/3] 启动前端应用...
echo.
echo ╔════════════════════════════════════════════╗
echo ║  浏览器将打开 http://localhost:8501      ║
echo ║  按 Ctrl+C 可以停止应用                  ║
echo ╚════════════════════════════════════════════╝
echo.
start http://localhost:8501
streamlit run app.py --server.port 8501
