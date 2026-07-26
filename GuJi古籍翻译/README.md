# 面向古籍文本的语义理解与知识图谱构建方法研究

## 项目简介

本项目实现了一套完整的古籍文本处理流水线，涵盖从原始OCR文本清洗到知识图谱构建的全流程，
旨在为古籍数字化与智能化研究提供基础工具与算法框架。

## 核心功能

| 模块 | 功能说明 |
|------|----------|
| `text_cleaner` | 古籍OCR后处理与文本清洗 |
| `tokenizer` | 古籍分词、断句与词性标注 |
| `ner` | 古籍命名实体识别（人物、地点、官职、事件） |
| `relation_extractor` | 实体关系抽取 |
| `knowledge_graph` | 知识图谱构建与Neo4j存储 |
| `models` | BERT-CC预训练模型微调与少样本学习 |
| `pipeline` | 端到端处理流水线 |

## 项目结构

```
GuJi/
├── config/                   # 配置文件
│   └── config.yaml
├── data/                     # 示例数据
│   ├── sample_raw.txt        # 示例原始文本
│   ├── sample_annotated.json # 示例标注数据
│   └── custom_dict.txt       # 自定义古籍词典
├── src/                      # 核心源代码
│   ├── __init__.py
│   ├── text_cleaner.py       # 文本清洗模块
│   ├── tokenizer.py          # 分词与断句模块
│   ├── ner/                  # 命名实体识别模块
│   │   ├── __init__.py
│   │   ├── dataset.py        # 数据集与数据增强
│   │   ├── model.py          # BERT-CRF模型
│   │   └── predictor.py      # 推理与训练
│   ├── relation_extractor.py # 关系抽取模块
│   ├── knowledge_graph.py    # 知识图谱模块
│   ├── few_shot.py           # 少样本学习模块
│   ├── pipeline.py           # 端到端流水线
│   └── web_api.py            # Web API接口
├── models/                   # 模型存储目录
├── logs/                     # 日志目录
├── output/                   # 输出目录
├── run.py                    # 主运行脚本
├── requirements.txt
├── .gitignore
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置Neo4j

确保Neo4j数据库已启动，并修改 `config/config.yaml` 中的连接配置。

### 3. 运行完整流水线

```bash
python run.py --mode full --input data/sample_raw.txt
```

### 4. 单模块运行

```bash
# 仅文本清洗
python run.py --mode clean --input data/sample_raw.txt

# 仅命名实体识别
python run.py --mode ner --input data/sample_raw.txt

# 仅知识图谱构建
python run.py --mode build_kg --input data/sample_annotated.json
```

### 5. 少样本学习训练

```bash
# 使用数据增强+微调
python run.py --few-shot --input data/sample_annotated.json --augment-factor 3

# 使用原型网络（需在Python代码中调用）
python -c "from src.few_shot import FewShotTrainer; ..."
```

### 6. 启动Web API服务

```bash
python run.py --serve --port 8000
```

启动后访问 `http://localhost:8000/docs` 查看API文档。

### 7. API调用示例

```bash
# 文本清洗
curl -X POST http://localhost:8000/api/clean \
  -H "Content-Type: application/json" \
  -d '{"text": "□太史公曰◇：余读《离骚》"}'

# 命名实体识别
curl -X POST http://localhost:8000/api/ner \
  -H "Content-Type: application/json" \
  -d '{"text": "屈原者，名平，楚之同姓也。"}'

# 完整流水线
curl -X POST http://localhost:8000/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{"text": "屈原者，名平，楚之同姓也。为楚怀王左徒。", "mode": "full"}'
```

## 技术栈

- **Python 3.12**
- **PyTorch 2.0+**
- **Transformers 4.40+** (BERT-CC预训练模型)
- **HanLP 2.3+** (分词与词性标注)
- **Neo4j Python Driver 5.0+** (知识图谱存储)
- **Scikit-learn 1.4+** (少样本学习)

## 许可证

MIT License
