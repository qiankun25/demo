# core/parser.py
import fitz  # PyMuPDF
import io
import os
from typing import List, Dict, Any, Union, Optional
from .blocks import (
    Span, Line, TextBlock, ImageBlock, MathBlock, FormulaBlock, PlaceholderBlock, Page, gen_id
)

class PDFParser:
    """PDF 解析器，使用 PyMuPDF 将 PDF 转换为结构化块"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
    
    def parse_document(self) -> List[Page]:
        """解析整个 PDF 文档，返回页面列表"""
        pages = []
        for page_num in range(len(self.doc)):
            page = self.parse_page(page_num)
            pages.append(page)
        return pages
    
    def parse_page(self, page_num: int) -> Page:
        """解析单个页面"""
        page = self.doc[page_num]
        
        # 获取页面尺寸
        rect = page.rect
        width, height = rect.width, rect.height
        
        # 解析文本块
        text_blocks = self.parse_text_blocks(page, page_num)
        
        # 解析图片块
        image_blocks = self.parse_image_blocks(page, page_num)
        
        # 合并所有块
        all_blocks = text_blocks + image_blocks
        
        # 按位置排序
        all_blocks.sort(key=lambda block: (block.bbox[1], block.bbox[0]))
        
        return Page(
            number=page_num,
            width=width,
            height=height,
            blocks=all_blocks
        )
    
    def parse_text_blocks(self, page, page_num: int) -> List[TextBlock]:
        """解析文本块"""
        text_blocks = []
        
        # 获取文本块
        blocks = page.get_text("dict")["blocks"]
        
        for block in blocks:
            if "lines" in block:  # 文本块
                lines = []
                for line in block["lines"]:
                    spans = []
                    for span in line["spans"]:
                        # 创建 Span 对象
                        span_obj = Span(
                            text=span["text"],
                            font=span.get("font", ""),
                            size=span.get("size", 12),
                            color=span.get("color", 0),
                            bbox=span["bbox"],
                            page_num=page_num
                        )
                        spans.append(span_obj)
                    
                    # 创建 Line 对象
                    line_obj = Line(
                        spans=spans,
                        bbox=line["bbox"],
                        page_num=page_num
                    )
                    lines.append(line_obj)
                
                # 创建 TextBlock 对象
                text_block = TextBlock(
                    id=gen_id("TXT"),
                    lines=lines,
                    bbox=block["bbox"],
                    page_num=page_num
                )
                text_blocks.append(text_block)
        
        return text_blocks
    
    def parse_image_blocks(self, page, page_num: int) -> List[ImageBlock]:
        """解析图片块"""
        image_blocks = []
        
        # 获取图片列表
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            # 获取图片引用
            xref = img[0]
            
            # 提取图片数据
            base_image = self.doc.extract_image(xref)
            image_bytes = base_image["image"]
            
            # 获取图片在页面中的位置
            img_rects = page.get_image_rects(xref)
            if img_rects:
                bbox = list(img_rects[0])  # 使用第一个矩形作为位置
                
                # 创建 ImageBlock 对象
                image_block = ImageBlock(
                    id=gen_id("IMG"),
                    img_bytes=image_bytes,
                    bbox=bbox,
                    page_num=page_num
                )
                image_blocks.append(image_block)
        
        return image_blocks
    
    def close(self):
        """关闭 PDF 文档"""
        if self.doc:
            self.doc.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
