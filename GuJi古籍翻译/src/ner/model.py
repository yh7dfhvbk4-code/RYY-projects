"""
古籍NER模型定义模块
======================

本模块实现了基于BERT-CRF的古籍命名实体识别模型，包括：
- BertCRFConfig: 模型配置类
- BertCRF: BERT-CRF联合模型
- CRF层实现
- 模型训练与评估函数

BERT-CRF模型结构:
    Input -> BERT Encoder -> Dropout -> Linear -> CRF -> Output

典型用法:
    >>> config = BertCRFConfig.from_pretrained("bert-base-chinese")
    >>> model = BertCRF(config)
    >>> outputs = model(input_ids, attention_mask, labels)
    >>> loss = outputs.loss
    >>> logits = outputs.logits
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
# ✅ 修复1：替换 PretrainedConfig 为 BertConfig
from transformers import (
    BertModel,
    BertPreTrainedModel,
    BertConfig,  # 核心修复：导入BertConfig
)
from loguru import logger


# ✅ 修复2：删除嵌套类！仅定义1次，直接继承 BertConfig
class BertCRFConfig(BertConfig):
    """BERT-CRF模型配置类。

    继承自Transformers的BertConfig，增加CRF相关配置参数。

    Attributes:
        num_labels: 标签数量（含O标签）
        dropout: Dropout概率
        bert_model_name: BERT预训练模型名称
        use_crf: 是否使用CRF层（False时退化为纯BERT分类）
    """
    model_type = "bert_crf"

    def __init__(
        self,
        num_labels: int = 13,
        dropout: float = 0.1,
        bert_model_name: str = "bert-base-chinese",
        use_crf: bool = True,
        **kwargs,
    ):
        # 初始化父类 BertConfig
        super().__init__(**kwargs)
        # 自定义参数（缩进、拼写全部正确）
        self.num_labels = num_labels
        self.dropout = dropout
        self.bert_model_name = bert_model_name
        self.use_crf = use_crf


class CRF(nn.Module):
    """条件随机场（CRF）层。

    实现线性链CRF，用于序列标注任务中的解码。
    CRF层能够学习标签之间的转移概率，确保输出的标签序列满足
    BIO标注的约束条件（如I-PER不能出现在O之后等）。

    Attributes:
        num_tags: 标签数量
        start_transitions: 起始转移分数，形状为 (num_tags,)
        end_transitions: 结束转移分数，形状为 (num_tags,)
        transitions: 转移矩阵，形状为 (num_tags, num_tags)
    """

    def __init__(self, num_tags: int):
        """初始化CRF层。

        Args:
            num_tags: 标签数量
        """
        super().__init__()
        self.num_tags = num_tags

        # 转移参数
        self.start_transitions = nn.Parameter(torch.empty(num_tags))
        self.end_transitions = nn.Parameter(torch.empty(num_tags))
        self.transitions = nn.Parameter(torch.empty(num_tags, num_tags))

        # 初始化
        nn.init.xavier_normal_(self.transitions)
        nn.init.normal_(self.start_transitions)
        nn.init.normal_(self.end_transitions)

    def forward(
        self,
        emissions: torch.Tensor,
        tags: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """计算CRF的负对数似然损失。

        Args:
            emissions: 发射分数，形状为 (batch_size, seq_len, num_tags)
            tags: 真实标签，形状为 (batch_size, seq_len)
            mask: 注意力掩码，形状为 (batch_size, seq_len)，1表示有效位置

        Returns:
            负对数似然损失，形状为 (batch_size,)
        """
        if mask is None:
            mask = torch.ones_like(tags, dtype=torch.bool)

        # 计算正确路径的分数
        gold_score = self._score_sentence(emissions, tags, mask)

        # 计算所有路径的logsumexp
        forward_score = self._forward_algorithm(emissions, mask)

        # 负对数似然
        return forward_score - gold_score

    def decode(
        self,
        emissions: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> List[List[int]]:
        """使用Viterbi算法解码最优标签序列。

        Args:
            emissions: 发射分数，形状为 (batch_size, seq_len, num_tags)
            mask: 注意力掩码，形状为 (batch_size, seq_len)

        Returns:
            最优标签序列列表，每个元素为该样本的标签ID列表
        """
        if mask is None:
            mask = emissions.new_ones(emissions.shape[:2], dtype=torch.bool)

        return self._viterbi_decode(emissions, mask)

    def _forward_algorithm(
        self,
        emissions: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        """前向算法，计算所有路径分数的logsumexp。

        Args:
            emissions: 发射分数 (batch_size, seq_len, num_tags)
            mask: 掩码 (batch_size, seq_len)

        Returns:
            所有路径分数的logsumexp (batch_size,)
        """
        batch_size, seq_len, num_tags = emissions.shape

        # 初始化：起始转移分数 + 第一个位置的发射分数
        alpha = self.start_transitions.unsqueeze(0) + emissions[:, 0]

        for i in range(1, seq_len):
            # alpha: (batch_size, num_tags) -> (batch_size, num_tags, 1)
            # transitions: (num_tags, num_tags) -> (1, num_tags, num_tags)
            # emissions: (batch_size, num_tags) -> (batch_size, 1, num_tags)
            emit_score = emissions[:, i].unsqueeze(1)
            trans_score = self.transitions.unsqueeze(0)
            alpha_expand = alpha.unsqueeze(2)

            # 计算新的alpha: (batch_size, num_tags)
            inner = alpha_expand + trans_score + emit_score
            new_alpha = torch.logsumexp(inner, dim=1)

            # 根据mask决定是否更新
            mask_i = mask[:, i].unsqueeze(1).float()
            alpha = new_alpha * mask_i + alpha * (1 - mask_i)

        # 加上结束转移分数
        end_score = alpha + self.end_transitions.unsqueeze(0)
        return torch.logsumexp(end_score, dim=1)

    def _score_sentence(
        self,
        emissions: torch.Tensor,
        tags: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        """计算给定标签序列的分数。

        Args:
            emissions: 发射分数 (batch_size, seq_len, num_tags)
            tags: 标签序列 (batch_size, seq_len)
            mask: 掩码 (batch_size, seq_len)

        Returns:
            给定标签序列的分数 (batch_size,)
        """
        batch_size, seq_len, num_tags = emissions.shape

        # 起始转移分数
        score = self.start_transitions[tags[:, 0]]

        # 发射分数
        score += emissions[:, 0].gather(1, tags[:, 0].unsqueeze(1)).squeeze(1)

        for i in range(1, seq_len):
            # 转移分数: 从tags[:, i-1]转移到tags[:, i]
            trans = self.transitions[tags[:, i - 1], tags[:, i]]
            # 发射分数
            emit = emissions[:, i].gather(1, tags[:, i].unsqueeze(1)).squeeze(1)

            # 根据mask累加
            mask_i = mask[:, i].float()
            score += (trans + emit) * mask_i

        # 结束转移分数
        # 找到每个序列的最后一个有效位置
        seq_ends = mask.long().sum(dim=1) - 1
        last_tags = tags.gather(1, seq_ends.unsqueeze(1)).squeeze(1)
        score += self.end_transitions[last_tags]

        return score

    def _viterbi_decode(
        self,
        emissions: torch.Tensor,
        mask: torch.Tensor,
    ) -> List[List[int]]:
        """Viterbi算法解码。

        Args:
            emissions: 发射分数 (batch_size, seq_len, num_tags)
            mask: 掩码 (batch_size, seq_len)

        Returns:
            最优标签序列列表
        """
        batch_size, seq_len, num_tags = emissions.shape

        # 初始化
        score = self.start_transitions.unsqueeze(0) + emissions[:, 0]
        history = []

        for i in range(1, seq_len):
            broadcast_score = score.unsqueeze(2)
            broadcast_emission = emissions[:, i].unsqueeze(1)

            # (batch_size, num_tags, num_tags)
            next_score = broadcast_score + self.transitions + broadcast_emission
            next_score, indices = next_score.max(dim=1)

            # 根据mask更新
            mask_i = mask[:, i].unsqueeze(1).float()
            score = next_score * mask_i + score * (1 - mask_i)
            history.append(indices)

        # 加上结束转移分数
        score += self.end_transitions.unsqueeze(0)

        # 回溯
        seq_ends = mask.long().sum(dim=1) - 1
        best_tags_list = []

        _, best_last_tag = score.max(dim=1)

        for idx in range(batch_size):
            best_tag = best_last_tag[idx].item()
            seq_len_i = seq_ends[idx].item()

            best_tags = [best_tag]
            for hist in reversed(history[:seq_len_i]):
                best_tag = hist[idx, best_tag].item()
                best_tags.append(best_tag)

            best_tags.reverse()
            best_tags_list.append(best_tags)

        return best_tags_list


class BertCRF(BertPreTrainedModel):
    """BERT-CRF古籍命名实体识别模型。

    模型结构:
        1. BERT编码器：提取上下文语义特征
        2. Dropout层：防止过拟合
        3. 线性层：将BERT输出映射到标签空间
        4. CRF层：建模标签间转移关系，解码最优标签序列

    该模型支持两种模式：
        - BERT-CRF模式（use_crf=True）：使用CRF层进行解码
        - 纯BERT模式（use_crf=False）：直接使用线性层输出

    Attributes:
        config: 模型配置
        bert: BERT模型
        dropout: Dropout层
        classifier: 线性分类层
        crf: CRF层（可选）
    """

    def __init__(self, config: BertCRFConfig):
        """初始化BERT-CRF模型。

        Args:
            config: 模型配置，包含num_labels、dropout等参数
        """
        super().__init__(config)
        self.config = config

        # BERT编码器
        self.bert = BertModel(config)

        # Dropout和分类层
        self.dropout = nn.Dropout(config.dropout)
        self.classifier = nn.Linear(config.hidden_size, config.num_labels)

        # CRF层
        if config.use_crf:
            self.crf = CRF(config.num_labels)
        else:
            self.crf = None

        # 初始化权重
        self.post_init()

        logger.info(
            f"BERT-CRF模型初始化 | 标签数: {config.num_labels} | "
            f"CRF: {config.use_crf} | Dropout: {config.dropout}"
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        token_type_ids: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """模型前向传播。

        Args:
            input_ids: 输入token ID序列 (batch_size, seq_len)
            attention_mask: 注意力掩码 (batch_size, seq_len)
            token_type_ids: 段落ID (batch_size, seq_len)
            labels: 真实标签 (batch_size, seq_len)，-100表示忽略

        Returns:
            包含以下键的字典:
                - loss: 损失值（仅当提供labels时返回）
                - logits: 模型输出分数 (batch_size, seq_len, num_labels)
                - predictions: 预测标签序列（仅当使用CRF时返回）
        """
        # BERT编码
        bert_outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        sequence_output = bert_outputs.last_hidden_state

        # Dropout + 线性映射
        sequence_output = self.dropout(sequence_output)
        emissions = self.classifier(sequence_output)

        result = {"logits": emissions}

        if self.crf is not None:
            # CRF模式
            if labels is not None:
                # 构建CRF的mask和标签
                crf_mask = attention_mask.bool() if attention_mask is not None else None
                crf_labels = labels.clone()

                # 将-100的位置替换为0（CRF需要连续的标签）
                if crf_mask is not None:
                    invalid_mask = labels == -100
                    crf_labels[invalid_mask] = 0
                    # 更新crf_mask，排除-100位置
                    crf_mask = crf_mask & (~invalid_mask)

                # 计算CRF损失
                loss = self.crf(emissions, crf_labels, crf_mask)
                result["loss"] = loss.mean()

            # 解码
            if attention_mask is not None:
                decode_mask = attention_mask.bool()
            else:
                decode_mask = None
            predictions = self.crf.decode(emissions, decode_mask)
            result["predictions"] = predictions
        else:
            # 纯BERT模式
            if labels is not None:
                loss_fct = nn.CrossEntropyLoss(ignore_index=-100)
                loss = loss_fct(
                    emissions.view(-1, self.config.num_labels),
                    labels.view(-1),
                )
                result["loss"] = loss

            predictions = emissions.argmax(dim=-1)
            result["predictions"] = predictions

        return result

    @classmethod
    def from_pretrained_bert(
        cls,
        bert_model_name: str = "bert-base-chinese",
        num_labels: int = 13,
        dropout: float = 0.1,
        use_crf: bool = True,
    ) -> "BertCRF":
        """从预训练BERT模型创建BERT-CRF模型。

        Args:
            bert_model_name: BERT预训练模型名称或路径
            num_labels: 标签数量
            dropout: Dropout概率
            use_crf: 是否使用CRF层

        Returns:
            BERT-CRF模型实例
        """
        from transformers import BertConfig

        # 加载BERT配置
        bert_config = BertConfig.from_pretrained(bert_model_name)

        # 创建BERT-CRF配置
        crf_config = BertCRFConfig(
            vocab_size=bert_config.vocab_size,
            hidden_size=bert_config.hidden_size,
            num_hidden_layers=bert_config.num_hidden_layers,
            num_attention_heads=bert_config.num_attention_heads,
            intermediate_size=bert_config.intermediate_size,
            num_labels=num_labels,
            dropout=dropout,
            bert_model_name=bert_model_name,
            use_crf=use_crf,
        )

        # 创建模型
        model = cls(crf_config)

        # 加载预训练BERT权重
        pretrained_bert = BertModel.from_pretrained(bert_model_name)
        model.bert.load_state_dict(pretrained_bert.state_dict())

        logger.info(f"从 {bert_model_name} 加载预训练权重完成")
        return model


@dataclass
class NEROutput:
    """NER模型输出数据结构。

    Attributes:
        loss: 损失值
        logits: 模型输出分数
        predictions: 预测标签序列
    """
    loss: Optional[torch.Tensor] = None
    logits: Optional[torch.Tensor] = None
    predictions: Optional[List[List[int]]] = None