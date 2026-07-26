"""
古籍文本处理Web API接口
=========================

基于FastAPI实现的RESTful API，提供古籍文本处理的在线服务。

接口列表:
    POST /api/clean       - 文本清洗
    POST /api/tokenize    - 分词断句
    POST /api/ner         - 命名实体识别
    POST /api/relation    - 关系抽取
    POST /api/pipeline    - 完整流水线
    GET  /api/kg/stats    - 知识图谱统计
    POST /api/kg/query    - 知识图谱查询
    GET  /api/health      - 健康检查

启动方式:
    uvicorn src.web_api:app --host 0.0.0.0 --port 8000 --reload
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from loguru import logger


# ============ 请求/响应模型 ============

class TextRequest(BaseModel):
    """文本处理请求。"""
    text: str = Field(..., description="输入文本", min_length=1)
    options: Optional[Dict[str, Any]] = Field(default=None, description="可选参数")


class FileRequest(BaseModel):
    """文件处理请求。"""
    file_path: str = Field(..., description="输入文件路径")


class NERRequest(BaseModel):
    """NER请求。"""
    text: str = Field(..., description="输入文本", min_length=1)


class RelationRequest(BaseModel):
    """关系抽取请求。"""
    text: str = Field(..., description="输入文本", min_length=1)
    entities: List[Dict[str, Any]] = Field(..., description="实体列表")


class KGQueryRequest(BaseModel):
    """知识图谱查询请求。"""
    entity_name: Optional[str] = Field(default=None, description="实体名称")
    relation_type: Optional[str] = Field(default=None, description="关系类型")
    limit: int = Field(default=100, description="返回结果上限")


class PipelineRequest(BaseModel):
    """流水线请求。"""
    text: str = Field(..., description="输入文本", min_length=1)
    mode: str = Field(default="full", description="运行模式")


class EntityResponse(BaseModel):
    """实体识别结果。"""
    text: str
    type: str
    start: int
    end: int


class RelationResponse(BaseModel):
    """关系抽取结果。"""
    head: Dict[str, Any]
    tail: Dict[str, Any]
    type: str
    confidence: float = 0.0


class StandardResponse(BaseModel):
    """标准API响应。"""
    success: bool = True
    message: str = "ok"
    data: Optional[Any] = None


# ============ FastAPI应用 ============

app = FastAPI(
    title="古籍文本语义理解与知识图谱构建 API",
    description="面向古籍文本的语义理解与知识图谱构建方法的在线服务接口",
    version="1.0.0",
)

# 全局流水线实例（延迟初始化）
_pipeline = None


def get_pipeline():
    """获取流水线单例。"""
    global _pipeline
    if _pipeline is None:
        from src.pipeline import GuJiPipeline
        config_path = "config/config.yaml"
        if os.path.exists(config_path):
            from src.pipeline import create_pipeline_from_config
            _pipeline = create_pipeline_from_config(config_path)
        else:
            _pipeline = GuJiPipeline()
    return _pipeline


# ============ API路由 ============

@app.get("/api/health", response_model=StandardResponse, tags=["系统"])
async def health_check():
    """健康检查接口。"""
    return StandardResponse(
        success=True,
        message="服务运行正常",
        data={"version": "1.0.0"},
    )


@app.post("/api/clean", response_model=StandardResponse, tags=["文本处理"])
async def clean_text(request: TextRequest):
    """文本清洗接口。

    对古籍OCR文本进行清洗，包括去噪、繁简转换、规范化等。
    """
    try:
        pipeline = get_pipeline()
        cleaned = pipeline.step_clean(request.text)
        return StandardResponse(
            success=True,
            message="文本清洗完成",
            data={"cleaned_text": cleaned},
        )
    except Exception as e:
        logger.error(f"文本清洗失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tokenize", response_model=StandardResponse, tags=["文本处理"])
async def tokenize_text(request: TextRequest):
    """分词断句接口。

    对文本进行分词、词性标注和断句处理。
    """
    try:
        pipeline = get_pipeline()
        result = pipeline.step_tokenize(request.text)
        return StandardResponse(
            success=True,
            message="分词断句完成",
            data=result,
        )
    except Exception as e:
        logger.error(f"分词断句失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ner", response_model=StandardResponse, tags=["实体识别"])
async def named_entity_recognition(request: NERRequest):
    """命名实体识别接口。

    识别文本中的人物、地点、官职、事件等命名实体。
    """
    try:
        pipeline = get_pipeline()
        entities = pipeline.step_ner(request.text)
        return StandardResponse(
            success=True,
            message=f"识别到 {len(entities)} 个实体",
            data={"entities": entities},
        )
    except Exception as e:
        logger.error(f"NER失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/relation", response_model=StandardResponse, tags=["关系抽取"])
async def extract_relations(request: RelationRequest):
    """关系抽取接口。

    根据文本和已识别的实体，抽取实体间的关系。
    """
    try:
        pipeline = get_pipeline()
        relations = pipeline.step_relation_extraction(request.text, request.entities)
        return StandardResponse(
            success=True,
            message=f"抽取到 {len(relations)} 个关系",
            data={"relations": relations},
        )
    except Exception as e:
        logger.error(f"关系抽取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipeline", response_model=StandardResponse, tags=["流水线"])
async def run_pipeline(request: PipelineRequest):
    """完整流水线接口。

    执行从文本清洗到知识图谱构建的完整流程。
    """
    try:
        pipeline = get_pipeline()
        # 将文本写入临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(request.text)
            temp_path = f.name

        try:
            result = pipeline.run(input_path=temp_path, mode=request.mode)
            return StandardResponse(
                success=True,
                message="流水线处理完成",
                data=result.to_dict(),
            )
        finally:
            os.unlink(temp_path)
    except Exception as e:
        logger.error(f"流水线处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kg/stats", response_model=StandardResponse, tags=["知识图谱"])
async def kg_statistics():
    """知识图谱统计接口。

    返回知识图谱的节点数、关系数等统计信息。
    """
    try:
        pipeline = get_pipeline()
        stats = pipeline.kg_builder.get_statistics()
        return StandardResponse(
            success=True,
            message="统计信息获取成功",
            data=stats,
        )
    except Exception as e:
        logger.error(f"统计信息获取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kg/query", response_model=StandardResponse, tags=["知识图谱"])
async def query_knowledge_graph(request: KGQueryRequest):
    """知识图谱查询接口。

    根据实体名称或关系类型查询知识图谱。
    """
    try:
        pipeline = get_pipeline()
        if request.entity_name:
            results = pipeline.kg_builder.query_entity(request.entity_name)
        elif request.relation_type:
            results = pipeline.kg_builder.query_relations(
                relation_type=request.relation_type,
                limit=request.limit,
            )
        else:
            results = pipeline.kg_builder.query_relations(limit=request.limit)

        return StandardResponse(
            success=True,
            message=f"查询到 {len(results)} 条结果",
            data={"results": results},
        )
    except Exception as e:
        logger.error(f"知识图谱查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 启动入口 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.web_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
