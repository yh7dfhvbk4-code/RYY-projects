"""
古籍OCR后处理与文本清洗模块
============================

本模块实现了古籍文本的OCR后处理与清洗功能，包括：
- 噪声字符去除（OCR识别错误产生的乱码、标记符号等）
- 繁简转换
- 空白字符合并与规范化
- 无效行过滤
- 标点符号规范化
- 古籍特有格式处理（如双行夹注、篇首标记等）

典型用法:
    >>> cleaner = AncientTextCleaner()
    >>> cleaned = cleaner.clean("□太史公曰◇：余读《离骚》")
    >>> print(cleaned)
    太史公曰：余读《离骚》
"""

import re
import unicodedata
from typing import Optional

from loguru import logger


class AncientTextCleaner:
    """古籍OCR后处理与文本清洗器。

    该类对古籍OCR识别后的原始文本进行多步骤清洗处理，
    去除噪声、规范化格式，为后续NLP处理提供高质量输入。

    Attributes:
        noise_chars: 需要去除的噪声字符集合
        conversion_mode: 繁简转换模式 ('t2s', 's2t', 'none')
        merge_whitespace: 是否合并连续空白为单个空格
        strip_lines: 是否去除行首行尾空白
        min_line_length: 最小有效行长度
        punctuation_map: 标点符号规范化映射表
    """

    # 古籍OCR常见噪声字符（默认）
    DEFAULT_NOISE_CHARS = "□◇◆☆★○●◎△▲▽▼※〓§№■▪▫"

    # 全角标点到半角标点的映射（部分常用）
    PUNCTUATION_MAP = {
        "，": "，",
        "。": "。",
        "；": "；",
        "：": "：",
        "？": "？",
        "！": "！",
        "（": "（",
        "）": "）",
        "《": "《",
        "》": "》",
        """: "“",
        """: "”",
        "'": "‘",
        "'": "’",
        "——": "——",
        "…": "……",
    }

    # 古籍特有标记模式（篇首、卷次等）
    VOLUME_PATTERN = re.compile(
        r"^[卷第][一二三四五六七八九十百千万零\d]+"
    )

    # 双行夹注标记
    ANNOTATION_PATTERN = re.compile(r"〔[^〕]*〕")

    def __init__(
        self,
        noise_chars: Optional[str] = None,
        conversion_mode: str = "t2s",
        merge_whitespace: bool = True,
        strip_lines: bool = True,
        min_line_length: int = 2,
    ):
        """初始化古籍文本清洗器。

        Args:
            noise_chars: 需要去除的噪声字符，默认使用 DEFAULT_NOISE_CHARS
            conversion_mode: 繁简转换模式，可选 't2s'(繁转简), 's2t'(简转繁), 'none'(不转换)
            merge_whitespace: 是否合并连续空白字符为单个空格
            strip_lines: 是否去除每行首尾的空白字符
            min_line_length: 有效行的最小字符数，低于此值的行将被过滤
        """
        self.noise_chars = set(noise_chars or self.DEFAULT_NOISE_CHARS)
        self.conversion_mode = conversion_mode
        self.merge_whitespace = merge_whitespace
        self.strip_lines = strip_lines
        self.min_line_length = min_line_length

        # 延迟加载繁简转换器
        self._converter = None

        logger.info(
            f"古籍文本清洗器初始化完成 | 转换模式: {conversion_mode} | "
            f"噪声字符数: {len(self.noise_chars)} | 最小行长度: {min_line_length}"
        )

    def _get_converter(self):
        """延迟加载繁简转换器。

        使用 opencc-python-reimplemented 包进行繁简转换，
        若未安装则回退到简单映射方式。

        Returns:
            转换器对象，或 None（如果不可用）
        """
        if self._converter is not None:
            return self._converter

        if self.conversion_mode == "none":
            self._converter = None
            return None

        try:
            from opencc import OpenCC

            cc = OpenCC()
            if self.conversion_mode == "t2s":
                cc.set_conversion("t2s")
            elif self.conversion_mode == "s2t":
                cc.set_conversion("s2t")
            self._converter = cc
            logger.info(f"繁简转换器加载成功，模式: {self.conversion_mode}")
        except ImportError:
            logger.warning(
                "opencc 未安装，繁简转换功能不可用。"
                "可通过 pip install opencc-python-reimplemented 安装。"
            )
            self._converter = None

        return self._converter

    def remove_noise_chars(self, text: str) -> str:
        """去除文本中的噪声字符。

        移除OCR识别过程中产生的各种标记符号和乱码字符，
        如方框、星号、菱形等无法识别的占位符。

        Args:
            text: 输入文本

        Returns:
            去除噪声字符后的文本

        Example:
            >>> cleaner = AncientTextCleaner()
            >>> cleaner.remove_noise_chars("□太史公曰◇")
            '太史公曰'
        """
        result = "".join(ch for ch in text if ch not in self.noise_chars)
        if len(result) < len(text):
            removed_count = len(text) - len(result)
            logger.debug(f"去除噪声字符 {removed_count} 个")
        return result

    def normalize_whitespace(self, text: str) -> str:
        """规范化空白字符。

        将连续的空白字符（空格、制表符等）合并为单个空格，
        并根据配置决定是否保留行首行尾空白。

        Args:
            text: 输入文本

        Returns:
            规范化空白后的文本
        """
        if self.merge_whitespace:
            # 合并连续空白为单个空格
            text = re.sub(r"[ 	]+", " ", text)

        if self.strip_lines:
            # 逐行去除首尾空白
            lines = text.split("\n")
            lines = [line.strip() for line in lines]
            text = "\n".join(lines)

        # 去除连续空行（保留段落分隔）
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text

    def normalize_punctuation(self, text: str) -> str:
        """规范化标点符号。

        将OCR识别中常见的标点符号错误进行修正，
        统一标点符号格式。

        Args:
            text: 输入文本

        Returns:
            标点规范化后的文本
        """
        # 修复常见OCR标点错误
        # 多个连续句号合并为省略号
        text = re.sub(r"\.{3,}", "……", text)
        # 多个连续逗号合并为一个
        text = re.sub(r"，{2,}", "，", text)
        # 修复引号配对
        text = re.sub(r"""[""]""", "“", text, count=0)

        return text

    def convert_simplified_traditional(self, text: str) -> str:
        """繁简体中文转换。

        根据配置的转换模式，将文本在繁体和简体中文之间转换。
        古籍原文通常为繁体，可根据需要转换为简体以便后续处理。

        Args:
            text: 输入文本

        Returns:
            转换后的文本
        """
        converter = self._get_converter()
        if converter is None:
            return text

        try:
            return converter.convert(text)
        except Exception as e:
            logger.warning(f"繁简转换失败: {e}，返回原文")
            return text

    def remove_annotations(self, text: str) -> str:
        """去除双行夹注等注释内容。

        古籍中常见双行夹注、眉批等注释，使用特定符号标记。
        本方法去除这些注释内容，仅保留正文。

        Args:
            text: 输入文本

        Returns:
            去除注释后的文本
        """
        # 去除〔〕夹注
        text = self.ANNOTATION_PATTERN.sub("", text)
        # 去除（）内的注音或注释（可选，保留配置）
        # text = re.sub(r"（[^）]*）", "", text)
        return text

    def filter_invalid_lines(self, text: str) -> str:
        """过滤无效行。

        去除长度低于阈值或仅包含空白/标点的行，
        这些行通常是OCR识别错误或页眉页脚等无关内容。

        Args:
            text: 输入文本

        Returns:
            过滤后的文本
        """
        lines = text.split("\n")
        valid_lines = []

        for line in lines:
            stripped = line.strip()
            # 检查行长度
            if len(stripped) < self.min_line_length:
                continue
            # 检查是否仅包含标点和空白
            if re.match(r"^[\s\W]+$", stripped):
                continue
            valid_lines.append(line)

        filtered_count = len(lines) - len(valid_lines)
        if filtered_count > 0:
            logger.debug(f"过滤无效行 {filtered_count} 行")

        return "\n".join(valid_lines)

    def normalize_unicode(self, text: str) -> str:
        """Unicode规范化。

        将文本中的Unicode字符统一为NFC形式，
        处理全角/半角字符等不一致问题。

        Args:
            text: 输入文本

        Returns:
            Unicode规范化后的文本
        """
        # NFC规范化
        text = unicodedata.normalize("NFC", text)

        # 全角数字转半角（古籍OCR常见问题）
        result = []
        for ch in text:
            if "０" <= ch <= "９":  # 全角数字 ０-９
                result.append(chr(ord(ch) - 0xFEE0))
            elif ch == "　":  # 全角空格
                result.append(" ")
            else:
                result.append(ch)

        return "".join(result)

    def clean(self, text: str) -> str:
        """执行完整的文本清洗流水线。

        按照以下顺序依次执行各清洗步骤：
        1. Unicode规范化
        2. 噪声字符去除
        3. 注释内容去除
        4. 标点符号规范化
        5. 繁简转换
        6. 空白字符规范化
        7. 无效行过滤

        Args:
            text: 输入的原始OCR文本

        Returns:
            清洗后的文本

        Example:
            >>> cleaner = AncientTextCleaner(conversion_mode="none")
            >>> raw = "□太史公曰◇：余读《离骚》  "
            >>> cleaner.clean(raw)
            '太史公曰：余读《离骚》'
        """
        logger.info(f"开始文本清洗，原始长度: {len(text)} 字符")

        # Step 1: Unicode规范化
        text = self.normalize_unicode(text)

        # Step 2: 噪声字符去除
        text = self.remove_noise_chars(text)

        # Step 3: 注释内容去除
        text = self.remove_annotations(text)

        # Step 4: 标点符号规范化
        text = self.normalize_punctuation(text)

        # Step 5: 繁简转换
        text = self.convert_simplified_traditional(text)

        # Step 6: 空白字符规范化
        text = self.normalize_whitespace(text)

        # Step 7: 无效行过滤
        text = self.filter_invalid_lines(text)

        logger.info(f"文本清洗完成，清洗后长度: {len(text)} 字符")
        return text

    def clean_file(self, input_path: str, output_path: Optional[str] = None) -> str:
        """清洗文本文件。

        读取指定路径的文本文件，执行完整清洗流水线，
        并将结果写入输出文件。

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径，若为None则在输入路径后添加 '_cleaned' 后缀

        Returns:
            输出文件路径
        """
        if output_path is None:
            base, ext = input_path.rsplit(".", 1) if "." in input_path else (input_path, "txt")
            output_path = f"{base}_cleaned.{ext}" if "." in input_path else f"{base}_cleaned.txt"

        logger.info(f"读取文件: {input_path}")
        with open(input_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        cleaned_text = self.clean(raw_text)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(cleaned_text)

        logger.info(f"清洗结果已写入: {output_path}")
        return output_path
