import fitz
import json
from typing import List, Dict, Any, Optional

from .layout import LayoutAnalyzer
from .math_detector import MathDetector
from .renderer import MarkdownRenderer


class PDFEngine:
    """
    PDFMathTranslate 主引擎：
    负责 orchestrate 整个 PDF → structured → math → markdown 流程
    """

    def __init__(
        self,
        dpi: int = 300,
        detect_math: bool = True,
        math_min_confidence: float = 0.5,
        extract_images: bool = True,
        image_min_area: int = 4000,
        debug: bool = False
    ):
        self.dpi = dpi
        self.detect_math = detect_math
        self.math_min_conf = math_min_confidence
        self.extract_images = extract_images
        self.image_min_area = image_min_area
        self.debug = debug

        # 子模块
        self.layout_analyzer = LayoutAnalyzer(debug=debug)
        self.math_detector = MathDetector(conf_threshold=math_min_confidence, debug=debug)
        self.renderer = MarkdownRenderer(debug=debug)

    # ------------- 主流程入口 ------------------

    def process_pdf(
        self,
        pdf_path: str,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        return_md: bool = True
    ) -> Dict[str, Any]:
        """
        解析 PDF → 结构化 → 公式检测 → markdown

        返回：
        {
            "markdown": "...",
            "metadata": {...},
            "pages": [...]
        }
        """
        doc = fitz.open(pdf_path)
        total_pages = doc.page_count

        sp = start_page - 1 if start_page else 0
        ep = end_page - 1 if end_page else total_pages - 1

        results = {
            "markdown": "",
            "pages": [],
            "metadata": {
                "total_pages": total_pages,
                "processed_pages": ep - sp + 1,
                "pdf_path": pdf_path
            }
        }

        for i in range(sp, ep + 1):
            page = doc.load_page(i)
            page_result = self.process_single_page(page, page_number=i + 1)
            results["pages"].append(page_result)

        # 统一 Markdown 输出
        if return_md:
            md = self.renderer.combine_pages(results["pages"])
            results["markdown"] = md

        return results

    # ------------- 每页处理 ------------------

    def process_single_page(self, page, page_number: int) -> Dict[str, Any]:
        """
        单页处理：layout → math → render markdown
        """

        # 1. PDF（文本 + OCR + 图片）布局解析
        layout = self.layout_analyzer.analyze_page(page, page_number)

        # layout 结构：
        # {
        #   "text_blocks": [...],
        #   "images": [...],
        #   "lines": [...],
        #   ...
        # }

        # 2. 公式检测（基于 vision 模型）
        if self.detect_math:
            math_regions = self.math_detector.detect_math_regions(page)
        else:
            math_regions = []

        # 3. 公式插入到 layout
        enriched_layout = self.integrate_math(layout, math_regions)

        # 4. 渲染成 markdown 结构
        md_data = self.renderer.render_page(enriched_layout, page_number)

        return {
            "page": page_number,
            "layout": enriched_layout,
            "markdown": md_data
        }

    # ------------- 数学公式融合 ------------------

    def integrate_math(self, layout: Dict[str, Any], math_regions: List[Dict[str, Any]]):
        """
        将 MathDetector 的公式区域融合到文本块中：
        1. 识别公式 bbox 位置
        2. 找到对应文本位置
        3. 使用 $$...$$ 或 `\(...\)` 标记
        """
        if not math_regions:
            return layout

        for region in math_regions:
            bbox = region["bbox"]
            latex = region["latex"]
            block_idx = self.find_block_for_math(layout, bbox)
            if block_idx is not None:
                layout["text_blocks"][block_idx]["content"].append(
                    {
                        "type": "math",
                        "bbox": bbox,
                        "latex": latex
                    }
                )

        return layout

    # ------------- 寻找公式所属文本块 ------------------

    def find_block_for_math(self, layout, bbox):
        """
        遍历 text_blocks 找到与公式 bbox 重叠的块。
        """
        for i, blk in enumerate(layout.get("text_blocks", [])):
            bb = blk.get("bbox")
            if bb and self._intersect(bb, bbox):
                return i
        return None

    @staticmethod
    def _intersect(bb1, bb2):
        """
        判断两个 bbox 是否有重叠
        """
        x1, y1, x2, y2 = bb1
        a1, b1, a2, b2 = bb2
        return not (x2 < a1 or a2 < x1 or y2 < b1 or b2 < y1)


# ---------------- 工具函数 ----------------

def run_pdf_engine(
    pdf_path: str,
    dpi: int = 300,
    detect_math: bool = True,
    return_md: bool = True,
    debug: bool = False
):
    engine = PDFEngine(
        dpi=dpi,
        detect_math=detect_math,
        debug=debug
    )
    return engine.process_pdf(pdf_path, return_md=return_md)
