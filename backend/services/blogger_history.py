from __future__ import annotations

"""博主历史分析模块 — 阶段6

分析博主历史发布内容的风险趋势，追踪风险维度变化，
生成博主风险画像（长期风险偏好），基于历史数据预测未来风险。
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskTrendPoint:
    """风险趋势数据点"""
    date: str = ""
    overall_score: float = 0.0
    dimensions: Dict[str, float] = field(default_factory=dict)
    risk_level: str = "green"
    content_preview: str = ""


@dataclass
class DimensionChange:
    """风险维度变化"""
    dimension: str = ""
    direction: str = ""          # rising / falling / stable
    current_score: float = 0.0
    previous_score: float = 0.0
    change_rate: float = 0.0     # 变化率
    trend_description: str = ""


@dataclass
class RiskProfile:
    """博主风险画像"""
    blogger_id: str = ""
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    risk_level_distribution: Dict[str, int] = field(default_factory=dict)
    high_risk_dimensions: List[str] = field(default_factory=list)
    risk_tolerance: str = "moderate"     # conservative / moderate / aggressive
    risk_pattern: str = ""               # 风险模式描述
    trend_summary: str = ""              # 趋势摘要
    dimension_changes: List[DimensionChange] = field(default_factory=list)
    trend_data: List[RiskTrendPoint] = field(default_factory=list)
    prediction: Dict = field(default_factory=dict)
    confidence: float = 0.0


class BloggerHistoryAnalyzer:
    """博主历史分析器"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def analyze_history(self, blogger_id: str, db=None) -> RiskProfile:
        """分析博主历史风险趋势

        Args:
            blogger_id: 博主ID
            db: 数据库会话

        Returns:
            RiskProfile
        """
        profile = RiskProfile(blogger_id=blogger_id)

        history_records = self._fetch_history(blogger_id, db)
        if not history_records:
            profile.trend_summary = "暂无历史分析数据"
            return profile

        profile.total_analyses = len(history_records)
        profile.trend_data = self._build_trend_data(history_records)
        profile.risk_level_distribution = self._calc_risk_distribution(history_records)
        profile.avg_risk_score = self._calc_avg_score(history_records)
        profile.high_risk_dimensions = self._identify_high_risk_dims(history_records)
        profile.dimension_changes = self._track_dimension_changes(history_records)
        profile.risk_tolerance = self._infer_risk_tolerance(history_records)
        profile.confidence = self._calc_confidence(history_records)

        profile.risk_pattern = self._generate_risk_pattern(profile)
        profile.trend_summary = self._generate_trend_summary(profile)
        profile.prediction = self._predict_future_risk(profile)

        return profile

    def get_risk_profile(self, blogger_id: str, db=None) -> RiskProfile:
        """获取博主风险画像（简化版）"""
        return self.analyze_history(blogger_id, db)

    def _fetch_history(self, blogger_id: str, db=None) -> List[dict]:
        """从数据库获取博主历史分析记录"""
        if db is None:
            from backend.database import SessionLocal
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            from backend.models import Task, RiskItem, AnalysisSummary

            tasks = (
                db.query(Task)
                .filter(Task.status == "completed")
                .order_by(Task.created_at.desc())
                .limit(50)
                .all()
            )

            records = []
            for task in tasks:
                summary = (
                    db.query(AnalysisSummary)
                    .filter(AnalysisSummary.task_id == task.id)
                    .first()
                )
                risk_items = (
                    db.query(RiskItem)
                    .filter(RiskItem.task_id == task.id)
                    .all()
                )

                dimensions = {}
                for ri in risk_items:
                    dimensions[ri.dimension] = {
                        "severity": ri.severity,
                        "evidence": ri.evidence or "",
                    }

                record = {
                    "task_id": task.id,
                    "created_at": task.created_at.isoformat() if task.created_at else "",
                    "overall_score": summary.overall_score if summary else 0,
                    "suggestion": summary.suggestion if summary else "",
                    "dimensions": dimensions,
                    "text_preview": (task.text or "")[:100],
                }

                if summary and summary.dimensions_json:
                    try:
                        dim_data = json.loads(summary.dimensions_json)
                        if isinstance(dim_data, list):
                            for d in dim_data:
                                name = d.get("name", "")
                                if name:
                                    record["dimensions"][name] = {
                                        "score": d.get("score", 0),
                                        "severity": d.get("severity", "green"),
                                    }
                    except (json.JSONDecodeError, TypeError):
                        pass

                records.append(record)

            return records

        except Exception as e:
            logger.error("获取博主历史记录失败: %s", e)
            return []
        finally:
            if should_close:
                db.close()

    def _build_trend_data(self, records: List[dict]) -> List[RiskTrendPoint]:
        """构建风险趋势数据"""
        trend = []
        for r in records:
            date_str = r.get("created_at", "")[:10]
            dim_scores = {}
            for dim_name, dim_data in r.get("dimensions", {}).items():
                if isinstance(dim_data, dict):
                    dim_scores[dim_name] = dim_data.get("score", 0)

            score = r.get("overall_score", 0)
            level = "green"
            if score >= 80:
                level = "red"
            elif score >= 60:
                level = "orange"
            elif score >= 40:
                level = "yellow"

            trend.append(RiskTrendPoint(
                date=date_str,
                overall_score=float(score),
                dimensions=dim_scores,
                risk_level=level,
                content_preview=r.get("text_preview", ""),
            ))

        trend.reverse()
        return trend

    def _calc_risk_distribution(self, records: List[dict]) -> Dict[str, int]:
        """计算风险等级分布"""
        dist = {"green": 0, "yellow": 0, "orange": 0, "red": 0}
        for r in records:
            score = r.get("overall_score", 0)
            if score >= 80:
                dist["red"] += 1
            elif score >= 60:
                dist["orange"] += 1
            elif score >= 40:
                dist["yellow"] += 1
            else:
                dist["green"] += 1
        return dist

    def _calc_avg_score(self, records: List[dict]) -> float:
        """计算平均风险分"""
        if not records:
            return 0.0
        total = sum(r.get("overall_score", 0) for r in records)
        return round(total / len(records), 1)

    def _identify_high_risk_dims(self, records: List[dict]) -> List[str]:
        """识别高频高风险维度"""
        dim_counts: Dict[str, int] = {}
        for r in records:
            for dim_name, dim_data in r.get("dimensions", {}).items():
                if isinstance(dim_data, dict):
                    severity = dim_data.get("severity", "green")
                    if severity in ("orange", "red"):
                        dim_counts[dim_name] = dim_counts.get(dim_name, 0) + 1

        sorted_dims = sorted(dim_counts.items(), key=lambda x: x[1], reverse=True)
        return [d[0] for d in sorted_dims[:5]]

    def _track_dimension_changes(self, records: List[dict]) -> List[DimensionChange]:
        """追踪风险维度变化"""
        if len(records) < 2:
            return []

        dim_scores_over_time: Dict[str, List[float]] = {}
        for r in records:
            for dim_name, dim_data in r.get("dimensions", {}).items():
                if isinstance(dim_data, dict):
                    score = dim_data.get("score", 0)
                    if isinstance(score, (int, float)):
                        dim_scores_over_time.setdefault(dim_name, []).append(float(score))

        changes = []
        for dim_name, scores in dim_scores_over_time.items():
            if len(scores) < 2:
                continue

            recent_avg = sum(scores[:3]) / min(len(scores), 3)
            older_avg = sum(scores[-3:]) / min(len(scores), 3)

            if older_avg == 0:
                change_rate = 0.0
            else:
                change_rate = (recent_avg - older_avg) / older_avg

            if change_rate > 0.1:
                direction = "rising"
                desc = f"近期{dim_name}风险呈上升趋势（+{change_rate:.0%}）"
            elif change_rate < -0.1:
                direction = "falling"
                desc = f"近期{dim_name}风险呈下降趋势（{change_rate:.0%}）"
            else:
                direction = "stable"
                desc = f"近期{dim_name}风险保持稳定"

            changes.append(DimensionChange(
                dimension=dim_name,
                direction=direction,
                current_score=round(recent_avg, 1),
                previous_score=round(older_avg, 1),
                change_rate=round(change_rate, 3),
                trend_description=desc,
            ))

        changes.sort(key=lambda c: abs(c.change_rate), reverse=True)
        return changes[:8]

    def _infer_risk_tolerance(self, records: List[dict]) -> str:
        """推断风险容忍度"""
        if not records:
            return "moderate"

        high_risk_count = sum(
            1 for r in records if r.get("overall_score", 0) >= 60
        )
        ratio = high_risk_count / len(records)

        if ratio > 0.4:
            return "aggressive"
        elif ratio > 0.15:
            return "moderate"
        return "conservative"

    def _calc_confidence(self, records: List[dict]) -> float:
        """计算分析置信度"""
        confidence = 0.0
        count = len(records)

        if count >= 20:
            confidence += 0.5
        elif count >= 10:
            confidence += 0.4
        elif count >= 5:
            confidence += 0.3
        elif count >= 2:
            confidence += 0.2
        else:
            confidence += 0.1

        dim_coverage = set()
        for r in records:
            for dim_name in r.get("dimensions", {}):
                dim_coverage.add(dim_name)
        if len(dim_coverage) >= 5:
            confidence += 0.3
        elif len(dim_coverage) >= 3:
            confidence += 0.2
        else:
            confidence += 0.1

        if count >= 3:
            confidence += 0.2

        return round(min(confidence, 1.0), 2)

    def _generate_risk_pattern(self, profile: RiskProfile) -> str:
        """生成风险模式描述"""
        parts = []

        if profile.risk_tolerance == "aggressive":
            parts.append("高风险偏好型博主，频繁触碰风险边界")
        elif profile.risk_tolerance == "moderate":
            parts.append("中等风险偏好型博主，偶有风险内容")
        else:
            parts.append("低风险偏好型博主，内容较为安全")

        if profile.high_risk_dimensions:
            parts.append(f"高频风险维度: {', '.join(profile.high_risk_dimensions[:3])}")

        rising = [c for c in profile.dimension_changes if c.direction == "rising"]
        if rising:
            parts.append(f"风险上升趋势维度: {', '.join(c.dimension for c in rising[:3])}")

        return "；".join(parts)

    def _generate_trend_summary(self, profile: RiskProfile) -> str:
        """生成趋势摘要"""
        if not profile.trend_data:
            return "暂无趋势数据"

        recent = profile.trend_data[-3:] if len(profile.trend_data) >= 3 else profile.trend_data
        avg_recent = sum(t.overall_score for t in recent) / len(recent)

        if len(profile.trend_data) > 3:
            older = profile.trend_data[:3]
            avg_older = sum(t.overall_score for t in older) / len(older)
        else:
            avg_older = avg_recent

        if avg_recent > avg_older + 5:
            return f"近期风险呈上升趋势（近3次均值{avg_recent:.0f}分），需关注"
        elif avg_recent < avg_older - 5:
            return f"近期风险呈下降趋势（近3次均值{avg_recent:.0f}分），表现良好"
        return f"近期风险保持稳定（均值{avg_recent:.0f}分）"

    def _predict_future_risk(self, profile: RiskProfile) -> Dict:
        """基于历史数据预测未来风险"""
        prediction = {
            "next_risk_level": "green",
            "predicted_score": 0.0,
            "confidence": 0.0,
            "risk_factors": [],
            "mitigation_suggestions": [],
        }

        if not profile.trend_data or len(profile.trend_data) < 2:
            prediction["confidence"] = 0.1
            return prediction

        scores = [t.overall_score for t in profile.trend_data]
        avg_score = sum(scores) / len(scores)

        if len(scores) >= 3:
            recent_trend = (scores[-1] - scores[-3]) / 2
            predicted = avg_score + recent_trend
        else:
            predicted = avg_score

        predicted = max(0, min(100, predicted))
        prediction["predicted_score"] = round(predicted, 1)

        if predicted >= 80:
            prediction["next_risk_level"] = "red"
        elif predicted >= 60:
            prediction["next_risk_level"] = "orange"
        elif predicted >= 40:
            prediction["next_risk_level"] = "yellow"
        else:
            prediction["next_risk_level"] = "green"

        prediction["confidence"] = round(min(0.9, profile.confidence * 0.8), 2)

        rising_dims = [c for c in profile.dimension_changes if c.direction == "rising"]
        for c in rising_dims[:3]:
            prediction["risk_factors"].append({
                "dimension": c.dimension,
                "reason": c.trend_description,
            })

        for dim in profile.high_risk_dimensions[:3]:
            prediction["mitigation_suggestions"].append(
                f"关注{dim}维度风险，避免相关敏感内容"
            )

        return prediction
