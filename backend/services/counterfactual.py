"""反事实仿真引擎 - "如果换一种做法会怎样？"

从指定仿真创建分支，注入干预（修改文案/删除评论/发布声明等），
运行分支仿真，对比原始仿真与分支差异。
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Intervention:
    """干预措施"""
    intervention_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    tick: int = 0                     # 在哪个tick注入
    intervention_type: str = ""       # modify_text / delete_comment / publish_statement / inject_event
    content: str = ""                 # 干预内容
    platform: str = "weibo"           # 干预平台
    as_role: str = "system"           # 干预角色


@dataclass
class BranchResult:
    """分支仿真结果"""
    branch_id: str = ""
    intervention: Optional[Intervention] = None
    overall_score: int = 0
    platform_reactions: Dict = field(default_factory=dict)
    propagation: Dict = field(default_factory=dict)
    key_differences: List[str] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """对比结果"""
    original_id: str = ""
    branch_results: List[BranchResult] = field(default_factory=list)
    score_improvement: Dict[str, int] = field(default_factory=dict)  # branch_id -> improvement
    best_branch: str = ""
    summary: str = ""


class CounterfactualEngine:
    """反事实仿真引擎"""

    async def create_branch(
        self, sim_id: str, intervention: Intervention
    ) -> str:
        """从指定仿真创建分支，注入干预

        Args:
            sim_id: 原始仿真ID
            intervention: 干预措施

        Returns:
            branch_id: 分支仿真ID
        """
        branch_id = f"branch_{sim_id}_{intervention.intervention_id}"

        try:
            from backend.services.simulation.engine import SimulationEngine

            # 获取原始仿真状态
            engine = await self._get_simulation_engine(sim_id)
            if not engine:
                logger.error("反事实: 仿真 %s 不存在", sim_id)
                return ""

            # 创建分支仿真
            branch_engine = SimulationEngine.create_lightweight(
                sim_id=branch_id,
                topic=engine.topic,
                seed_content=self._apply_intervention(engine.topic, intervention),
            )
            await branch_engine.initialize()

            # 注入干预
            await self._inject_intervention(branch_engine, intervention)

            # 运行分支仿真
            await branch_engine.run()

            # 存储分支引擎
            self._store_branch(branch_id, branch_engine)

            logger.info("反事实分支 %s 创建并运行完成", branch_id)
            return branch_id

        except Exception as e:
            logger.error("反事实分支创建失败: %s", e)
            return ""

    async def compare_branches(
        self, original_id: str, branch_ids: List[str]
    ) -> ComparisonResult:
        """对比原始仿真与各分支的差异"""
        result = ComparisonResult(original_id=original_id)

        # 获取原始仿真数据
        original_status = await self._get_simulation_status(original_id)
        original_score = self._estimate_risk_score(original_status)

        best_improvement = -999
        for bid in branch_ids:
            branch_status = await self._get_simulation_status(bid)
            branch_score = self._estimate_risk_score(branch_status)

            improvement = original_score - branch_score
            result.score_improvement[bid] = improvement

            # 识别关键差异
            differences = self._identify_differences(original_status, branch_status)

            result.branch_results.append(BranchResult(
                branch_id=bid,
                overall_score=branch_score,
                platform_reactions=branch_status.get("platforms", {}),
                propagation=branch_status.get("propagation", {}),
                key_differences=differences,
            ))

            if improvement > best_improvement:
                best_improvement = improvement
                result.best_branch = bid

        result.summary = self._generate_comparison_summary(result, original_score)
        return result

    def _apply_intervention(self, original_topic: str, intervention: Intervention) -> str:
        """应用干预生成新种子内容"""
        if intervention.intervention_type == "modify_text":
            return intervention.content
        elif intervention.intervention_type == "publish_statement":
            return f"[官方声明] {intervention.content}\n\n原始话题: {original_topic}"
        else:
            return original_topic

    async def _inject_intervention(self, engine, intervention: Intervention):
        """向仿真引擎注入干预"""
        platform = engine.platforms.get(intervention.platform)
        if platform:
            if intervention.intervention_type == "inject_event":
                platform.seed_topic(intervention.content, author_id=f"injector_{intervention.as_role}")
            elif intervention.intervention_type == "publish_statement":
                platform.seed_topic(
                    f"[官方声明] {intervention.content}",
                    author_id="official_statement",
                )

    async def _get_simulation_engine(self, sim_id: str):
        """获取仿真引擎实例"""
        # 尝试从活跃仿真中获取
        from backend.routes import _active_simulations if '_' in '' else {}
        return None  # 简化：实际从数据库重建

    async def _get_simulation_status(self, sim_id: str) -> Dict:
        """获取仿真状态"""
        from backend.database import SessionLocal
        from backend.models import SimulationStatus

        db = SessionLocal()
        try:
            status = db.query(SimulationStatus).filter(
                SimulationStatus.sim_id == sim_id
            ).first()
            if status:
                return {
                    "sim_id": status.sim_id,
                    "status": status.status,
                    "total_agents": status.total_agents,
                    "config": json.loads(status.config_json) if status.config_json else {},
                    "platforms": json.loads(status.platform_snapshot_json) if status.platform_snapshot_json else {},
                }
        finally:
            db.close()
        return {}

    def _estimate_risk_score(self, status: Dict) -> int:
        """从仿真状态估算风险分"""
        propagation = status.get("propagation", {})
        if isinstance(propagation, dict):
            kinetic = propagation.get("kinetic", 0)
            reach = propagation.get("reach_count", 0)
            score = min(100, int(kinetic * 50 + reach * 0.5))
            return score
        return 50

    def _identify_differences(self, original: Dict, branch: Dict) -> List[str]:
        """识别两个仿真之间的关键差异"""
        differences = []

        orig_prop = original.get("propagation", {})
        branch_prop = branch.get("propagation", {})

        if isinstance(orig_prop, dict) and isinstance(branch_prop, dict):
            orig_kinetic = orig_prop.get("kinetic", 0)
            branch_kinetic = branch_prop.get("kinetic", 0)
            if abs(orig_kinetic - branch_kinetic) > 0.1:
                diff = "降低" if branch_kinetic < orig_kinetic else "升高"
                differences.append(f"传播动能{diff}: {orig_kinetic:.2f} → {branch_kinetic:.2f}")

            orig_reach = orig_prop.get("reach_count", 0)
            branch_reach = branch_prop.get("reach_count", 0)
            if abs(orig_reach - branch_reach) > 5:
                diff = "减少" if branch_reach < orig_reach else "增加"
                differences.append(f"覆盖人数{diff}: {orig_reach} → {branch_reach}")

        return differences

    def _store_branch(self, branch_id: str, engine):
        """存储分支引擎（简化：使用全局dict）"""
        # 实际实现可使用Redis或数据库
        pass

    def _generate_comparison_summary(self, result: ComparisonResult, original_score: int) -> str:
        """生成对比摘要"""
        if not result.branch_results:
            return "无分支结果"

        parts = [f"原始风险分: {original_score}"]
        for br in result.branch_results:
            improvement = result.score_improvement.get(br.branch_id, 0)
            parts.append(f"分支 {br.branch_id}: 风险分 {br.overall_score} (改善 {improvement:+d})")

        if result.best_branch:
            best_imp = result.score_improvement.get(result.best_branch, 0)
            parts.append(f"最优分支: {result.best_branch} (改善 {best_imp:+d})")

        return " | ".join(parts)
