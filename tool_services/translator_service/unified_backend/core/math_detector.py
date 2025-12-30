import io
import fitz
import json
import numpy as np
from typing import List, Dict, Any, Optional
from PIL import Image, ImageOps


class MathDetector:
    """
    数学公式检测模块：
    - 从 PDF 页面截图
    - 使用 Math OCR 模型检测公式区域
    - 输出 bbox + Latex
    """

    def __init__(
        self,
        model=None,
        conf_threshold: float = 0.5,
        debug: bool = False
    ):
        """
        model: 公式识别 backend（通常为 mfd 或 vision-ocr）
        """
        self.model = model
        self.conf_threshold = conf_threshold
        self.debug = debug

    # ---------------- 主入口 ---------------- #

    def detect_math_regions(self, page) -> List[Dict[str, Any]]:
        """
        检测 PDF 页面中的所有数学公式区域。  
        工作流：
        1. 将页面渲染为图像 (pix)
        2. 调用数学模型检测（比如 MathNet / MathOCR）
        3. 将 pixel 坐标映射回 PDF 坐标
        4. 返回 [{bbox, latex, score}]
        """

        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # high resolution
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # 调用数学 OCR 模型
        response = self.run_math_ocr(img)

        if not response:
            return []

        math_regions = []

        for det in response:
            if det.get("score", 0) < self.conf_threshold:
                continue

            bbox_pix = det["bbox"]  # in pixel coords
            latex = det["latex"]

            bbox_pdf = self.pixel_bbox_to_pdf_bbox(bbox_pix, pix, page)

            math_regions.append({
                "bbox": bbox_pdf,
                "latex": latex,
                "score": det.get("score", 1.0)
            })

        return math_regions

    # ---------------- 模型调用 ---------------- #

    def run_math_ocr(self, img: Image.Image) -> Optional[List[Dict[str, Any]]]:
        """
        调用 external 数学公式识别 API 或本地模型
        返回格式：
        [
            {
                "bbox": [x1,y1,x2,y2],
                "latex": "...",
                "score": float
            }
        ]
        """

        if not self.model:
            print("[MathDetector] 未提供数学公式模型，跳过检测。")
            return []

        try:
            return self.model.predict_math(img)
        except Exception as e:
            print("[MathDetector] 模型调用异常：", e)
            return None

    # ---------------- 坐标转换 ---------------- #

    def pixel_bbox_to_pdf_bbox(self, bbox_pix, pix, page):
        """
        将 pixel 坐标转换成 PDF 页面坐标（fitz 的原始坐标系）
        """
        pw = pix.width
        ph = pix.height

        x1, y1, x2, y2 = bbox_pix

        # 基于渲染缩放反推 PDF 坐标
        # matrix(2,2) → scale = 2
        scale = pix.xres / 72  # 72 dpi 基准
        if scale == 0:
            scale = 2.0

        return [
            x1 / scale,
            y1 / scale,
            x2 / scale,
            y2 / scale
        ]


# -------------------- 便捷函数 --------------------

def run_math_detector(model, page):
    det = MathDetector(model=model)
    return det.detect_math_regions(page)
