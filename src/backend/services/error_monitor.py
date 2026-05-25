import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_ALERT_THRESHOLD = 10
_WINDOW_SECONDS = 300


@dataclass
class ErrorRecord:
    error_code: str
    severity: str
    timestamp: float
    task_id: str
    step: str
    context: dict = field(default_factory=dict)


class ErrorMonitor:
    def __init__(self, window_seconds: int = _WINDOW_SECONDS, alert_threshold: int = _ALERT_THRESHOLD):
        self.window_seconds = window_seconds
        self.alert_threshold = alert_threshold
        self.errors: list[ErrorRecord] = []
        self.error_counts: dict[str, int] = defaultdict(int)

    def record_error(self, error, task_id: str, step: str):
        from backend.services.exceptions import AnalysisError
        if isinstance(error, AnalysisError):
            record = ErrorRecord(
                error_code=error.error_code,
                severity=error.severity,
                timestamp=time.time(),
                task_id=task_id,
                step=step,
                context=error.context,
            )
        else:
            record = ErrorRecord(
                error_code="UNEXPECTED",
                severity="high",
                timestamp=time.time(),
                task_id=task_id,
                step=step,
            )
        self.errors.append(record)
        self.error_counts[record.error_code] += 1
        self._cleanup_old_records()
        self._check_alerts(record.error_code)

    def record_unexpected(self, error: Exception, task_id: str, step: str):
        record = ErrorRecord(
            error_code="UNEXPECTED",
            severity="high",
            timestamp=time.time(),
            task_id=task_id,
            step=step,
            context={"message": str(error)},
        )
        self.errors.append(record)
        self.error_counts["UNEXPECTED"] += 1
        self._cleanup_old_records()
        self._check_alerts("UNEXPECTED")

    def _cleanup_old_records(self):
        cutoff = time.time() - self.window_seconds
        self.errors = [e for e in self.errors if e.timestamp > cutoff]

    def _check_alerts(self, error_code: str):
        recent = [e for e in self.errors if e.error_code == error_code]
        if len(recent) > self.alert_threshold:
            logger.error(
                "错误告警: %s 在过去 %d 秒内发生 %d 次",
                error_code, self.window_seconds, len(recent),
            )

    def get_error_summary(self) -> dict:
        return {
            "total_errors": len(self.errors),
            "error_counts": dict(self.error_counts),
            "window_seconds": self.window_seconds,
        }


error_monitor = ErrorMonitor()
