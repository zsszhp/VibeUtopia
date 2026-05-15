"""Prompt版本管理器 — T2.2

支持Prompt文件的版本控制、A/B测试和效果对比。
每个Prompt可以有多个版本，通过A/B测试验证哪个版本效果更好。
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Prompt文件目录
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class PromptVersion:
    """Prompt版本"""

    def __init__(
        self,
        prompt_name: str,
        version: str,
        content: str,
        created_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.prompt_name = prompt_name
        self.version = version
        self.content = content
        self.created_at = created_at or datetime.now(timezone.utc)
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_name": self.prompt_name,
            "version": self.version,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptVersion":
        return cls(
            prompt_name=data["prompt_name"],
            version=data["version"],
            content=data["content"],
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data.get("created_at"),
            metadata=data.get("metadata", {}),
        )


class PromptABTestResult:
    """A/B测试结果"""

    def __init__(
        self,
        prompt_name: str,
        version_a: str,
        version_b: str,
        metrics_a: Dict[str, float],
        metrics_b: Dict[str, float],
        sample_size: int = 0,
    ):
        self.prompt_name = prompt_name
        self.version_a = version_a
        self.version_b = version_b
        self.metrics_a = metrics_a
        self.metrics_b = metrics_b
        self.sample_size = sample_size
        self.winner = self._determine_winner()
        self.created_at = datetime.now(timezone.utc)

    def _determine_winner(self) -> str:
        """根据综合得分判断胜出版本"""
        score_a = sum(self.metrics_a.values()) / len(self.metrics_a) if self.metrics_a else 0
        score_b = sum(self.metrics_b.values()) / len(self.metrics_b) if self.metrics_b else 0
        if score_a > score_b:
            return self.version_a
        elif score_b > score_a:
            return self.version_b
        return "tie"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_name": self.prompt_name,
            "version_a": self.version_a,
            "version_b": self.version_b,
            "metrics_a": self.metrics_a,
            "metrics_b": self.metrics_b,
            "sample_size": self.sample_size,
            "winner": self.winner,
            "created_at": self.created_at.isoformat(),
        }


class PromptVersionManager:
    """Prompt版本管理器

    职责:
    1. 管理Prompt文件的多版本
    2. 支持A/B测试配置
    3. 记录测试结果
    4. 推荐最佳版本
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir = self.prompts_dir / "versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.ab_tests_dir = self.prompts_dir / "ab_tests"
        self.ab_tests_dir.mkdir(parents=True, exist_ok=True)
        self._load_versions()
        self._load_ab_tests()

    def _load_versions(self):
        """加载已有版本"""
        self.versions: Dict[str, Dict[str, PromptVersion]] = {}
        if not self.versions_dir.exists():
            return
        for prompt_dir in self.versions_dir.iterdir():
            if prompt_dir.is_dir():
                prompt_name = prompt_dir.name
                self.versions[prompt_name] = {}
                for version_file in prompt_dir.glob("*.json"):
                    with open(version_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        version = PromptVersion.from_dict(data)
                        self.versions[prompt_name][version.version] = version

    def _load_ab_tests(self):
        """加载已有A/B测试"""
        self.ab_tests: List[Dict[str, Any]] = []
        if not self.ab_tests_dir.exists():
            return
        for test_file in self.ab_tests_dir.glob("*.json"):
            with open(test_file, "r", encoding="utf-8") as f:
                self.ab_tests.append(json.load(f))

    def register_version(
        self,
        prompt_name: str,
        version: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptVersion:
        """注册新Prompt版本

        Args:
            prompt_name: Prompt名称 (不含.txt后缀)
            version: 版本号 (如 v1.0, v2.0, experimental)
            content: Prompt内容
            metadata: 元数据 (描述、修改说明等)

        Returns:
            注册的版本对象
        """
        pv = PromptVersion(
            prompt_name=prompt_name,
            version=version,
            content=content,
            metadata=metadata,
        )

        if prompt_name not in self.versions:
            self.versions[prompt_name] = {}

        self.versions[prompt_name][version] = pv

        # 持久化到文件
        prompt_dir = self.versions_dir / prompt_name
        prompt_dir.mkdir(parents=True, exist_ok=True)
        version_file = prompt_dir / f"{version}.json"
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(pv.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info("注册Prompt版本: %s %s", prompt_name, version)
        return pv

    def get_version(self, prompt_name: str, version: str) -> Optional[PromptVersion]:
        """获取指定版本"""
        if prompt_name in self.versions and version in self.versions[prompt_name]:
            return self.versions[prompt_name][version]
        return None

    def get_latest_version(self, prompt_name: str) -> Optional[PromptVersion]:
        """获取最新版本"""
        if prompt_name not in self.versions:
            return None
        versions = list(self.versions[prompt_name].values())
        return max(versions, key=lambda v: v.created_at)

    def get_all_versions(self, prompt_name: str) -> List[PromptVersion]:
        """获取所有版本"""
        if prompt_name not in self.versions:
            return []
        return sorted(
            self.versions[prompt_name].values(),
            key=lambda v: v.created_at,
        )

    def list_prompts(self) -> List[str]:
        """列出所有有版本的Prompt名称"""
        return list(self.versions.keys())

    def delete_version(self, prompt_name: str, version: str) -> bool:
        """删除指定版本"""
        if prompt_name not in self.versions or version not in self.versions[prompt_name]:
            return False

        # 删除文件
        version_file = self.versions_dir / prompt_name / f"{version}.json"
        if version_file.exists():
            version_file.unlink()

        del self.versions[prompt_name][version]
        if not self.versions[prompt_name]:
            del self.versions[prompt_name]

        logger.info("删除Prompt版本: %s %s", prompt_name, version)
        return True

    def create_ab_test(
        self,
        prompt_name: str,
        version_a: str,
        version_b: str,
        test_name: str = "",
    ) -> Dict[str, Any]:
        """创建A/B测试

        Args:
            prompt_name: Prompt名称
            version_a: 版本A
            version_b: 版本B
            test_name: 测试名称

        Returns:
            测试配置
        """
        if prompt_name not in self.versions:
            raise ValueError(f"Prompt '{prompt_name}' 无可用版本")
        if version_a not in self.versions[prompt_name]:
            raise ValueError(f"版本 '{version_a}' 不存在")
        if version_b not in self.versions[prompt_name]:
            raise ValueError(f"版本 '{version_b}' 不存在")

        test_id = f"{prompt_name}_{version_a}_vs_{version_b}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        test_config = {
            "test_id": test_id,
            "prompt_name": prompt_name,
            "version_a": version_a,
            "version_b": version_b,
            "test_name": test_name or f"{prompt_name}: {version_a} vs {version_b}",
            "status": "pending",
            "results_a": [],
            "results_b": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        test_file = self.ab_tests_dir / f"{test_id}.json"
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_config, f, ensure_ascii=False, indent=2)

        self.ab_tests.append(test_config)
        logger.info("创建A/B测试: %s", test_name)
        return test_config

    def record_ab_test_result(
        self,
        test_id: str,
        version: str,
        metrics: Dict[str, float],
    ) -> Optional[Dict[str, Any]]:
        """记录A/B测试结果

        Args:
            test_id: 测试ID
            version: 版本 (a 或 b)
            metrics: 评估指标

        Returns:
            更新后的测试配置
        """
        test_config = None
        for test in self.ab_tests:
            if test["test_id"] == test_id:
                test_config = test
                break

        if not test_config:
            logger.warning("A/B测试 %s 不存在", test_id)
            return None

        result_key = f"results_{version}"
        if result_key not in test_config:
            test_config[result_key] = []

        test_config[result_key].append({
            "metrics": metrics,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        test_config["status"] = "running"

        # 持久化
        test_file = self.ab_tests_dir / f"{test_id}.json"
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_config, f, ensure_ascii=False, indent=2)

        return test_config

    def conclude_ab_test(self, test_id: str) -> Optional[PromptABTestResult]:
        """完成A/B测试并得出结论

        Args:
            test_id: 测试ID

        Returns:
            A/B测试结果
        """
        test_config = None
        for test in self.ab_tests:
            if test["test_id"] == test_id:
                test_config = test
                break

        if not test_config:
            return None

        # 计算平均指标
        metrics_a = self._average_metrics(test_config.get("results_a", []))
        metrics_b = self._average_metrics(test_config.get("results_b", []))

        result = PromptABTestResult(
            prompt_name=test_config["prompt_name"],
            version_a=test_config["version_a"],
            version_b=test_config["version_b"],
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            sample_size=len(test_config.get("results_a", [])) + len(test_config.get("results_b", [])),
        )

        test_config["status"] = "completed"
        test_config["winner"] = result.winner
        test_config["metrics_a_avg"] = metrics_a
        test_config["metrics_b_avg"] = metrics_b
        test_config["concluded_at"] = datetime.now(timezone.utc).isoformat()

        # 持久化
        test_file = self.ab_tests_dir / f"{test_id}.json"
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_config, f, ensure_ascii=False, indent=2)

        logger.info("A/B测试完成: %s, 胜出版本: %s", test_id, result.winner)
        return result

    def _average_metrics(self, results: List[Dict]) -> Dict[str, float]:
        """计算多轮测试的平均指标"""
        if not results:
            return {}
        all_metrics = [r.get("metrics", {}) for r in results]
        keys = set()
        for m in all_metrics:
            keys.update(m.keys())
        avg = {}
        for key in keys:
            values = [m.get(key, 0) for m in all_metrics if key in m]
            avg[key] = round(sum(values) / len(values), 4) if values else 0
        return avg

    def get_recommended_version(self, prompt_name: str) -> Optional[str]:
        """根据A/B测试结果推荐最佳版本

        Returns:
            推荐版本号，如无数据则返回None
        """
        if prompt_name not in self.versions:
            return None

        # 查找已完成的A/B测试
        completed_tests = [
            t for t in self.ab_tests
            if t["prompt_name"] == prompt_name and t.get("status") == "completed"
        ]

        if not completed_tests:
            # 无A/B测试数据，返回最新版本
            latest = self.get_latest_version(prompt_name)
            return latest.version if latest else None

        # 统计各版本胜出次数
        win_counts = {}
        for test in completed_tests:
            winner = test.get("winner")
            if winner:
                win_counts[winner] = win_counts.get(winner, 0) + 1

        if not win_counts:
            latest = self.get_latest_version(prompt_name)
            return latest.version if latest else None

        # 返回胜出次数最多的版本
        return max(win_counts, key=win_counts.get)

    def get_ab_test_history(self, prompt_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取A/B测试历史"""
        if prompt_name:
            return [t for t in self.ab_tests if t["prompt_name"] == prompt_name]
        return self.ab_tests

    def import_from_file(self, prompt_name: str, file_path: str, version: str) -> PromptVersion:
        """从现有文件导入Prompt版本"""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.register_version(prompt_name, version, content)

    def export_to_file(self, prompt_name: str, version: str, output_path: str) -> bool:
        """导出Prompt版本到文件"""
        pv = self.get_version(prompt_name, version)
        if not pv:
            return False
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(pv.content)
        return True

    def get_version_summary(self, prompt_name: str) -> List[Dict[str, Any]]:
        """获取版本摘要"""
        versions = self.get_all_versions(prompt_name)
        return [
            {
                "version": v.version,
                "created_at": v.created_at.isoformat(),
                "metadata": v.metadata,
                "content_length": len(v.content),
            }
            for v in versions
        ]

    def get_active_ab_test(self, prompt_name: str) -> Optional[Dict[str, Any]]:
        """获取进行中的A/B测试"""
        for test in self.ab_tests:
            if test["prompt_name"] == prompt_name and test.get("status") == "running":
                return test
        return None
