"""RAG 命令行入口。

用法：
    python cli.py build [--force]     建库（默认增量，--force 全量重建）
    python cli.py query "你的问题"     问答（需 API key：--api-key 或环境变量 LLM_API_KEY）
    python cli.py retrieve "你的问题"  仅召回+重排（不调 LLM，用于调试检索效果）
    python cli.py stats               库状态
"""
import argparse

from rag.engine import RAGEngine


def main() -> None:
    # 公共参数通过 parents 传入各子命令，子命令前后均可使用
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api-key", help="LLM API key（也可设环境变量 LLM_API_KEY）")
    common.add_argument("--base-url", help="LLM base_url（默认 DeepSeek）")
    common.add_argument("--model", help="LLM 模型名（默认 deepseek-chat）")

    parser = argparse.ArgumentParser(description="个人知识库 RAG", parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)
    p_build = sub.add_parser("build", parents=[common], help="构建/更新索引")
    p_build.add_argument("--force", action="store_true", help="强制全量重建")
    p_query = sub.add_parser("query", parents=[common], help="问答（召回+重排+生成）")
    p_query.add_argument("question", help="问题")
    p_query.add_argument("--top-n", type=int, help="重排后送入生成的分片数")
    p_retr = sub.add_parser("retrieve", parents=[common], help="仅召回+重排，不调 LLM")
    p_retr.add_argument("question", help="问题")
    p_retr.add_argument("--top-n", type=int, help="重排后返回的分片数")
    sub.add_parser("stats", parents=[common], help="库状态")

    args = parser.parse_args()
    engine = RAGEngine(api_key=args.api_key, base_url=args.base_url, model=args.model)

    if args.command == "build":
        engine.build(force=args.force)
    elif args.command == "query":
        result = engine.query(args.question, top_n=args.top_n)
        print("\n=== 回答 ===")
        print(result["answer"])
        print("\n=== 来源 ===")
        for s in result["sources"]:
            print(f"  - {s['source']} (score={s['score']})")
    elif args.command == "retrieve":
        ranked = engine.retrieve(args.question, top_n=args.top_n)
        print(f"\n=== 重排后 top-{len(ranked)} ===")
        for doc, score in ranked:
            src = doc.metadata.get("source", "")
            print(f"\n[{score:.4f}] {src}")
            print(doc.page_content[:200])
    elif args.command == "stats":
        print(engine.stats())


if __name__ == "__main__":
    main()
