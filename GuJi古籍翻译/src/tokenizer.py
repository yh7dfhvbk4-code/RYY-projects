"""
古籍分词、断句与词性标注模块
==============================

本模块实现了面向古籍文本的分词、断句与词性标注功能，包括：
- 基于HanLP的古籍分词与词性标注
- 古籍断句（基于标点和语义）
- 自定义古籍词典加载
- 分词结果的数据结构定义

典型用法:
    >>> tokenizer = AncientTokenizer()
    >>> result = tokenizer.process("屈原者，名平，楚之同姓也。")
    >>> print(result.sentences)
    >>> print(result.words)
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from loguru import logger
import hanlp

@dataclass
class Token:
    """单个词元（Token）的数据结构。

    Attributes:
        text: 词元文本
        pos: 词性标注标签
        start: 在原文中的起始位置（字符偏移）
        end: 在原文中的结束位置（字符偏移）
    """
    text: str
    pos: str
    start: int
    end: int

    def to_dict(self) -> Dict:
        """转换为字典格式。"""
        return {
            "text": self.text,
            "pos": self.pos,
            "start": self.start,
            "end": self.end,
        }


@dataclass
class Sentence:
    """句子数据结构。

    Attributes:
        text: 句子原文
        start: 在原文中的起始位置
        end: 在原文中的结束位置
        tokens: 句子内的词元列表
    """
    text: str
    start: int
    end: int
    tokens: List[Token] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典格式。"""
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "tokens": [t.to_dict() for t in self.tokens],
        }


@dataclass
class TokenizationResult:
    """分词与断句的完整结果。

    Attributes:
        text: 原始文本
        sentences: 句子列表
        words: 所有词元列表
    """
    text: str
    sentences: List[Sentence] = field(default_factory=list)
    words: List[Token] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典格式。"""
        return {
            "text": self.text,
            "sentences": [s.to_dict() for s in self.sentences],
            "words": [w.to_dict() for w in self.words],
        }


class AncientTokenizer:
    """古籍分词、断句与词性标注器。

    基于HanLP实现古籍文本的分词、词性标注与断句功能，
    并支持自定义古籍词典以提升分词质量。

    Attributes:
        hanlp_model: HanLP模型名称
        custom_dict_path: 自定义词典路径
        max_sentence_length: 断句最大长度
        sentence_delimiters: 断句分隔标点集合
        keep_punctuation: 是否保留标点
    """

    # 古籍常见词性映射（HanLP词性标签 -> 古籍语义标签）
    POS_MAPPING = {
        "NR": "PER",      # 人名 -> 人物
        "NS": "LOC",      # 地名 -> 地点
        "NT": "ORG",      # 机构名 -> 组织
        "NN": "NOUN",     # 名词
        "VV": "VERB",     # 动词
        "VA": "ADJ",      # 形容词
        "AD": "ADV",      # 副词
        "P": "PREP",      # 介词
        "CS": "CONJ",     # 连词
        "SP": "PART",     # 助词
        "PU": "PUNCT",    # 标点
        "DT": "DET",      # 限定词
        "CD": "NUM",      # 数词
        "M": "MEAS",      # 量词
        "IJ": "INTJ",     # 感叹词
    }

    # 古籍专有词性标签
    ANCIENT_POS_TAGS = {
        "OFF",    # 官职
        "EVT",    # 事件
        "TITLE",  # 书名/篇名
        "HON",    # 尊号/谥号
        "DYN",    # 朝代
    }

    def __init__(
        self,
        hanlp_model: str = "hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH",
        custom_dict_path: Optional[str] = None,
        max_sentence_length: int = 128,
        sentence_delimiters: str = "。！？；",
        keep_punctuation: bool = True,
    ):
        """初始化古籍分词器。

        Args:
            hanlp_model: HanLP使用的模型名称，默认为CTB9_TOK_POS
            custom_dict_path: 自定义古籍词典路径，每行一个词条
            max_sentence_length: 断句的最大字符长度
            sentence_delimiters: 用于断句的标点符号集合
            keep_punctuation: 是否在分词结果中保留标点符号
        """
        self.hanlp_model_name = hanlp_model
        self.custom_dict_path = custom_dict_path
        self.max_sentence_length = max_sentence_length
        self.sentence_delimiters = set(sentence_delimiters)
        self.keep_punctuation = keep_punctuation

        # HanLP管线（延迟加载）
        self._hanlp_pipeline = None
        # 自定义词典
        self._custom_words: Dict[str, str] = {}

        logger.info(
            f"古籍分词器初始化 | 模型: {hanlp_model} | "
            f"最大句长: {max_sentence_length} | 保留标点: {keep_punctuation}"
        )

    def _load_hanlp(self):
    
        if self._hanlp_pipeline is not None:
            return

        try:
            import hanlp

        # ✅ 核心修改：替换旧版CTB9_TOK_POS为HanLP2.x官方模型
            self._hanlp_pipeline = hanlp.load(
                hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH
            )
            logger.info("HanLP模型加载成功")

        # 新增：注入自定义词典到HanLP
            if self._custom_words:
                self._hanlp_pipeline['tok'].dict_combine(self._custom_words.keys())
                logger.info(f"已注入 {len(self._custom_words)} 个自定义词到HanLP")
            
        except ImportError:
            logger.warning(
            "HanLP未安装，将使用基于规则的分词方式。"
            "可通过 pip install hanlp 安装。"
            )
            self._hanlp_pipeline = None
        except Exception as e:
            logger.warning(f"HanLP模型加载失败: {e}，将使用基于规则的分词方式")
            self._hanlp_pipeline = None

    def load_custom_dict(self, dict_path: Optional[str] = None):
        """加载自定义古籍词典。

        词典文件格式为每行一个词条，可选包含词性标签，
        以制表符分隔，如：屈原	PER

        Args:
            dict_path: 词典文件路径，若为None则使用初始化时指定的路径
        """
        path = dict_path or self.custom_dict_path
        if path is None:
            logger.debug("未指定自定义词典路径，跳过加载")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("	")
                    word = parts[0]
                    pos = parts[1] if len(parts) > 1 else "CUSTOM"
                    self._custom_words[word] = pos

            logger.info(f"自定义词典加载完成: {len(self._custom_words)} 个词条")
        except FileNotFoundError:
            logger.warning(f"词典文件不存在: {path}")

    def _rule_based_tokenize(self, text: str) -> List[Tuple[str, str]]:
        """基于规则的分词方法（HanLP不可用时的回退方案）。

        使用正向最大匹配算法，结合自定义词典进行分词。
        对于词典中未收录的词，按单字切分。

        Args:
            text: 输入文本

        Returns:
            分词结果列表，每个元素为 (词文本, 词性标签) 的元组
        """
        # 获取自定义词典中的最大词长
        max_word_len = max((len(w) for w in self._custom_words), default=1)

        tokens = []
        i = 0
        while i < len(text):
            # 尝试最长匹配
            matched = False
            for length in range(min(max_word_len, len(text) - i), 0, -1):
                candidate = text[i:i + length]
                if candidate in self._custom_words:
                    tokens.append((candidate, self._custom_words[candidate]))
                    i += length
                    matched = True
                    break

            if not matched:
                ch = text[i]
                # 判断字符类型
                if re.match(r"[\s]", ch):
                    pos = "SPACE"
                elif re.match(r"[，。！？；：""''《》（）\-\—\…]", ch):
                    pos = "PU"
                elif re.match(r"[一-鿿]", ch):
                    pos = "NN"  # 默认单字名词
                else:
                    pos = "UNK"
                tokens.append((ch, pos))
                i += 1

        return tokens

    def _hanlp_tokenize(self, text: str) -> List[Tuple[str, str]]:
        """使用HanLP进行分词和词性标注。

        Args:
            text: 输入文本

        Returns:
            分词结果列表，每个元素为 (词文本, 词性标签) 的元组
        """
        self._load_hanlp()

        if self._hanlp_pipeline is None:
            return self._rule_based_tokenize(text)

        try:
            result = self._hanlp_pipeline(text)
            # HanLP返回的结果格式处理
            tokens = []
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        tokens.append((str(item[0]), str(item[1])))
                    elif isinstance(item, str):
                        tokens.append((item, "UNK"))
            return tokens
        except Exception as e:
            logger.warning(f"HanLP分词失败: {e}，回退到规则分词")
            return self._rule_based_tokenize(text)

    def segment_sentences(self, text: str) -> List[Sentence]:
        """对文本进行断句处理。

        基于标点符号和最大长度约束对文本进行断句，
        保留每个句子在原文中的位置信息。

        Args:
            text: 输入文本

        Returns:
            句子列表
        """
        sentences = []
        current_start = 0
        current_text = ""

        for i, ch in enumerate(text):
            current_text += ch

            # 遇到断句标点或超过最大长度时断句
            if ch in self.sentence_delimiters or len(current_text) >= self.max_sentence_length:
                stripped = current_text.strip()
                if stripped:
                    sentences.append(Sentence(
                        text=stripped,
                        start=current_start,
                        end=i + 1,
                    ))
                current_start = i + 1
                current_text = ""

        # 处理末尾未断句的文本
        if current_text.strip():
            sentences.append(Sentence(
                text=current_text.strip(),
                start=current_start,
                end=len(text),
            ))

        return sentences

    def tokenize(self, text: str) -> List[Token]:
        """对文本进行分词和词性标注。

        Args:
            text: 输入文本

        Returns:
            词元列表
        """
        raw_tokens = self._hanlp_tokenize(text)

        tokens = []
        offset = 0
        for word, pos in raw_tokens:
            # 跳过空白
            if pos == "SPACE":
                offset += len(word)
                continue

            # 跳过标点（如果配置不保留）
            if not self.keep_punctuation and pos == "PU":
                offset += len(word)
                continue

            # 查找词在文本中的精确位置
            start = text.find(word, offset)
            if start == -1:
                start = offset
            end = start + len(word)
            offset = end

            # 映射词性标签
            mapped_pos = self.POS_MAPPING.get(pos, pos)

            tokens.append(Token(
                text=word,
                pos=mapped_pos,
                start=start,
                end=end,
            ))

        return tokens

    def process(self, text: str) -> TokenizationResult:
        """执行完整的分词、断句与词性标注流程。

        先对文本进行断句，再对每个句子进行分词和词性标注，
        最后汇总所有结果。

        Args:
            text: 输入文本

        Returns:
            包含句子和词元信息的完整分词结果

        Example:
            >>> tokenizer = AncientTokenizer()
            >>> result = tokenizer.process("屈原者，名平，楚之同姓也。")
            >>> for sent in result.sentences:
            ...     print(f"句子: {sent.text}")
            ...     for token in sent.tokens:
            ...         print(f"  {token.text}/{token.pos}")
        """
        logger.info(f"开始分词处理，文本长度: {len(text)} 字符")

        # 加载自定义词典（如果尚未加载）
        if not self._custom_words:
            self.load_custom_dict()

        # Step 1: 断句
        sentences = self.segment_sentences(text)
        logger.info(f"断句完成，共 {len(sentences)} 个句子")

        # Step 2: 对每个句子进行分词
        all_tokens = []
        for sentence in sentences:
            tokens = self.tokenize(sentence.text)
            sentence.tokens = tokens
            all_tokens.extend(tokens)

        # Step 3: 构建结果
        result = TokenizationResult(
            text=text,
            sentences=sentences,
            words=all_tokens,
        )

        logger.info(
            f"分词完成 | 句子数: {len(sentences)} | 词元数: {len(all_tokens)}"
        )
        return result

    def process_file(self, input_path: str, output_path: Optional[str] = None) -> TokenizationResult:
        """处理文本文件。

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（JSON格式），若为None则不保存

        Returns:
            分词结果
        """
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()

        result = self.process(text)

        if output_path:
            import json
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"分词结果已保存至: {output_path}")

        return result
