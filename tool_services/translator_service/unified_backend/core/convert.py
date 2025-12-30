
import os
from typing import List, Dict, Any

from .parser import PDFParser
from .layout import LayoutBuilder
from .engine import PDFEngine
from .renderer import MarkdownRenderer
from .math_detector import MathDetector

from app.services.translation_service import translate_text  # 你自己的翻译服务


class PDFConverter:
    """
    PDF 全流程翻译 orchestrator：
    1. PDF → raw blocks（parser）
    2. blocks → layout（layout builder）
    3. 数学公式检测（math_detector）
    4. 文本翻译（translation_service）
    5. markdown 渲染（renderer）
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.parser = PDFParser(pdf_path)
        self.layout_builder = LayoutBuilder()
        self.math_detector = MathDetector()
        self.engine = PDFEngine()
        self.renderer = MarkdownRenderer()

    # --------------------------------------------------------
    # 主流程入口
    # --------------------------------------------------------
    def convert(self) -> Dict[str, Any]:
        """
        全流程执行入口：
        返回 dict:
        {
            "markdown": "...",
            "pages": [...]
        }
        """

        # ==================================================
        # 1. 解析 PDF → blocks
        # ==================================================
        pages_blocks = self.parser.parse_pdf()
        # pages_blocks: List[List[Block]]

        # ==================================================
        # 2. blocks → layout（主要是文本行合并、段落切分）
        # ==================================================
        pages_layout = []
        for page_index, blocks in enumerate(pages_blocks):
            layout = self.layout_builder.build_layout(blocks)
            pages_layout.append(layout)

        # ==================================================
        # 3. 数学公式检测标记（返回公式区域）
        # ==================================================
        for layout in pages_layout:
            self.math_detector.detect_in_layout(layout)

        # ==================================================
        # 4. 翻译（调用你自己的文本翻译服务）
        # ==================================================
        for layout in pages_layout:
            self._translate_layout_text(layout)

        # ==================================================
        # 5. 渲染为 Markdown
        # ==================================================
        markdown = self.renderer.render_document(pages_layout)

        return {
            "markdown": markdown,
            "pages": pages_layout
        }

    # --------------------------------------------------------
    # 文本翻译（保护 latex 公式）
    # --------------------------------------------------------
    def _translate_layout_text(self, layout):
        """
        给每个 layout 中的 block 进行文本翻译。
        数学公式类型的 block 不翻译。
        """
        for block in layout.blocks:
            if block.is_math:  # 数学公式不翻译
                continue
            if not block.text.strip():
                continue

            try:
                translated = translate_text(block.text)
                block.text = translated
            except Exception as e:
                print("[翻译失败]", e)
                # 保留原文
                continue
