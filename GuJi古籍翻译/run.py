#!/usr/bin/env python3
"""
面向古籍文本的语义理解与知识图谱构建 - 主运行脚本
======================================================

本脚本是整个项目的入口，支持以下运行模式：
- full: 完整流水线（清洗 -> 分词 -> NER -> 关系抽取 -> 知识图谱）
- clean: 仅文本清洗
- ner: 清洗 + 命名实体识别
- re: 清洗 + NER + 关系抽取
- build_kg: 从标注文件构建知识图谱

用法:
    python run.py --mode full --input data/sample_raw.txt
    python run.py --mode clean --input data/sample_raw.txt
    python run.py --mode ner --input data/sample_raw.txt
    python run.py --mode build_kg --input data/sample_annotated.json
    python run.py --serve --port 8000  # Web服务无需input
"""

import argparse
import os
import sys

# ===================== 新增：全局配置 Hugging Face 国内镜像 =====================
# 使用国内镜像，彻底解决连接超时问题
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
# 禁用在线检查，加快加载速度
os.environ['TRANSFORMERS_OFFLINE'] = '0'
# ==============================================================================

from loguru import logger


def setup_logging(log_level: str = "INFO", log_file: str = None):
    """配置日志系统。

    Args:
        log_level: 日志级别
        log_file: 日志文件路径（可选）
    """
    # 移除默认handler
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stderr,
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}",
    )

    # 文件输出
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        logger.add(
            log_file,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="7 days",
        )


def load_config(config_path: str) -> dict:
    """加载YAML配置文件。

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.info(f"配置文件加载成功: {config_path}")
        return config or {}
    except ImportError:
        logger.warning("PyYAML未安装，使用默认配置")
        return {}
    except FileNotFoundError:
        logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
        return {}


def main():
    """主函数。"""
    parser = argparse.ArgumentParser(
        description="面向古籍文本的语义理解与知识图谱构建",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py --mode full --input data/sample_raw.txt
  python run.py --mode clean --input data/sample_raw.txt --output data/cleaned.txt
  python run.py --mode ner --input data/sample_raw.txt
  python run.py --mode build_kg --input data/sample_annotated.json
  python run.py --serve --port 8000  # 启动Web服务
        """,
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="full",
        choices=["full", "clean", "ner", "re", "build_kg"],
        help="运行模式 (默认: full)",
    )
    # ===================== 核心修复1：input改为非必填 =====================
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=False,  # 原代码：required=True
        help="输入文件路径（Web服务模式无需填写）",
    )
    # ====================================================================
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出文件路径 (默认: 自动生成)",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="config/config.yaml",
        help="配置文件路径 (默认: config/config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认: INFO)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="计算设备 (默认: auto)",
    )
    parser.add_argument(
        "--no-kg",
        action="store_true",
        help="跳过知识图谱构建步骤",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="启动Web API服务",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Web API服务端口 (默认: 8000)",
    )
    parser.add_argument(
        "--few-shot",
        action="store_true",
        help="使用少样本学习模式训练NER模型",
    )
    parser.add_argument(
        "--augment-factor",
        type=int,
        default=3,
        help="少样本数据增强倍数 (默认: 3)",
    )

    args = parser.parse_args()

    # ===================== 核心修复2：非服务模式必须指定input =====================
    if not args.serve and not args.input:
        logger.error("错误：本地处理模式必须指定 --input/-i 参数！")
        logger.error("Web服务请使用命令：python run.py --serve --port 8000")
        sys.exit(1)
    # ==========================================================================

    # 配置日志
    setup_logging(log_level=args.log_level, log_file="logs/guji.log")

    logger.info("=" * 60)
    logger.info("面向古籍文本的语义理解与知识图谱构建")
    logger.info("=" * 60)
    logger.info(f"运行模式: {args.mode}")
    # Web服务不打印输入文件
    if not args.serve:
        logger.info(f"输入文件: {args.input}")

    # ===================== 核心修复3：仅非服务模式检查输入文件 =====================
    if not args.serve and not os.path.isfile(args.input):
        logger.error(f"输入文件不存在: {args.input}")
        sys.exit(1)
    # ==========================================================================

    # 加载配置
    config = load_config(args.config)
    config["device"] = args.device

    # 如果指定跳过知识图谱，调整模式
    if args.no_kg and args.mode == "full":
        args.mode = "re"

    # 启动Web API服务
    if args.serve:
        logger.info(f"启动Web API服务，端口: {args.port}")
        import uvicorn
        uvicorn.run(
            "src.web_api:app",
            host="0.0.0.0",
            port=args.port,
            reload=True,
        )
        return

    # 少样本学习训练模式
    if args.few_shot:
        logger.info("少样本学习训练模式")
        from src.few_shot import FewShotTrainer
        from src.ner.dataset import NERDataset

        # 加载标注数据
        dataset = NERDataset.from_annotated_file(args.input)
        logger.info(f"加载标注数据: {len(dataset)} 个样本")

        trainer = FewShotTrainer(
            pretrained_model=config.get("ner", {}).get("pretrained_model", "bert-base-chinese"),
            device=args.device,
        )

        predictor = trainer.train_with_augmentation(
            dataset=dataset,
            augmentation_factor=args.augment_factor,
            num_epochs=config.get("ner", {}).get("num_epochs", 10),
            save_dir=config.get("ner", {}).get("model_save_dir", "models/ner_fewshot"),
        )
        logger.info("少样本学习训练完成！")
        return

    # 创建流水线
    from src.pipeline import GuJiPipeline

    pipeline = GuJiPipeline(config=config)

    # 运行流水线
    result = pipeline.run(
        input_path=args.input,
        mode=args.mode,
        output_path=args.output,
    )

    # 输出结果摘要
    print(result.summary())

    # 保存结果
    if args.output is None:
        base_name = os.path.splitext(os.path.basename(args.input))[0]
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        args.output = os.path.join(output_dir, f"{base_name}_result.json")

    result.save(args.output)

    logger.info("处理完成！")


if __name__ == "__main__":
    main()