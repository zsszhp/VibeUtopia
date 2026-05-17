"""报告生成引擎 - 4类报告生成

风控报告 / 仿真报告 / 趋势报告 / 决策报告
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


@dataclass
class Report:
    """报告"""
    report_id: str = field(default_factory=lambda: f"rpt_{uuid.uuid4().hex[:8]}")
    report_type: str = ""           # risk / simulation / trend / decision
    title: str = ""
    content: str = ""               # Markdown格式报告
    summary: str = ""
    metadata: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReportGenerator:
    """报告生成引擎"""

    async def generate_risk_report(
        self, task_id: str, analysis_data: Dict
    ) -> Report:
        """生成风控报告"""
        prompt = f"""基于以下风控分析数据，生成专业的风控评估报告。

分析数据:
- 总风险分: {analysis_data.get('overall_score', 0)}/100
- 风险维度: {json.dumps(analysis_data.get('dimensions', {}), ensure_ascii=False)}
- 风险句子: {json.dumps(analysis_data.get('risk_sentences', [])[:5], ensure_ascii=False)}
- 平台反应: {json.dumps(analysis_data.get('platform_reactions', {}), ensure_ascii=False)}
- 热点关联: {json.dumps(analysis_data.get('signal_matches', []), ensure_ascii=False)}
- 实体风险链: {json.dumps(analysis_data.get('entity_chains', []), ensure_ascii=False)}

生成Markdown格式报告，包含：
1. 概述（风险等级和核心发现）
2. 七维风险分析
3. 平台情绪预测
4. 热点关联风险
5. 改写建议
6. 可信度标注"""

        return await self._generate("risk", "风控评估报告", prompt, analysis_data)

    async def generate_simulation_report(
        self, simulation_data: Dict
    ) -> Report:
        """生成仿真报告"""
        prompt = f"""基于以下仿真数据，生成仿真分析报告。

仿真数据:
- Agent数量: {simulation_data.get('total_agents', 0)}
- 传播阶段: {simulation_data.get('propagation', {})}
- 平台状态: {json.dumps(simulation_data.get('platforms', {}), ensure_ascii=False)[:500]}
- 监控数据: {json.dumps(simulation_data.get('monitor', {}), ensure_ascii=False)}

生成Markdown格式报告，包含：
1. 仿真概况
2. 传播路径分析
3. 各平台反应汇总
4. 关键Agent洞察
5. 传播动力学分析"""

        return await self._generate("simulation", "仿真分析报告", prompt, simulation_data)

    async def generate_trend_report(
        self, prediction_data: Dict
    ) -> Report:
        """生成趋势报告"""
        prompt = f"""基于以下趋势预测数据，生成趋势分析报告。

预测数据:
{json.dumps(prediction_data, ensure_ascii=False)[:2000]}

生成Markdown格式报告，包含：
1. 态势感知摘要
2. 舆论模式分析
3. 短期/中期/长期走势预测
4. 关键转折点
5. 不确定性分析
6. 建议措施"""

        return await self._generate("trend", "趋势预测报告", prompt, prediction_data)

    async def generate_decision_report(
        self, decision_data: Dict
    ) -> Report:
        """生成决策报告"""
        prompt = f"""基于以下决策数据，生成决策辅助报告。

决策数据:
{json.dumps(decision_data, ensure_ascii=False)[:2000]}

生成Markdown格式报告，包含：
1. 风险判定
2. 行动建议
3. 反事实仿真对比
4. 最优策略推荐
5. 风险缓解措施"""

        return await self._generate("decision", "决策辅助报告", prompt, decision_data)

    async def _generate(
        self, report_type: str, title: str, prompt: str, metadata: Dict
    ) -> Report:
        """通用报告生成"""
        try:
            response = await call_llm(
                prompt,
                system="你是一个专业的舆情风险报告撰写专家，擅长生成结构清晰、数据支撑的报告。",
                task_type="persona_simulation",
            )

            # 提取摘要
            summary = response[:200] + "..." if len(response) > 200 else response

            return Report(
                report_type=report_type,
                title=title,
                content=response,
                summary=summary,
                metadata={"source_data_keys": list(metadata.keys())},
            )

        except Exception as e:
            logger.error("报告生成失败: %s", e)
            return Report(
                report_type=report_type,
                title=title,
                content=f"报告生成失败: {e}",
                summary="生成失败",
                metadata=metadata,
            )
