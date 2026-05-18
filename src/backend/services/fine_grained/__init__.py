"""V3.4 细粒度视频理解模块

解决视频中短暂画面（十几帧）和小区域细节的检测与理解问题。
"""

from backend.services.fine_grained.dense_frame_scanner import DenseFrameScanner, DenseFrame, DenseScanResult
from backend.services.fine_grained.region_amplifier import RegionAmplifier, RegionOfInterest, RegionDetail, RegionAmplifyResult
from backend.services.fine_grained.map_auditor import MapCompletenessAuditor, MapAuditResult, VideoMapAuditResult
from backend.services.fine_grained.code_tracer import CodeOriginTracer, CodeTraceResult, VideoCodeTraceResult
from backend.services.fine_grained.symbol_detector import SensitiveSymbolDetector, SymbolRiskResult, VideoSymbolResult
from backend.services.fine_grained.temporal_anomaly import TemporalAnomalyDetector, TemporalAnomaly, TemporalAnomalyResult
from backend.services.fine_grained.pipeline import FineGrainedPipeline, FineGrainedRiskReport

__all__ = [
    "DenseFrameScanner", "DenseFrame", "DenseScanResult",
    "RegionAmplifier", "RegionOfInterest", "RegionDetail", "RegionAmplifyResult",
    "MapCompletenessAuditor", "MapAuditResult", "VideoMapAuditResult",
    "CodeOriginTracer", "CodeTraceResult", "VideoCodeTraceResult",
    "SensitiveSymbolDetector", "SymbolRiskResult", "VideoSymbolResult",
    "TemporalAnomalyDetector", "TemporalAnomaly", "TemporalAnomalyResult",
    "FineGrainedPipeline", "FineGrainedRiskReport",
]
