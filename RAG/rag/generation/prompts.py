"""Prompt 模板。"""

SYSTEM_PROMPT = """你是一个基于个人知识库回答问题的助手。规则：
1. 仅根据下方提供的上下文回答，不要编造上下文之外的信息。
2. 回答中引用信息时，在句末标注来源文件名，格式为【来源:文件名】。
3. 如果上下文不足以回答问题，明确回答"知识库中没有相关信息"，不要强行作答。
4. 回答使用与用户问题相同的语言，简洁准确。"""

USER_PROMPT_TEMPLATE = """上下文：
{context}

问题：{question}"""


def build_context(chunks: list[tuple]) -> str:
    """将重排后的 (Document, score) 列表拼装为上下文字符串。"""
    blocks = []
    for i, (doc, _score) in enumerate(chunks, 1):
        source = doc.metadata.get("source", "未知来源")
        title_path = doc.metadata.get("title_path")
        location = f"{source}（{title_path}）" if title_path else source
        blocks.append(f"[片段{i} | {location}]\n{doc.page_content}")
    return "\n\n".join(blocks)
