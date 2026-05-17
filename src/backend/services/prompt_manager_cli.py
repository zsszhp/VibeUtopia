"""Prompt 版本管理 CLI 工具 — T2.2

提供命令行接口用于管理 Prompt 版本、运行 A/B 测试和生成报告。
"""
import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.services.prompt_version_manager import PromptVersionManager
from backend.services.prompt_ab_test_runner import PromptABTestRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_register(args):
    """注册新 Prompt 版本"""
    mgr = PromptVersionManager()
    
    # 从文件读取内容
    with open(args.file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 解析 metadata
    metadata = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            logger.error("无效的 JSON metadata")
            sys.exit(1)
    
    # 注册版本
    version = mgr.register_version(
        prompt_name=args.prompt,
        version=args.version,
        content=content,
        metadata=metadata,
    )
    
    print(f"✅ 已注册版本：{args.prompt} {args.version}")
    print(f"   创建时间：{version.created_at.isoformat()}")
    print(f"   内容长度：{len(content)} 字符")


def cmd_list(args):
    """列出所有 Prompt 版本"""
    mgr = PromptVersionManager()
    
    prompts = mgr.list_prompts()
    if not prompts:
        print("暂无 Prompt 版本记录")
        return
    
    for prompt_name in prompts:
        print(f"\n📦 {prompt_name}")
        versions = mgr.get_all_versions(prompt_name)
        for v in versions:
            metadata_info = ""
            if v.metadata and "description" in v.metadata:
                metadata_info = f" - {v.metadata['description']}"
            print(f"   • {v.version} ({v.created_at.strftime('%Y-%m-%d %H:%M')}){metadata_info}")
        
        # 显示推荐版本
        recommended = mgr.get_recommended_version(prompt_name)
        if recommended:
            print(f"   ⭐ 推荐版本：{recommended}")


def cmd_show(args):
    """显示指定版本详情"""
    mgr = PromptVersionManager()
    
    version = mgr.get_version(args.prompt, args.version)
    if not version:
        print(f"❌ 版本不存在：{args.prompt} {args.version}")
        sys.exit(1)
    
    print(f"\n📄 {args.prompt} - {args.version}")
    print(f"创建时间：{version.created_at.isoformat()}")
    print(f"内容长度：{len(version.content)} 字符")
    print(f"元数据：{json.dumps(version.metadata, ensure_ascii=False, indent=2)}")
    
    if args.show_content:
        print("\n--- 内容预览 ---")
        preview_length = 500
        print(version.content[:preview_length])
        if len(version.content) > preview_length:
            print(f"... (还有 {len(version.content) - preview_length} 字符)")


def cmd_create_ab_test(args):
    """创建 A/B 测试"""
    mgr = PromptVersionManager()
    
    test_config = mgr.create_ab_test(
        prompt_name=args.prompt,
        version_a=args.version_a,
        version_b=args.version_b,
        test_name=args.name,
    )
    
    print(f"✅ 已创建 A/B 测试")
    print(f"   测试 ID: {test_config['test_id']}")
    print(f"   版本 A: {args.version_a}")
    print(f"   版本 B: {args.version_b}")
    print(f"   状态：{test_config['status']}")


def cmd_run_ab_test(args):
    """运行 A/B 测试"""
    import asyncio
    
    runner = PromptABTestRunner(args.prompt, args.version_a, args.version_b)
    
    # 加载测试案例
    test_cases = None
    if args.cases:
        with open(args.cases, "r", encoding="utf-8") as f:
            test_cases = json.load(f)
    
    print(f"🧪 开始 A/B 测试：{args.prompt} ({args.version_a} vs {args.version_b})")
    if test_cases:
        print(f"   测试案例：{len(test_cases)} 个")
    else:
        print(f"   测试案例：使用默认案例")
    
    report = asyncio.run(runner.run_test(test_cases))
    
    print(f"\n✅ A/B 测试完成")
    print(f"   测试 ID: {report['test_id']}")
    print(f"   胜出版本：{report['winner']}")
    print(f"   样本数：{report['sample_size']}")
    
    print(f"\n📊 版本 A ({args.version_a}) 指标:")
    for metric, value in report["metrics_a"].items():
        print(f"   • {metric}: {value:.4f}")
    
    print(f"\n📊 版本 B ({args.version_b}) 指标:")
    for metric, value in report["metrics_b"].items():
        print(f"   • {metric}: {value:.4f}")
    
    # 保存报告
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n💾 报告已保存：{output_path}")


def cmd_history(args):
    """显示 A/B 测试历史"""
    mgr = PromptVersionManager()
    
    tests = mgr.get_ab_test_history(args.prompt if args.prompt else None)
    
    if not tests:
        print("暂无 A/B 测试记录")
        return
    
    print(f"\n📋 A/B 测试历史")
    print("=" * 80)
    
    for test in tests[-10:]:  # 只显示最近 10 条
        status_emoji = {"pending": "⏳", "running": "🔄", "completed": "✅", "stopped": "🛑"}
        status = test.get("status", "unknown")
        emoji = status_emoji.get(status, "❓")
        
        print(f"\n{emoji} {test.get('test_name', test['test_id'])}")
        print(f"   ID: {test['test_id']}")
        print(f"   Prompt: {test['prompt_name']}")
        print(f"   版本：{test['version_a']} vs {test['version_b']}")
        print(f"   状态：{status}")
        
        if status == "completed":
            winner = test.get("winner", "unknown")
            print(f"   胜出者：{winner}")
            if "metrics_a_avg" in test:
                print(f"   版本 A 平均指标：{json.dumps(test['metrics_a_avg'], ensure_ascii=False)}")
            if "metrics_b_avg" in test:
                print(f"   版本 B 平均指标：{json.dumps(test['metrics_b_avg'], ensure_ascii=False)}")


def cmd_recommend(args):
    """推荐最佳版本"""
    mgr = PromptVersionManager()
    
    recommended = mgr.get_recommended_version(args.prompt)
    
    if not recommended:
        print(f"❌ 无法推荐版本：{args.prompt} 无版本记录")
        sys.exit(1)
    
    print(f"⭐ 推荐版本：{args.prompt} {recommended}")
    
    # 显示推荐原因
    versions = mgr.get_all_versions(args.prompt)
    completed_tests = [
        t for t in mgr.get_ab_test_history(args.prompt)
        if t.get("status") == "completed"
    ]
    
    if completed_tests:
        win_counts = {}
        for test in completed_tests:
            winner = test.get("winner")
            if winner:
                win_counts[winner] = win_counts.get(winner, 0) + 1
        
        print(f"   推荐原因：在 {len(completed_tests)} 次 A/B 测试中胜出 {win_counts.get(recommended, 0)} 次")
    else:
        print(f"   推荐原因：最新版本（无 A/B 测试数据）")


def main():
    parser = argparse.ArgumentParser(
        description="Prompt 版本管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # register 命令
    parser_register = subparsers.add_parser("register", help="注册新 Prompt 版本")
    parser_register.add_argument("prompt", help="Prompt 名称")
    parser_register.add_argument("version", help="版本号 (如 v1.0, v2.0)")
    parser_register.add_argument("file", help="Prompt 文件路径")
    parser_register.add_argument("--metadata", "-m", help="JSON 格式的元数据")
    parser_register.set_defaults(func=cmd_register)
    
    # list 命令
    parser_list = subparsers.add_parser("list", help="列出所有 Prompt 版本")
    parser_list.set_defaults(func=cmd_list)
    
    # show 命令
    parser_show = subparsers.add_parser("show", help="显示版本详情")
    parser_show.add_argument("prompt", help="Prompt 名称")
    parser_show.add_argument("version", help="版本号")
    parser_show.add_argument("--content", "-c", action="store_true", help="显示完整内容")
    parser_show.set_defaults(func=cmd_show)
    
    # create-ab-test 命令
    parser_create = subparsers.add_parser("create-ab-test", help="创建 A/B 测试")
    parser_create.add_argument("prompt", help="Prompt 名称")
    parser_create.add_argument("version_a", help="版本 A")
    parser_create.add_argument("version_b", help="版本 B")
    parser_create.add_argument("--name", "-n", help="测试名称")
    parser_create.set_defaults(func=cmd_create_ab_test)
    
    # run-ab-test 命令
    parser_run = subparsers.add_parser("run-ab-test", help="运行 A/B 测试")
    parser_run.add_argument("prompt", help="Prompt 名称")
    parser_run.add_argument("version_a", help="版本 A")
    parser_run.add_argument("version_b", help="版本 B")
    parser_run.add_argument("--cases", "-c", help="测试案例文件 (JSON)")
    parser_run.add_argument("--output", "-o", help="输出报告文件")
    parser_run.set_defaults(func=cmd_run_ab_test)
    
    # history 命令
    parser_history = subparsers.add_parser("history", help="显示 A/B 测试历史")
    parser_history.add_argument("--prompt", "-p", help="筛选特定 Prompt")
    parser_history.set_defaults(func=cmd_history)
    
    # recommend 命令
    parser_recommend = subparsers.add_parser("recommend", help="推荐最佳版本")
    parser_recommend.add_argument("prompt", help="Prompt 名称")
    parser_recommend.set_defaults(func=cmd_recommend)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
