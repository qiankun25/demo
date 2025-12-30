# core/layout.py
from typing import List, Tuple, Union
import re
from .blocks import (
    Span, Line, TextBlock, ImageBlock, MathBlock, FormulaBlock, PlaceholderBlock, Page, gen_id
)

# =====================================================
# 公式检测规则（来自 PDFMathTranslate）
# =====================================================

# 检测 inline math 的典型正则（LaTeX）
INLINE_MATH_PATTERNS = [
    r"\$[^$]+\$",      # $ ... $
    r"\\\([^\\]+\\\)", # \( ... \)
    r"\\\[[^\\]+\\\]", # \[ ... \]
]

# display math 检测：由较大字体或单独行组成

# =====================================================
# 工具函数
# =====================================================

def text_from_line(line: Line) -> str:
    """从Line对象提取文本字符串"""
    return "".join([s.text for s in line.spans])

def detect_inline_math(text: str) -> List[Tuple[int, int, str]]:
    """
    返回 inline math 在字符串中的 span 列表:
    [(start, end, expr), ...]
    """
    matches = []
    for pat in INLINE_MATH_PATTERNS:
        for m in re.finditer(pat, text):
            matches.append((m.start(), m.end(), m.group()))
    matches.sort(key=lambda x: x[0])
    return matches

def detect_display_math(line: Line) -> bool:
    """
    display 公式检测规则（PDFMathTranslate 概念重构版）
    如果一行内只有一个 span 且字体较大 或 内容包含典型公式字符。
    """
    if len(line.spans) == 1:
        s = line.spans[0]
        txt = s.text.strip()
        if any(sym in txt for sym in ["=", "\\frac", "\\int", "\\sum", "\\begin", "\\alpha", "\\beta"]):
            if s.size >= 10:  # 显著大于普通文本
                return True
    return False

# =====================================================
# 公式替换（文字 → MathBlock）
# =====================================================

def convert_line_to_blocks(line: Line) -> List[Union[TextBlock, MathBlock]]:
    """
    将包含 inline 公式的 line 分割成：
    - TextBlock
    - MathBlock
    """
    text = text_from_line(line)
    matches = detect_inline_math(text)

    if not matches:
        return [TextBlock(
            id=gen_id("TXT"),
            lines=[line],
            bbox=line.bbox,
            page_num=line.page_num
        )]

    blocks = []
    last = 0

    for (start, end, expr) in matches:
        # 前置文本
        if start > last:
            blocks.append(
                TextBlock(
                    id=gen_id("TXT"),
                    lines=[Line(
                        spans=[Span(
                            text=text[last:start],
                            font=line.spans[0].font,
                            size=line.spans[0].size,
                            color=line.spans[0].color,
                            bbox=line.spans[0].bbox,
                            page_num=line.page_num
                        )],
                        bbox=line.bbox,
                        page_num=line.page_num
                    )],
                    bbox=line.bbox,
                    page_num=line.page_num
                )
            )

        # 公式
        blocks.append(
            MathBlock(
                id=gen_id("MATH"),
                latex=expr,
                display=False,
                bbox=line.bbox,
                page_num=line.page_num
            )
        )

        last = end

    # 收尾文字
    if last < len(text):
        blocks.append(
            TextBlock(
                id=gen_id("TXT"),
                lines=[Line(
                    spans=[Span(
                        text=text[last:],
                        font=line.spans[0].font,
                        size=line.spans[0].size,
                        color=line.spans[0].color,
                        bbox=line.spans[0].bbox,
                        page_num=line.page_num
                    )],
                    bbox=line.bbox,
                    page_num=line.page_num
                )],
                bbox=line.bbox,
                page_num=line.page_num
            )
        )

    return blocks

# =====================================================
# Layout Analyzer 类
# =====================================================

class LayoutAnalyzer:
    """
    对 parser 提取的 Page 结构进行布局分析：
    1. 文本 block 展开为行
    2. 行级公式检测（inline + display）
    3. 图片按 bbox 排序
    4. 合并为统一 Block 列表
    """

    def process_page(self, page: Page) -> Page:
        layout_blocks = []

        for b in page.blocks:
            if isinstance(b, TextBlock):
                for line in b.lines:
                    line_text = text_from_line(line).strip()

                    # display 公式
                    if detect_display_math(line):
                        layout_blocks.append(
                            MathBlock(
                                id=gen_id("MATH"),
                                latex=line_text,
                                display=True,
                                bbox=b.bbox,
                                page_num=page.number
                            )
                        )
                        continue

                    # inline 公式处理
                    sub_blocks = convert_line_to_blocks(line)
                    for sb in sub_blocks:
                        layout_blocks.append(sb)

            elif isinstance(b, ImageBlock):
                layout_blocks.append(b)

        # 按位置排序（top-down + left-right）
        layout_blocks.sort(key=lambda bl: (bl.bbox[1], bl.bbox[0]))

        # 生成新 Page
        return Page(
            number=page.number,
            width=page.width,
            height=page.height,
            blocks=layout_blocks
        )

    def process_document(self, pages: List[Page]) -> List[Page]:
        return [self.process_page(p) for p in pages]
