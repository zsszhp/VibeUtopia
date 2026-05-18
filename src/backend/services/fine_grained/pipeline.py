from __future__ import annotations

"""细粒度视频理解管线 - V3.4

整合密集帧扫描、区域放大、专项检测器，输出细粒度风险补充报告。
与现有多模态风控管线并行运行，补充"几帧定生死"的检测盲区。
"""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Optional

from backend.services.fine_grained.dense_frame_scanner import DenseFrameScanner, DenseScanResult
from backend.services.fine_grained.region_amplifier import RegionAmplifier, RegionAmplifyResult
from backend.services.fine_grained.map_auditor import MapCompletenessAuditor, VideoMapAuditResult
from backend.services.fine_grained.code_tracer import CodeOriginTracer, VideoCodeTraceResult
from backend.services.fine_grained.symbol_detector import SensitiveSymbolDetector, VideoSymbolResult
from backend.services.fine_grained.temporal_anomaly import TemporalAnomalyDetector, TemporalAnomalyResult

logger = logging.getLogger(__name__)


@dataclass
class FineGrainedRiskReport:
    """细粒度风险补充报告"""
    video_path: str = ""
    dense_scan: Optional[DenseScanResult] = None
    map_audit: Optional[VideoMapAuditResult] = None
    code_trace: Optional[VideoCodeTraceResult] = None
    symbol_detect: Optional[VideoSymbolResult] = None
    temporal_anomaly: Optional[TemporalAnomalyResult] = None
    has_fine_grained_risk: bool = False
    risk_upgrade: int = 0
    max_risk_level: str = "safe"
    key_findings: list = field(default_factory=list)
    evidence_frames: list = field(default_factory=list)
    error: Optional[str] = None


DEFAULT_PIPELINE_CONFIG = {
    "enable_dense_scan": True,
    "enable_map_audit": True,
    "enable_code_trace": True,
    "enable_symbol_detect": True,
    "enable_temporal_anomaly": True,
    "dense_fps": 1.0,
    "anomaly_threshold_high": 0.7,
    "max_analysis_frames": 50,
}


class FineGrainedPipeline:
    """细粒度视频理解管线——补齐"几帧定生死"的检测盲区"""

    def __init__(self, config: dict | None = None):
        self.config = {**DEFAULT_PIPELINE_CONFIG, **(config or {})}

        self.scanner = DenseFrameScanner({
            "dense_fps": self.config["dense_fps"],
            "anomaly_threshold_high": self.config["anomaly_threshold_high"],
        })
        self.amplifier = RegionAmplifier()
        self.map_auditor = MapCompletenessAuditor()
        self.code_tracer = CodeOriginTracer({
            "github_token": self.config.get("github_token", ""),
        })
        self.symbol_detector = SensitiveSymbolDetector()
        self.temporal_detector = TemporalAnomalyDetector()

    async def analyze(self, video_path: str, output_dir: str | None = None) -> FineGrainedRiskReport:
        """细粒度视频理解主入口

        Args:
            video_path: 本地视频文件路径
            output_dir: 中间结果输出目录

        Returns:
            FineGrainedRiskReport
        """
        if not os.path.exists(video_path):
            return FineGrainedRiskReport(
                video_path=video_path,
                error=f"视频文件不存在: {video_path}",
            )

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="vibe_fine_grained_")
        os.makedirs(output_dir, exist_ok=True)

        report = FineGrainedRiskReport(video_path=video_path)
        key_findings = []
        evidence_frames = []
        risk_upgrade = 0
        risk_order = {"safe": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        max_risk_level = "safe"

        # Step 1: 密集帧扫描
        if self.config["enable_dense_scan"]:
            logger.info("Step 1: 密集帧扫描...")
            scan_result = await self.scanner.scan(video_path, output_dir)
            report.dense_scan = scan_result

            if scan_result.error:
                logger.warning("密集帧扫描失败: %s", scan_result.error)
            else:
                logger.info(
                    "密集帧扫描完成: 全量=%d, 高异常=%d, 低异常(抽审)=%d",
                    scan_result.total_dense_frames,
                    len(scan_result.high_anomaly_frames),
                    len(scan_result.low_anomaly_frames),
                )

        # 收集需要细审的帧
        analysis_frames = []
        if report.dense_scan and not report.dense_scan.error:
            analysis_frames = (
                report.dense_scan.high_anomaly_frames +
                report.dense_scan.low_anomaly_frames
            )

            max_frames = self.config["max_analysis_frames"]
            if len(analysis_frames) > max_frames:
                analysis_frames = sorted(analysis_frames, key=lambda f: f.anomaly_score, reverse=True)
                analysis_frames = analysis_frames[:max_frames]

        if not analysis_frames:
            logger.info("无需要细审的帧，跳过专项检测")
            return report

        # Step 2: 区域放大分析
        logger.info("Step 2: 区域放大分析 (%d帧)...", len(analysis_frames))
        region_results = []
        for frame in analysis_frames:
            try:
                result = await self.amplifier.analyze_frame(frame.image_path, frame.timestamp)
                region_results.append(result)
            except Exception as e:
                logger.debug("区域放大分析失败 (t=%.2f): %s", frame.timestamp, e)

        # Step 3: 专项检测器
        frame_paths = [f.image_path for f in analysis_frames]
        timestamps = [f.timestamp for f in analysis_frames]

        # 3a. 地图完整性审核
        if self.config["enable_map_audit"]:
            logger.info("Step 3a: 地图完整性审核...")
            try:
                map_result = await self.map_auditor.audit_video_frames(frame_paths, timestamps)
                report.map_audit = map_result

                if map_result.has_map_risk:
                    key_findings.append(f"地图审核发现风险: 缺失区域={map_result.audit_results}")
                    risk_upgrade += 30
                    if risk_order.get(map_result.max_risk_level, 0) > risk_order.get(max_risk_level, 0):
                        max_risk_level = map_result.max_risk_level

                    for r in map_result.audit_results:
                        if r.is_map and r.missing_regions:
                            evidence_frames.append(r.frame_path)

            except Exception as e:
                logger.warning("地图审核失败: %s", e)

        # 3b. 代码溯源检测
        if self.config["enable_code_trace"]:
            logger.info("Step 3b: 代码溯源检测...")
            code_frame_paths = []
            code_timestamps = []

            for rr in region_results:
                for region in rr.regions:
                    if region.region_type == "code_terminal":
                        code_frame_paths.append(rr.frame_path)
                        code_timestamps.append(rr.timestamp)
                        break

            if code_frame_paths:
                try:
                    code_result = await self.code_tracer.trace_video_frames(
                        code_frame_paths, code_timestamps
                    )
                    report.code_trace = code_result

                    if code_result.has_opensource_risk:
                        key_findings.append(f"代码溯源发现风险: 可能使用开源项目")
                        risk_upgrade += 20
                        if risk_order.get(code_result.max_risk_level, 0) > risk_order.get(max_risk_level, 0):
                            max_risk_level = code_result.max_risk_level

                        for r in code_result.trace_results:
                            if r.is_likely_opensource:
                                evidence_frames.append(r.frame_path)

                except Exception as e:
                    logger.warning("代码溯源失败: %s", e)

        # 3c. 敏感符号检测
        if self.config["enable_symbol_detect"]:
            logger.info("Step 3c: 敏感符号检测...")
            try:
                symbol_result = await self.symbol_detector.detect_video_frames(
                    frame_paths, timestamps
                )
                report.symbol_detect = symbol_result

                if symbol_result.has_symbol_risk:
                    key_findings.append("敏感符号检测发现风险")
                    risk_upgrade += 15
                    if risk_order.get(symbol_result.max_risk_level, 0) > risk_order.get(max_risk_level, 0):
                        max_risk_level = symbol_result.max_risk_level

                    for r in symbol_result.symbol_results:
                        if r.has_sensitive_symbol:
                            evidence_frames.append(r.frame_path)

            except Exception as e:
                logger.warning("敏感符号检测失败: %s", e)

        # 3d. 时序异常检测
        if self.config["enable_temporal_anomaly"] and report.dense_scan and not report.dense_scan.error:
            logger.info("Step 3d: 时序异常检测...")
            try:
                anomaly_result = await self.temporal_detector.detect_from_scan(report.dense_scan)
                report.temporal_anomaly = anomaly_result

                if anomaly_result.has_anomaly:
                    key_findings.append(f"时序异常检测发现{len(anomaly_result.anomalies)}处异常画面")
                    risk_upgrade += 10
                    if risk_order.get(anomaly_result.max_risk_level, 0) > risk_order.get(max_risk_level, 0):
                        max_risk_level = anomaly_result.max_risk_level

                    for a in anomaly_result.anomalies:
                        if a.frame_path:
                            evidence_frames.append(a.frame_path)

            except Exception as e:
                logger.warning("时序异常检测失败: %s", e)

        # Step 4: 结果融合
        report.has_fine_grained_risk = risk_upgrade > 0
        report.risk_upgrade = min(risk_upgrade, 100)
        report.max_risk_level = max_risk_level
        report.key_findings = key_findings
        report.evidence_frames = list(set(evidence_frames))

        logger.info(
            "细粒度分析完成: has_risk=%s, risk_upgrade=%d, max_level=%s, findings=%d",
            report.has_fine_grained_risk,
            report.risk_upgrade,
            report.max_risk_level,
            len(key_findings),
        )

        return report

    def get_status(self) -> dict:
        """获取管线可用状态"""
        return {
            "available": True,
            "modules": {
                "dense_scan": self.scanner.get_scan_status(),
                "region_amplifier": self.amplifier.get_status(),
                "map_auditor": self.map_auditor.get_status(),
                "code_tracer": self.code_tracer.get_status(),
                "symbol_detector": self.symbol_detector.get_status(),
                "temporal_anomaly": self.temporal_detector.get_status(),
            },
            "config": {
                "enable_dense_scan": self.config["enable_dense_scan"],
                "enable_map_audit": self.config["enable_map_audit"],
                "enable_code_trace": self.config["enable_code_trace"],
                "enable_symbol_detect": self.config["enable_symbol_detect"],
                "enable_temporal_anomaly": self.config["enable_temporal_anomaly"],
            },
        }
