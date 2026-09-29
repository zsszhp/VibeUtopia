"""pytest 全局配置：保证 backend 包可导入，并为可选依赖提供统一跳过策略。"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def pytest_collection_modifyitems(config, items):
    """缺少可选依赖或 API Key 的用例自动 skip，保证一键 pytest 可收集、可运行。"""
    skip_chromadb = pytest.mark.skip(reason="chromadb 未安装，跳过向量检索集成测试")
    skip_api = pytest.mark.skip(reason="未配置 LONGCAT_API_KEY，跳过真实模型调用测试")
    has_chromadb = _has_module("chromadb")
    has_api_key = bool(os.getenv("LONGCAT_API_KEY", "").strip())

    for item in items:
        path = str(item.fspath)
        if "test_chromadb" in path and not has_chromadb:
            item.add_marker(skip_chromadb)
        if "test_llm_models" in path and not has_api_key:
            item.add_marker(skip_api)


@pytest.fixture(scope="session", autouse=True)
def _ensure_data_dirs():
    (ROOT / "data").mkdir(exist_ok=True)
