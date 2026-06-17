# 校园 WiFi 体验保障与 LLM 运维助手

> 参考 HPE Juniper Networking Mist AI / Marvis AI 的无线网络智能运维思路  
> FDE 无线网络智能运维培训 · 场景 4

## 项目概述

本项目构建了一个**校园 WiFi 体验保障原型系统**，基于公开数据集 UJIIndoorLoc，实现：

- 📡 **RSSI 质量评估**：计算每个位置的可见 AP 数、最强信号、平均信号
- 🗺️ **楼层热力图**：可视化展示 good/medium/poor 覆盖区域
- 🚨 **弱覆盖异常检测**：自动识别弱信号点位（378 个告警）
- 🤖 **LLM 排障助手**：基于 RSSI 证据 + WiFi 知识库，输出结构化诊断报告
- 📊 **Streamlit 交互前端**：楼栋/楼层筛选 + 诊断卡片 + 报告导出

## 系统架构

```
UJIIndoorLoc 数据
      ↓
[数据层]   pandas 加载 → 100→NaN 清洗 → 质量评估
      ↓
[检测层]   阈值规则: max_rssi<-85dBm, visible_ap<3
      ↓
[知识库]   WiFi 排障知识 (AP功率/遮挡/干扰/离线/容量/漫游)
      ↓
[LLM层]    Prompt + 证据 + 知识库 → 结构化诊断 JSON
      ↓
[前端层]   Streamlit + Plotly → 热力图 + 告警 + 诊断卡片
```

## 数据集

- **来源**: [UJIIndoorLoc](https://archive.ics.uci.edu/dataset/310/ujiindoorloc) (UCI ML Repository)
- **格式**: CSV, 19,937 采样点 × 529 列
- **字段**:
  - `WAP001` ~ `WAP520`: 各 AP 的 RSSI 值 (dBm)，`100` = 无信号
  - `LONGITUDE`, `LATITUDE`: 经纬度坐标
  - `FLOOR`: 楼层编号
  - `BUILDINGID`: 楼栋编号
  - `SPACEID`, `RELATIVEPOSITION`, `USERID`, `PHONEID`, `TIMESTAMP`: 辅助信息

## 快速开始

### 环境要求

- Python 3.8+
- 依赖: `pip install pandas numpy plotly streamlit`

### 运行步骤

```bash
# 1. 下载 UJIIndoorLoc trainingData.csv 放到桌面 (或修改 config.py 中的路径)

# 2. 运行数据处理流水线
python data_processor.py

# 3. 启动 Streamlit 前端
streamlit run app.py

# 4. 浏览器打开 http://localhost:8501
```

### 项目结构

```
wifi-llm-ops/
├── config.py           # 配置文件 (路径/阈值/LLM设置)
├── data_processor.py   # 数据处理流水线
├── llm_diagnosis.py    # LLM 排障助手 + WiFi 知识库
├── app.py              # Streamlit 前端 Demo
├── output/             # 数据处理结果
│   ├── all_points_annotated.csv  # 全量数据 (含质量评估)
│   ├── weak_points.csv           # 弱覆盖异常点
│   └── building_stats.csv        # 楼层覆盖统计
└── README.md
```

## 信号质量规则

| 等级 | 条件 | 颜色 |
|------|------|------|
| 🟢 Good | max_rssi ≥ -65 dBm | 绿 |
| 🟡 Medium | -85 ≤ max_rssi < -65 dBm | 黄 |
| 🔴 Poor | max_rssi < -85 dBm | 红 |
| ⚪ None | 无可检测信号 | 灰 |

## 异常检测规则

1. **弱信号**: `max_rssi < -85 dBm`
2. **AP 不足**: `visible_ap_count < 3`
3. **风险等级**: 同时满足 → `high`，单一条件 → `medium`

## LLM 诊断输出字段

```json
{
  "affected_area": "Building 1, Floor 3",
  "risk_level": "high",
  "possible_cause": "AP 离线或故障（可见AP数异常少）",
  "evidence": "max_rssi=-89dBm, visible_ap_count=2",
  "next_steps": ["检查AP在线状态", "检查PoE供电", "..."],
  "user_message": "您在1号楼第3层暂时搜不到WiFi热点...",
  "uncertainty": "缺少AP实时在线状态、吞吐量和信道利用率数据",
  "needed_data": "AP在线状态、实时流量、信道利用率、用户关联数"
}
```

## WiFi 排障知识库

| 类别 | 症状 | 排查方向 |
|------|------|----------|
| AP 功率 | 边缘弱信号 | 发射功率、天线方向 |
| 物理遮挡 | 方向性衰减 | 墙体/玻璃/金属 |
| 信道干扰 | 信号密集 | 频谱分析、信道切换 |
| AP 离线 | 大面积盲区 | PoE供电、AP状态 |
| 容量拥塞 | 信号好/吞吐低 | 关联用户数、负载均衡 |
| 漫游问题 | 移动中断 | 重叠覆盖、快速漫游 |

## 数据结果摘要

```
总采样点:     19,937
信号优秀:     15,622 (78.4%)
信号中等:      3,945 (19.8%)
信号差:          294 (1.5%)
无信号:           76 (0.4%)
弱覆盖告警:      378 (1.9%)
最差楼层:    Building 1 Floor 3 (21.2%弱覆盖)
```

## 交付物清单

- ✅ Python 数据处理流水线 (`data_processor.py`)
- ✅ WiFi 排障知识库 + LLM 诊断模块 (`llm_diagnosis.py`)
- ✅ Streamlit 交互式前端 (`app.py`)
- ✅ 数据处理结果 (output/)
- ✅ README 说明文档
- ✅PPT 演示文稿 (7页，见方案文档第7章)
- ✅测试截图
- ✅GitHub 仓库

## 参考来源

- [HPE Marvis AI](https://www.hpe.com/us/en/marvis-ai.html)
- [Juniper Mist AI | AI-Native Networking](https://www.juniper.net/us/en/products/mist-ai.html)
- [UJIIndoorLoc Dataset](https://archive.ics.uci.edu/dataset/310/ujiindoorloc)
- 开源数据可在本说明第三个链接下载
