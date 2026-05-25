import asyncio
import logging
from typing import Any, Callable

from backend.services.exceptions import AnalysisError, NetworkError, ServiceUnavailableError
from backend.services.error_monitor import error_monitor

logger = logging.getLogger(__name__)

DEFAULT_RECOVERABLE_ERRORS: tuple[type[Exception], ...] = (NetworkError, ServiceUnavailableError)


async def safe_execute(
    step_name: str,
    task_id: str,
    func: Callable[..., Any],
    *args: Any,
    fallback_value: Any = None,
    max_retries: int = 2,
    recoverable_errors: tuple[type[Exception], ...] = DEFAULT_RECOVERABLE_ERRORS,
    **kwargs: Any,
) -> Any:
    retry_count = 0

    while retry_count <= max_retries:
        try:
            return await func(*args, **kwargs)
        except AnalysisError as e:
            error_monitor.record_error(e, task_id, step_name)

            error_context = {
                "task_id": task_id,
                "step": step_name,
                "error_code": e.error_code,
                "severity": e.severity,
                "retry_count": retry_count,
                "timestamp": e.timestamp,
                **e.context,
            }

            if isinstance(e, recoverable_errors) and retry_count < max_retries:
                retry_count += 1
                logger.warning(
                    "步骤 %s 可恢复错误，第 %d 次重试: %s | 上下文: %s",
                    step_name, retry_count, str(e), error_context,
                )
                await asyncio.sleep(1 * retry_count)
                continue

            if e.severity in ("high", "critical"):
                logger.error(
                    "步骤 %s 严重错误: %s | 上下文: %s",
                    step_name, str(e), error_context, exc_info=True,
                )
            else:
                logger.warning(
                    "步骤 %s 降级执行: %s | 上下文: %s",
                    step_name, str(e), error_context,
                )
            return fallback_value

        except Exception as e:
            error_monitor.record_unexpected(e, task_id, step_name)
            logger.error(
                "步骤 %s 未预期异常: %s | 任务ID: %s",
                step_name, str(e), task_id, exc_info=True,
            )
            return fallback_value

    return fallback_value
