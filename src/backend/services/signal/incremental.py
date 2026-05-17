"""增量检测器 - 识别新上榜/排名变化/下榜事件"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from backend.models import SignalRecord
from backend.services.signal.models import Signal, RankPoint

logger = logging.getLogger(__name__)


class IncrementalDetector:
    """增量检测器"""

    # 信号有效期：超过此时间的旧记录不再参与增量对比
    HISTORY_WINDOW_HOURS = 24

    def __init__(self, db: Session):
        self.db = db

    async def detect(
        self, new_signals: Dict[str, List[Signal]]
    ) -> Dict[str, List[Signal]]:
        """与数据库历史对比，标记增量信号

        返回: {
            "new": [新上榜信号],
            "changed": [排名变化信号],
            "unchanged": [未变化信号],
        }
        """
        result = {"new": [], "changed": [], "unchanged": []}

        for platform_id, signals in new_signals.items():
            # 查询该平台的历史记录
            cutoff = datetime.now(timezone.utc) - timedelta(
                hours=self.HISTORY_WINDOW_HOURS
            )
            history_records = (
                self.db.query(SignalRecord)
                .filter(
                    SignalRecord.source_platform == platform_id,
                    SignalRecord.last_seen >= cutoff,
                )
                .all()
            )

            # 构建历史标题索引
            history_map: Dict[str, SignalRecord] = {}
            for rec in history_records:
                normalized = self._normalize_title(rec.title)
                history_map[normalized] = rec

            # 当前批次标题集合
            current_titles: Set[str] = set()

            for signal in signals:
                normalized = self._normalize_title(signal.title)
                current_titles.add(normalized)

                if normalized in history_map:
                    existing = history_map[normalized]
                    rank_change = self._compute_rank_change(signal, existing)

                    # 更新已有记录
                    existing.last_seen = datetime.now(timezone.utc)
                    existing.appearance_count += 1

                    # 更新排名时间线
                    if signal.rank is not None:
                        timeline = json.loads(existing.rank_timeline or "[]")
                        timeline.append(
                            {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "rank": signal.rank,
                            }
                        )
                        existing.rank_timeline = json.dumps(timeline)
                        existing.rank = signal.rank

                    if rank_change is not None and abs(rank_change) >= 2:
                        signal.is_new = False
                        result["changed"].append(signal)
                    else:
                        signal.is_new = False
                        result["unchanged"].append(signal)
                else:
                    # 新上榜
                    signal.is_new = True
                    result["new"].append(signal)

            # 标记下榜事件
            dropped = self._mark_dropped(platform_id, current_titles)
            if dropped:
                logger.info(
                    "IncrementalDetector: %s 有 %d 个事件下榜",
                    platform_id, len(dropped),
                )

        # 持久化新信号到数据库
        for signal in result["new"]:
            self._save_signal(signal)
        for signal in result["changed"]:
            # changed 的信号已在上面更新了历史记录
            pass

        self.db.commit()

        logger.info(
            "IncrementalDetector: 检测完成 - 新上榜 %d, 排名变化 %d, 未变化 %d",
            len(result["new"]), len(result["changed"]), len(result["unchanged"]),
        )
        return result

    def _compute_rank_change(
        self, current: Signal, history: SignalRecord
    ) -> Optional[int]:
        """计算排名变化值，正值表示排名上升"""
        if current.rank is None or history.rank is None:
            return None
        return history.rank - current.rank  # 排名数字变小=上升

    def _mark_dropped(
        self, platform: str, current_titles: Set[str]
    ) -> List[SignalRecord]:
        """识别已下榜的事件"""
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.HISTORY_WINDOW_HOURS
        )
        old_records = (
            self.db.query(SignalRecord)
            .filter(
                SignalRecord.source_platform == platform,
                SignalRecord.last_seen >= cutoff,
            )
            .all()
        )

        dropped = []
        for rec in old_records:
            normalized = self._normalize_title(rec.title)
            if normalized not in current_titles:
                dropped.append(rec)
        return dropped

    def _save_signal(self, signal: Signal) -> SignalRecord:
        """将新信号持久化到数据库"""
        if signal.rank_timeline:
            timeline_json = json.dumps([
                {"timestamp": rp.timestamp.isoformat(), "rank": rp.rank}
                for rp in signal.rank_timeline
            ])
        else:
            timeline_json = "[]"

        record = SignalRecord(
            signal_id=signal.signal_id,
            source_platform=signal.source_platform,
            title=signal.title,
            url=signal.url,
            rank=signal.rank,
            rank_timeline=timeline_json,
            first_seen=signal.first_seen,
            last_seen=signal.last_seen,
            appearance_count=signal.appearance_count,
            is_new=signal.is_new,
            signal_type=signal.signal_type.value if isinstance(signal.signal_type, type) else signal.signal_type,
            category=signal.category.value if signal.category and hasattr(signal.category, 'value') else (signal.category or None),
            raw_data=json.dumps(signal.raw_data) if signal.raw_data else None,
        )
        self.db.add(record)
        return record

    @staticmethod
    def _normalize_title(title: str) -> str:
        """标题标准化（去除平台特有格式）"""
        import re
        # 去除常见平台标记
        t = re.sub(r"[【】#]", "", title)
        # 去除emoji和特殊字符
        t = re.sub(r"[\U00010000-\U0010ffff]", "", t)
        # 去除首尾空白
        t = t.strip()
        # 统一多个空格
        t = re.sub(r"\s+", " ", t)
        return t
