"""
校园WiFi体验保障系统 - 配置文件
参考 Juniper Mist AI / Marvis AI 思路
"""

# 数据路径
DATA_PATH = r"C:\Users\dengg\Desktop\trainingData.csv"
OUTPUT_DIR = r"C:\Users\dengg\Desktop\wifi-llm-ops\output"

# RSSI 阈值
RSSI_NO_SIGNAL = 100       # 100 表示无信号
RSSI_GOOD = -65            # >= -65 信号优秀
RSSI_MEDIUM = -85          # -85 ~ -65 信号中等，< -85 信号差

# 异常检测阈值
WEAK_RSSI_THRESHOLD = -85  # max_rssi 低于此值为弱信号
MIN_VISIBLE_AP = 3         # 可见 AP 少于 3 个为异常

# LLM 配置
LLM_MODEL = "gpt-4o"       # 或其他模型
LLM_TEMPERATURE = 0.3
OPENAI_API_KEY = "your-api-key-here"  # 使用前替换
