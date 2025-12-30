# app/core/blocks.py
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Union

@dataclass
class Span:
    """表示文本中的一个字符或单词片段"""
    text: str
    font: str
    size: float
    color: str
    bbox: List[float]  # [x0, y0, x1, y1] 表示文本的边界框
    page_num: int

@dataclass
class Line:
    """表示一行文本"""
    spans: List[Span]
    bbox: List[float]  # [x0, y0, x1, y1] 表示整行的边界框
    page_num: int

@dataclass
class TextBlock:
    """表示一个文本块，包含多行文本"""
    id: str
    lines: List[Line]
    bbox: List[float]  # [x0, y0, x1, y1] 表示文本块的边界框
    page_num: int
    translated_text: Optional[str] = None

    def to_text(self) -> str:
        """将文本块转换为纯文本"""
        return "\n".join(["".join([s.text for s in line.spans]) for line in self.lines])

@dataclass
class FormulaBlock:
    """表示一个公式块，包含LaTeX格式的公式"""
    id: str
    latex: str
    bbox: List[float]  # [x0, y0, x1, y1] 表示公式块的边界框
    page_num: int
    display: bool = False  # True表示行间公式，False表示行内公式
    translated_text: Optional[str] = None

@dataclass
class MathBlock:
    """表示一个数学公式块，包含LaTeX格式的公式（与FormulaBlock功能相同，保持命名一致性）"""
    id: str
    latex: str
    bbox: List[float]  # [x0, y0, x1, y1] 表示公式块的边界框
    page_num: int
    display: bool = False  # True表示行间公式，False表示行内公式
    translated_text: Optional[str] = None

@dataclass
class ImageBlock:
    """表示一个图片块"""
    id: str
    img_bytes: bytes
    bbox: List[float]  # [x0, y0, x1, y1] 表示图片块的边界框
    page_num: int
    translated_text: Optional[str] = None

@dataclass
class PlaceholderBlock:
    """表示一个占位符，用于在Markdown中表示公式或图片"""
    type: str  # "MATH" 或 "IMAGE"
    page_num: int
    content: str

    def placeholder_token(self) -> str:
        """生成Markdown占位符"""
        if self.type == "MATH":
            return f"[[MATH:{self.content}]]"
        elif self.type == "IMAGE":
            return f"[[IMAGE:{self.content}]]"
        return f"[[{self.type}:{self.content}]]"

@dataclass
class Page:
    """表示一个PDF页面"""
    number: int
    width: float
    height: float
    blocks: List[Union[TextBlock, FormulaBlock, MathBlock, ImageBlock, PlaceholderBlock]]

def gen_id(prefix: str) -> str:
    """生成带前缀的唯一ID"""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}"