"""Personalized anomaly scoring for daily IoT behavior windows."""
import json
import statistics
from datetime import datetime

from sklearn.ensemble import IsolationForest

import db

FEATURES = (
    "door_events",
    "water_liters",
    "activity_minutes",
    "room_transitions",
    "night_activity",
    "fall_confidence",
    "still_minutes",
)
FEATURE_LABELS = {
    "door_events": "门磁活动",
    "water_liters": "用水量",
    "activity_minutes": "活动时长",
    "room_transitions": "房间转移",
    "night_activity": "夜间活动",
    "fall_confidence": "跌倒姿态置信度",
    "still_minutes": "静止时长",
}
MIN_PERSONAL_SAMPLES = 7


def _vector(row):
    return [float(row.get(feature, 0) or 0) for feature in FEATURES]


def _baseline_rows(elder_id):
    return db.query(
        """SELECT * FROM sensor_readings WHERE elder_id=?
           AND source IN ('synthetic_baseline','device')
           ORDER BY observed_at DESC LIMIT 30""",
        (elder_id,),
    )


def evaluate(elder_id, reading):
    """Fit an Isolation Forest on the elder's history and score one new window."""
    training_rows = _baseline_rows(elder_id)
    scope = "personal"
    if len(training_rows) < MIN_PERSONAL_SAMPLES:
        training_rows = db.query(
            """SELECT * FROM sensor_readings WHERE source IN ('synthetic_baseline','device')
               ORDER BY observed_at DESC LIMIT 500"""
        )
        scope = "community_cold_start"
    if len(training_rows) < MIN_PERSONAL_SAMPLES:
        raise ValueError("行为样本不足，无法建立异常检测基线")

    matrix = [_vector(dict(row)) for row in training_rows]
    model = IsolationForest(
        n_estimators=128,
        contamination=0.08,
        random_state=42,
    )
    model.fit(matrix)
    baseline_scores = model.score_samples(matrix)
    current_vector = _vector(reading)
    model_score = float(model.score_samples([current_vector])[0])
    percentile = round(
        sum(float(score) >= model_score for score in baseline_scores) / len(baseline_scores) * 100,
        1,
    )

    means = [statistics.fmean(column) for column in zip(*matrix)]
    deviations = [statistics.pstdev(column) or 1.0 for column in zip(*matrix)]
    feature_summary = {
        feature: round(mean, 2)
        for feature, mean in zip(FEATURES, means)
    }
    unusual = sorted(
        (
            abs(value - mean) / deviation,
            feature,
            value,
            mean,
        )
        for feature, value, mean, deviation in zip(FEATURES, current_vector, means, deviations)
    )
    reasons = []
    for _, feature, value, mean in reversed(unusual[-2:]):
        if mean > 0 and abs(value - mean) / mean >= 0.35:
            direction = "高于" if value > mean else "低于"
            reasons.append(f"{FEATURE_LABELS[feature]}{direction}个人均值 {abs(value - mean) / mean:.0%}")
    if percentile >= 80:
        detail = "；".join(reasons) or "行为组合偏离个人近期基线"
        reason = f"Isolation Forest 判为个人行为异常（异常分位 {percentile:.1f}%）：{detail}"
    else:
        reason = f"行为处于个人近期常态范围（异常分位 {percentile:.1f}%）"

    fall_signal = float(reading.get("fall_confidence", 0) or 0) >= 0.85 and float(reading.get("still_minutes", 0) or 0) >= 10
    if fall_signal or percentile >= 98.5:
        level = "red"
    elif percentile >= 80:
        level = "yellow"
    else:
        level = "green"

    db.execute(
        """INSERT INTO behavior_baselines (elder_id, trained_at, sample_count, scope, feature_summary)
           VALUES (?,?,?,?,?)
           ON CONFLICT(elder_id) DO UPDATE SET trained_at=excluded.trained_at,
             sample_count=excluded.sample_count, scope=excluded.scope,
             feature_summary=excluded.feature_summary""",
        (
            elder_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            len(matrix),
            scope,
            json.dumps(feature_summary, ensure_ascii=False),
        ),
    )
    return {
        "level": level,
        "anomaly_percentile": percentile,
        "model_score": round(model_score, 4),
        "baseline_scope": scope,
        "sample_count": len(matrix),
        "reason": reason,
    }
