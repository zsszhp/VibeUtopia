"""
模块导入验证脚本
运行方式: python -m pytest services/__init___test.py -v
"""
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_checkpoint_manager_import():
    """检查点管理器可正常导入"""
    from backend.services.checkpoint_manager import CheckpointManager, AnalysisCheckpoint, StageStatus
    assert CheckpointManager is not None
    assert AnalysisCheckpoint is not None
    assert StageStatus.PENDING.value == "pending"
    print("✅ checkpoint_manager 导入成功")


def test_resumable_analyzer_import():
    """可恢复分析器可正常导入"""
    from backend.services.resumable_analyzer import ResumableAnalyzer, ANALYSIS_STAGES
    assert ResumableAnalyzer is not None
    assert len(ANALYSIS_STAGES) >= 6
    print("✅ resumable_analyzer 导入成功")


def test_routes_resume_import():
    """断点续传路由可正常导入"""
    from backend.routes_resume import router
    assert router is not None
    print("✅ routes_resume 导入成功")


def test_checkpoint_crud():
    """检查点 CRUD 操作"""
    from backend.services.checkpoint_manager import CheckpointManager, AnalysisCheckpoint
    import tempfile
    import shutil

    tmpdir = tempfile.mkdtemp()
    try:
        mgr = CheckpointManager("test_task_001", checkpoint_dir=tmpdir)

        # 创建
        cp = mgr.create(video_path="/test/video.mp4", mode="deep",
                         stage_names=["stage1", "stage2", "stage3"])
        assert cp.task_id == "test_task_001"
        assert len(cp.stages) == 3

        # 保存
        mgr.save(cp)

        # 加载
        loaded = mgr.load()
        assert loaded is not None
        assert loaded.task_id == "test_task_001"
        assert loaded.progress == 0.0

        # 完成阶段
        mgr.complete_stage(loaded, "stage1", result={"score": 50}, llm_calls=3)
        assert loaded.is_stage_completed("stage1")
        assert loaded.progress == 1/3

        # 验证视频哈希
        assert not mgr.verify_video_unchanged(loaded)  # 文件不存在

        # 删除
        mgr.delete()
        assert mgr.load() is None

        print("✅ 检查点 CRUD 操作正常")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_checkpoint_interrupted_resume():
    """模拟中断和恢复场景"""
    from backend.services.checkpoint_manager import CheckpointManager, StageStatus
    import tempfile, shutil

    tmpdir = tempfile.mkdtemp()
    try:
        mgr = CheckpointManager("test_resume_001", checkpoint_dir=tmpdir)

        # 创建并完成部分阶段
        cp = mgr.create(video_path="", mode="standard",
                         stage_names=["extract", "assess", "signal", "simulate", "report"])
        mgr.complete_stage(cp, "extract", result={"text": "hello"}, llm_calls=1)
        mgr.complete_stage(cp, "assess", result={"score": 30}, llm_calls=2)

        # 模拟中断
        mgr.mark_interrupted(cp, "API 限流 429")
        assert cp.overall_status == "interrupted"
        assert cp.quota_exhausted_count == 0  # mark_interrupted 不增加配额计数

        # 恢复
        loaded = mgr.load()
        assert loaded.is_resumable
        assert loaded.is_stage_completed("extract")
        assert loaded.is_stage_completed("assess")
        assert not loaded.is_stage_completed("signal")
        assert loaded.next_pending_stage == "signal"
        assert loaded.progress == 0.4  # 2/5

        # 继续完成
        mgr.complete_stage(loaded, "signal", result={"matches": []}, llm_calls=1)
        mgr.complete_stage(loaded, "simulate", result={}, llm_calls=3)
        mgr.complete_stage(loaded, "report", result={"final_score": 35}, llm_calls=0)
        mgr.mark_completed(loaded)

        assert loaded.overall_status == "completed"
        assert loaded.progress == 1.0
        assert loaded.total_llm_calls == 7

        print("✅ 中断恢复场景正常")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_all_imports():
    """验证所有后端模块可正常导入"""
    from backend.config import settings
    from backend.database import init_db, SessionLocal
    from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction
    from backend.services.llm_client import registry, router, call_llm, QuotaExhaustedError
    from backend.services.analyzer import run_analysis
    from backend.services.enhanced_analyzer import run_enhanced_analysis

    assert settings is not None
    assert registry is not None
    print(f"✅ 所有后端模块导入成功 (LLM端点数: {len(registry.endpoints)})")


if __name__ == "__main__":
    print("=" * 50)
    print("运行模块导入验证测试")
    print("=" * 50)

    test_checkpoint_manager_import()
    test_resumable_analyzer_import()
    test_routes_resume_import()
    test_checkpoint_crud()
    test_checkpoint_interrupted_resume()
    test_all_imports()

    print("\n" + "=" * 50)
    print("所有测试通过 ✅")
    print("=" * 50)
