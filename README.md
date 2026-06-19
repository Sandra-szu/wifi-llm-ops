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
- ✅ 一键启动脚本 (`run.bat` + `启动.bat`)
- ✅ PPT 演示文稿 (7页，见方案文档第7章)
- ✅测试截图
- ✅GitHub 仓库

## 参考来源

- [HPE Marvis AI](https://www.hpe.com/us/en/marvis-ai.html)
- [Juniper Mist AI | AI-Native Networking](https://www.juniper.net/us/en/products/mist-ai.html)
- [UJIIndoorLoc Dataset](https://archive.ics.uci.edu/dataset/310/ujiindoorloc)
- 开源数据可在本说明第三个链接下载
