from datetime import datetime, timezone


class AnalysisError(Exception):
    def __init__(self, message: str, error_code: str, severity: str = "medium",
                 context: dict | None = None, recoverable: bool = True):
        super().__init__(message)
        self.error_code = error_code
        self.severity = severity
        self.context = context or {}
        self.recoverable = recoverable
        self.timestamp = datetime.now(timezone.utc).isoformat()


class NetworkError(AnalysisError):
    def __init__(self, message: str, context: dict | None = None):
        super().__init__(message, "NETWORK_ERROR", "medium", context, recoverable=True)


class DataError(AnalysisError):
    def __init__(self, message: str, context: dict | None = None):
        super().__init__(message, "DATA_ERROR", "high", context, recoverable=False)


class ServiceUnavailableError(AnalysisError):
    def __init__(self, service_name: str, context: dict | None = None):
        super().__init__(
            f"服务 {service_name} 暂时不可用",
            "SERVICE_UNAVAILABLE", "medium", context, recoverable=True,
        )


class ConfigurationError(AnalysisError):
    def __init__(self, message: str, context: dict | None = None):
        super().__init__(message, "CONFIG_ERROR", "critical", context, recoverable=False)
