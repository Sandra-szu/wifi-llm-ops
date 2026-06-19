"""
数据加载、质量评估、异常检测模块
UJIIndoorLoc 数据集处理
"""
import os
import json
import pandas as pd
import numpy as np
from config import (
    DATA_PATH, OUTPUT_DIR, RSSI_NO_SIGNAL,
    RSSI_GOOD, RSSI_MEDIUM, WEAK_RSSI_THRESHOLD, MIN_VISIBLE_AP
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_data(path=DATA_PATH):
    """加载 CSV 数据"""
    print(f"正在加载数据: {path}")
    df = pd.read_csv(path)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")
    return df


def clean_data(df):
    """
    清洗数据：
    - 将 100 替换为 NaN（表示无信号）
    - 分离 AP 列和标签列
    """
    wap_cols = [c for c in df.columns if c.startswith("WAP")]
    label_cols = [c for c in df.columns if not c.startswith("WAP")]

    # AP 数据子集
    rssi = df[wap_cols].copy()
    rssi = rssi.replace(RSSI_NO_SIGNAL, np.nan)

    return rssi, df[label_cols]


def compute_quality(rssi_df):
    """
    对每个采样点计算质量指标:
    - visible_ap_count: 能扫到的 AP 数量
    - max_rssi: 最强信号
    - avg_rssi: 平均信号
    - min_rssi: 最弱信号（排除无信号）
    """
    quality = pd.DataFrame()

    # 非 NaN 计数
    quality["visible_ap_count"] = rssi_df.notna().sum(axis=1)
    quality["max_rssi"] = rssi_df.max(axis=1)
    quality["avg_rssi"] = rssi_df.mean(axis=1)
    quality["min_rssi"] = rssi_df.min(axis=1)

    return quality


def classify_signal(quality_df):
    """
    根据 max_rssi 进行信号质量分级
    good:   max_rssi >= -65 (信号优秀)
    medium: -85 <= max_rssi < -65 (信号中等)
    poor:   max_rssi < -85 (信号差)
    none:   max_rssi 为 NaN (无信号)
    """
    conditions = [
        quality_df["max_rssi"] >= RSSI_GOOD,
        (quality_df["max_rssi"] >= RSSI_MEDIUM) & (quality_df["max_rssi"] < RSSI_GOOD),
        quality_df["max_rssi"] < RSSI_MEDIUM,
    ]
    choices = ["good", "medium", "poor"]

    quality_df["signal_quality"] = np.select(conditions, choices, default="none")
    return quality_df


def detect_anomalies(df_all, quality_df):
    """
    检测弱覆盖异常点
    规则:
    1. max_rssi < -85 dBm
    2. visible_ap_count < 3
    """
    anomalies = df_all.copy()

    # 弱信号标记
    anomalies["is_weak_rssi"] = quality_df["max_rssi"] < WEAK_RSSI_THRESHOLD
    anomalies["is_few_ap"] = quality_df["visible_ap_count"] < MIN_VISIBLE_AP
    anomalies["is_anomaly"] = anomalies["is_weak_rssi"] | anomalies["is_few_ap"]

    # 风险等级
    conditions = [
        anomalies["is_weak_rssi"] & anomalies["is_few_ap"],
        anomalies["is_weak_rssi"],
        anomalies["is_few_ap"],
    ]
    choices = ["high", "medium", "medium"]
    anomalies["risk_level"] = np.select(conditions, choices, default="low")

    return anomalies


def build_evidence(row):
    """为异常点生成证据字符串"""
    parts = []
    if row["is_weak_rssi"]:
        parts.append(f"max_rssi={row['max_rssi']:.0f} dBm (弱信号,阈值 {WEAK_RSSI_THRESHOLD} dBm)")
    if row["is_few_ap"]:
        parts.append(f"visible_ap_count={row['visible_ap_count']} (AP数不足,阈值 {MIN_VISIBLE_AP})")
    return "; ".join(parts)


def compute_building_stats(df_all, quality_df):
    """
    按楼栋+楼层聚合统计
    返回每层的: 采样点数、弱覆盖点数、平均max_rssi、平均可见AP数、弱覆盖比例
    """
    stats = df_all.groupby(["BUILDINGID", "FLOOR"]).agg(
        total_points=("SPACEID", "count"),
        avg_max_rssi=("max_rssi", "mean"),
        avg_visible_ap=("visible_ap_count", "mean"),
        weak_points=("is_anomaly", "sum"),
        avg_rssi=("avg_rssi", "mean"),
    ).reset_index()

    stats["weak_ratio"] = (stats["weak_points"] / stats["total_points"] * 100).round(1)
    stats["avg_max_rssi"] = stats["avg_max_rssi"].round(1)
    stats["avg_visible_ap"] = stats["avg_visible_ap"].round(1)
    stats["avg_rssi"] = stats["avg_rssi"].round(1)

    return stats


def process_all():
    """完整数据处理流水线"""
    print("=" * 60)
    print("校园WiFi体验保障 - 数据处理流水线")
    print("=" * 60)

    # 1. 加载
    df = load_data()

    # 2. 清洗
    rssi_df, labels_df = clean_data(df)
    print(f"AP列数: {rssi_df.shape[1]}, 标签列: {list(labels_df.columns)}")

    # 3. 质量评估
    quality_df = compute_quality(rssi_df)
    quality_df = classify_signal(quality_df)
    print(f"\n信号质量分布:\n{quality_df['signal_quality'].value_counts()}")
    print(f"\n质量指标统计:\n{quality_df.describe()}")

    # 4. 合并数据
    df_all = pd.concat([labels_df, quality_df], axis=1)

    # 5. 异常检测
    df_all = detect_anomalies(df_all, quality_df)
    anomaly_count = df_all["is_anomaly"].sum()
    print(f"\n异常检测: {anomaly_count} 个弱覆盖点 ({anomaly_count/len(df_all)*100:.1f}%)")

    # 6. 生成证据
    df_all["evidence"] = df_all.apply(build_evidence, axis=1)

    # 7. 楼层统计
    building_stats = compute_building_stats(df_all, quality_df)
    print(f"\n楼层覆盖统计 (前10):\n{building_stats.head(10)}")

    # 8. 导出结果
    weak_points = df_all[df_all["is_anomaly"]].copy()
    weak_points.to_csv(os.path.join(OUTPUT_DIR, "weak_points.csv"), index=False)
    building_stats.to_csv(os.path.join(OUTPUT_DIR, "building_stats.csv"), index=False)
    df_all.to_csv(os.path.join(OUTPUT_DIR, "all_points_annotated.csv"), index=False)

    print(f"\n结果已导出到: {OUTPUT_DIR}")
    print(f"  - all_points_annotated.csv: 全量数据(含质量评估)")
    print(f"  - weak_points.csv: 弱覆盖点({len(weak_points)}条)")
    print(f"  - building_stats.csv: 楼层统计")

    return df_all, weak_points, building_stats, rssi_df


if __name__ == "__main__":
    process_all()
