# core/pipeline.py
from .blocks import TextBlock, ImageBlock, FormulaBlock, MathBlock, Page
from .text_translate import translate_text
from typing import List, Dict, Any, Union
import os
import re
import tempfile
from pathlib import Path

def translate_pdf_to_markdown(pdf_path: str, source_lang: str = "en", target_lang: str = "zh") -> str:
    """
    将PDF文件翻译为Markdown格式，保留公式和图片结构
    
    参数:
    pdf_path: PDF文件路径
    source_lang: 源语言代码，默认为"en"
    target_lang: 目标语言代码，默认为"zh"
    
    返回:
    Markdown格式的翻译结果字符串
    """
    # 步骤1: 解析PDF并获取所有页面块
    pages = parse_pdf_to_pages(pdf_path)
    
    markdown_lines = []
    
    for page in pages:
        for block in page.blocks:
            if isinstance(block, TextBlock):
                # 翻译文本块
                original_text = block.to_text()
                if original_text.strip():  # 只翻译非空文本
                    translated_text = translate_text(original_text, source_lang, target_lang)
                    block.translated_text = translated_text
                    markdown_lines.append(translated_text)
                
            elif isinstance(block, (FormulaBlock, MathBlock)):
                # 公式块，用LaTeX格式表示
                formula_md = f"$$\n{block.latex}\n$$" if block.display else f"${block.latex}$"
                markdown_lines.append(formula_md)
                
            elif isinstance(block, ImageBlock):
                # 图片块，保存图片并生成Markdown图片格式
                image_path = save_image_to_file(block.img_bytes, block.page_num)
                image_md = f"![Image on page {block.page_num}]({image_path})"
                markdown_lines.append(image_md)
    
    return "\n\n".join(markdown_lines)

def parse_pdf_to_pages(pdf_path: str) -> List[Page]:
    """
    解析PDF文件，返回页面列表（每个页面包含块列表）
    
    实际实现使用PyMuPDF库
    """
    from .parser import PDFParser
    
    parser = PDFParser(pdf_path)
    return parser.parse_document()

def save_image_to_file(img_bytes: bytes, page_num: int) -> str:
    """
    将图片字节保存到文件并返回相对路径
    
    参数:
    img_bytes: 图片字节数据
    page_num: 页码
    
    返回:
    图片文件的相对路径
    """
    from ..config import settings
    # 创建临时目录存储图片
    temp_dir = Path(settings.IMAGE_TMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成唯一的图片文件名
    import uuid
    image_filename = f"image_page_{page_num}_{uuid.uuid4().hex[:8]}.png"
    image_path = temp_dir / image_filename
    
    # 保存图片
    with open(image_path, "wb") as f:
        f.write(img_bytes)
    
    # 返回相对路径
    return f"{settings.IMAGE_TMP_DIR}/{image_filename}"
