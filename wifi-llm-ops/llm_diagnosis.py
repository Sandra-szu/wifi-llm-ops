"""
LLM 排障助手模块
基于 RSSI 指标 + 空间上下文 + 知识库 → 结构化诊断输出
"""
import json
import os
from config import OUTPUT_DIR, LLM_MODEL, LLM_TEMPERATURE, WEAK_RSSI_THRESHOLD, MIN_VISIBLE_AP

# ============ WiFi 排障知识库 ============
WIFI_KNOWLEDGE_BASE = """
## WiFi 信号排障知识库

### 1. AP 功率配置不当
- 症状: 覆盖范围不足，边缘区域信号弱 (max_rssi < -75)
- 排查: 检查 AP 发射功率设置，建议 2.4GHz 12-20 dBm，5GHz 14-23 dBm
- 优化: 适当提高功率，但避免过高导致同频干扰

### 2. 物理遮挡
- 症状: 特定方向信号衰减严重，尤其是有墙体/玻璃/金属的区域
- 排查: 查看建筑平面图，确认 AP 与用户间有无障碍物
- 优化: 调整 AP 安装位置，增加 AP 密度，使用定向天线

### 3. 信道干扰
- 症状: visible_ap_count 正常但 avg_rssi 低，多个 AP 信号强度相近
- 排查: 使用频谱分析工具检查 2.4GHz 信道 1/6/11 和 5GHz 信道占用
- 优化: 切换到空闲信道，启用自动信道选择

### 4. AP 离线或故障
- 症状: 某区域突然出现大面积弱覆盖，visible_ap_count 骤降
- 排查: 检查 PoE 交换机供电状态，确认 AP 在线状态和 LED 指示灯
- 优化: 冗余 AP 部署，启用 AP 故障自动告警

### 5. 用户密度过高
- 症状: 人均带宽不足，RSSI 正常但吞吐量低
- 排查: 查看 AP 关联客户端数，超过 30 个客户端时性能下降明显
- 优化: 增加 AP 密度，启用负载均衡，开启 band steering

### 6. 漫游问题
- 症状: 用户在楼层间移动时连接中断或频繁切换
- 排查: 检查 AP 间覆盖重叠区域 (< 15% 或 > 30% 均有问题)
- 优化: 调整 AP 位置使重叠率 15-25%，启用 802.11r/k/v 快速漫游

### 7. 终端网卡差异
- 症状: 同一位置不同设备信号差异大
- 排查: 对比不同终端的 RSSI 测量值
- 优化: 确保 AP 兼容旧设备 (开启 b/g/n 混合模式)
"""


def build_llm_prompt(anomaly_points, floor_stats, knowledge_base=WIFI_KNOWLEDGE_BASE):
    """
    构建 LLM Prompt: 将异常点数据 + 楼层统计 + 知识库拼接成诊断请求
    """
    # 选取前10个异常点作为示例
    sample_points = anomaly_points.head(10)
    evidence_list = []
    for _, row in sample_points.iterrows():
        evidence_list.append({
            "building": int(row.get("BUILDINGID", "?")),
            "floor": int(row.get("FLOOR", "?")),
            "longitude": float(row.get("LONGITUDE", 0)),
            "latitude": float(row.get("LATITUDE", 0)),
            "max_rssi": float(row.get("max_rssi", 0)) if not pd.isna(row.get("max_rssi")) else None,
            "avg_rssi": float(row.get("avg_rssi", 0)) if not pd.isna(row.get("avg_rssi")) else None,
            "visible_ap_count": int(row.get("visible_ap_count", 0)),
            "signal_quality": row.get("signal_quality", "unknown"),
            "risk_level": row.get("risk_level", "low"),
            "evidence": row.get("evidence", ""),
        })

    prompt = f"""
你是一位校园WiFi网络运维专家，类似 Juniper Mist Marvis AI 的角色。
请基于以下数据对校园WiFi弱覆盖问题进行诊断。

## WiFi排障知识库
{knowledge_base}

## 楼层覆盖统计
{floor_stats.to_json(orient="records", force_ascii=False, indent=2)}

## 弱覆盖异常点（前10个）
{json.dumps(evidence_list, ensure_ascii=False, indent=2)}

## 任务要求
请对上述异常点进行诊断，输出 JSON 格式。JSON 必须包含以下字段：
- overall_assessment: 总体评估 (1-2句)
- anomaly_analysis: 数组，每个元素包含:
  - affected_area: "Building X, Floor Y" 格式
  - risk_level: high/medium/low
  - possible_cause: 最可能的原因（必须引用知识库中的具体编号，如"物理遮挡"）
  - evidence: 引用具体的 RSSI 数值和 AP 数量作为证据
  - next_steps: 建议的排查步骤（3-5条，面向网络管理员）
  - user_message: 面向学生/普通用户的友好解释 (1-2句)
  - uncertainty: 仅凭 RSSI 数据无法判断的内容
  - needed_data: 还需要补充哪些数据
- summary_report: 可供导出的一页摘要报告

注意：
1. 必须引用具体的 max_rssi, visible_ap_count 数值
2. 如果 visible_ap_count 低而 max_rssi 正常，优先怀疑 AP 离线
3. 如果 visible_ap_count 正常但 max_rssi 低，优先怀疑物理遮挡或功率不足
4. 面向普通用户的消息要简单易懂，面向管理员的消息要技术详细
"""
    return prompt


def diagnose_with_llm(anomaly_points, floor_stats, client=None):
    """
    调用 LLM 进行诊断
    - client: OpenAI client 对象（如果为 None 则使用模拟输出）
    """
    prompt = build_llm_prompt(anomaly_points, floor_stats)

    if client is None:
        return simulate_diagnosis(anomaly_points, floor_stats)

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是校园WiFi网络运维专家。必须严格按照要求的 JSON 格式输出诊断结果。"},
                {"role": "user", "content": prompt},
            ],
            temperature=LLM_TEMPERATURE,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"LLM 调用失败: {e}")
        return simulate_diagnosis(anomaly_points, floor_stats)


def simulate_diagnosis(anomaly_points, floor_stats):
    """
    当 LLM 不可用时生成模拟诊断结果
    基于规则生成合理的诊断
    """
    import pandas as pd

    results = []
    risk_stats = {"high": 0, "medium": 0, "low": 0}

    for _, row in anomaly_points.head(15).iterrows():
        building = int(row["BUILDINGID"])
        floor = int(row["FLOOR"])
        max_rssi = row["max_rssi"]
        ap_count = int(row["visible_ap_count"])

        risk = row.get("risk_level", "medium")
        risk_stats[risk] = risk_stats.get(risk, 0) + 1

        # 规则诊断
        if pd.notna(max_rssi) and max_rssi < WEAK_RSSI_THRESHOLD and ap_count >= MIN_VISIBLE_AP:
            cause = "物理遮挡或AP功率不足（信号弱但AP数正常）"
            steps = [
                "1. 检查 AP 发射功率是否低于建议值 (2.4G: 12-20dBm, 5G: 14-23dBm)",
                "2. 查看建筑平面图确认 AP 与覆盖盲区之间有无墙体/玻璃幕墙",
                "3. 使用频谱分析仪现场测试该区域信号衰减",
                "4. 考虑增加 AP 或调整现有 AP 安装位置/天线方向",
            ]
            user_msg = f"您在{building}号楼第{floor}层的WiFi信号不太好，可能是因为距离较远或有建筑物遮挡，我们会尽快派人检查。"
        elif ap_count < MIN_VISIBLE_AP:
            cause = "AP 离线或故障（可见AP数异常少）"
            steps = [
                "1. 登录控制器检查该区域 AP 在线状态",
                "2. 检查 PoE 交换机对应端口的供电状态",
                "3. 现场确认 AP LED 指示灯是否正常",
                "4. 如 AP 已离线，安排替换或重启",
                f"5. 临时方案：引导用户连接到邻近楼层信号（当前仅{ap_count}个AP可见）",
            ]
            user_msg = f"您在{building}号楼第{floor}层暂时搜不到WiFi热点，可能是设备维护中，请稍等片刻或前往邻近区域使用网络。"
        else:
            cause = "综合因素导致的覆盖质量下降"
            steps = [
                "1. 综合分析该区域 AP 布局和信道配置",
                "2. 检查近期是否有建筑改造或新增遮挡物",
                "3. 评估是否需要增加 AP 密度",
            ]
            user_msg = f"您在{building}号楼第{floor}层的WiFi体验可能不稳定，我们正在优化中。"

        results.append({
            "affected_area": f"Building {building}, Floor {floor}",
            "risk_level": risk,
            "possible_cause": cause,
            "evidence": f"max_rssi={max_rssi:.0f}dBm, visible_ap_count={ap_count}",
            "next_steps": steps,
            "user_message": user_msg,
            "uncertainty": "缺少 AP 实时在线状态、用户吞吐量和信道利用率数据，仅为基于 RSSI 的推断",
            "needed_data": "AP 在线状态、实时流量数据、信道利用率、用户关联数",
        })

    total_points = len(anomaly_points)
    return {
        "overall_assessment": f"当前校园WiFi共有 {total_points} 个弱覆盖异常点，"
                              f"其中高风险 {risk_stats['high']} 个、中风险 {risk_stats['medium']} 个，"
                              f"建议优先排查 AP 离线问题和物理遮挡区域。",
        "anomaly_analysis": results,
        "summary_report": f"""
===== 校园WiFi体验保障诊断报告 =====
异常点总数: {total_points}
高风险: {risk_stats['high']}
中风险: {risk_stats['medium']}
低风险: {risk_stats['low']}

涉及楼栋: {sorted(anomaly_points['BUILDINGID'].unique().astype(int).tolist())}
涉及楼层: {sorted(anomaly_points['FLOOR'].unique().astype(int).tolist())}

主要问题:
- AP 离线/故障: 可见AP数 < {MIN_VISIBLE_AP} 的点位
- 弱信号覆盖: max_rssi < {WEAK_RSSI_THRESHOLD} dBm 的点位

建议行动:
1. 优先检查 AP 在线状态和 PoE 供电
2. 对弱信号区域进行现场勘测
3. 根据覆盖盲区调整 AP 布局和功率
4. 持续监控并对比历史数据
"""
    }


if __name__ == "__main__":
    from config import WEAK_RSSI_THRESHOLD, MIN_VISIBLE_AP
    import pandas as pd

    # 测试模拟诊断
    weak_points = pd.read_csv(os.path.join(OUTPUT_DIR, "weak_points.csv"))
    building_stats = pd.read_csv(os.path.join(OUTPUT_DIR, "building_stats.csv"))
    result = simulate_diagnosis(weak_points, building_stats)
    print(json.dumps(result["overall_assessment"], ensure_ascii=False))
    print(result["summary_report"])
