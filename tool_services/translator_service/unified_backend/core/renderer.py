
import base64
from typing import List
from .blocks import (
    TextBlock, MathBlock, ImageBlock, PlaceholderBlock, Page
)

# =====================================================
# 工具函数
# =====================================================

def bbox_to_md(bbox):
    """将标准 bbox 转为可读 text"""
    if not bbox:
        return ""
    return f"[bbox: {bbox[0]:.1f},{bbox[1]:.1f},{bbox[2]:.1f},{bbox[3]:.1f}]"


def image_to_md(image_block: ImageBlock) -> str:
    """
    把 ImageBlock 转为 Markdown
    PDFMathTranslate 原版通常走 base64 内嵌方式
    """
    try:
        with open(image_block.path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"![image](data:image/png;base64,{encoded})\n"
    except:
        # 回退: 使用占位符
        return f"![image-not-found](#)  <!-- {image_block.path} -->\n"


# =====================================================
# Markdown Renderer 类
# =====================================================

class MarkdownRenderer:

    def render_textblock(self, block: TextBlock) -> str:
        md = ""
        for line in block.lines:
            line_txt = "".join([s.text for s in line.spans])
            if line_txt.strip():
                md += line_txt + "\n"
        return md + "\n"

    def render_mathblock(self, block: MathBlock) -> str:
        """
        display: 使用 $$...$$
        inline: 使用 $...$
        """
        latex = block.latex.strip()

        if block.display:
            return f"\n$$\n{latex}\n$$\n\n"
        else:
            return f"${latex}$"

    def render_imageblock(self, block: ImageBlock) -> str:
        return image_to_md(block)

    def render_placeholder(self, block: PlaceholderBlock) -> str:
        """用于保留引擎未处理对象"""
        return f"<!-- placeholder {block.id} -->\n"

    # =====================================================
    # 渲染整页
    # =====================================================
    def render_page(self, page: Page) -> str:
        md = f"\n\n<!-- Page {page.number} -->\n\n"

        for block in page.blocks:
            if isinstance(block, TextBlock):
                md += self.render_textblock(block)
            elif isinstance(block, MathBlock):
                md += self.render_mathblock(block)
            elif isinstance(block, ImageBlock):
                md += self.render_imageblock(block)
            elif isinstance(block, PlaceholderBlock):
                md += self.render_placeholder(block)

        return md

    # =====================================================
    # 渲染完整 PDF 文档
    # =====================================================
    def render_document(self, pages: List[Page]) -> str:
        md = "# PDF Translation Output\n\n"

        for page in pages:
            md += self.render_page(page)

        return md
