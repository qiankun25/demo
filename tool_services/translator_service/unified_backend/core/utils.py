

import os
import re
import math
from typing import List, Tuple, Any


# -------------------------------------------------------------
# 坐标 & 几何工具
# -------------------------------------------------------------

def normalize_bbox(bbox: Tuple[float, float, float, float]):
    """确保 bbox 按顺序排列，避免出现 x2 < x1 或 y2 < y1 的情况。"""
    x1, y1, x2, y2 = bbox
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def bbox_area(bbox):
    """计算区域面积"""
    x1, y1, x2, y2 = normalize_bbox(bbox)
    return max(0, x2 - x1) * max(0, y2 - y1)


def bbox_intersection(a, b):
    """计算两个 bbox 的相交区域面积"""
    ax1, ay1, ax2, ay2 = normalize_bbox(a)
    bx1, by1, bx2, by2 = normalize_bbox(b)

    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)

    if x2 <= x1 or y2 <= y1:
        return 0
    return (x2 - x1) * (y2 - y1)


def bbox_overlaps(a, b, threshold=0.1):
    """判断两个 bbox 是否“重叠”"""
    inter = bbox_intersection(a, b)
    if inter == 0:
        return False

    area_a = bbox_area(a)
    area_b = bbox_area(b)

    ratio = inter / min(area_a, area_b)
    return ratio >= threshold


def center_of(bbox):
    """bbox 中心点"""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def distance(a, b):
    """两个点之间的距离"""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


# -------------------------------------------------------------
# 文本工具
# -------------------------------------------------------------

LATEX_INLINE_PATTERN = re.compile(r"\$[^$]+\$")

def clean_text(text: str) -> str:
    """清洗文本内容（去掉多余空格、隐藏字符等）"""
    if text is None:
        return ""
    text = text.replace("\u00A0", " ")   # 不间断空格
    text = re.sub(r"[ \t]+", " ", text)  # 合并空格
    return text.strip()


def is_likely_math(text: str) -> bool:
    """判断文本是否是 inline 数学公式（保留）"""
    if LATEX_INLINE_PATTERN.search(text):
        return True

    # 一些启发式规则
    if any(sym in text for sym in ["\\frac", "\\sum", "\\int", "\\alpha", "\\beta"]):
        return True

    # 带 ^ 或 _ 较多也可能是公式
    if len(re.findall(r"[\^_]", text)) >= 2:
        return True

    return False


# -------------------------------------------------------------
# block 排序、合并
# -------------------------------------------------------------

def sort_blocks(blocks):
    """
    按页面从上到下，从左到右排序。
    """
    return sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))


def is_same_line(a, b, line_threshold=8):
    """
    判断两个 block 是否在同一行。
    """
    _, ay1, _, ay2 = a.bbox
    _, by1, _, by2 = b.bbox

    a_center = (ay1 + ay2) / 2
    b_center = (by1 + by2) / 2

    return abs(a_center - b_center) < line_threshold


def merge_close_blocks(blocks: List[Any], x_threshold=10) -> List[Any]:
    """
    将同一行且 X 距离较近的文本 block 合并为更长的文本。
    用于 layout 构建前的预处理。
    """
    if not blocks:
        return []

    blocks = sort_blocks(blocks)
    merged = []
    current = blocks[0]

    for b in blocks[1:]:
        if is_same_line(current, b) and abs(b.bbox[0] - current.bbox[2]) <= x_threshold:
            # 合并文本
            current.text = clean_text(current.text + " " + b.text)
            # 扩展 bbox
            current.bbox = normalize_bbox((current.bbox[0], current.bbox[1], b.bbox[2], current.bbox[3]))
        else:
            merged.append(current)
            current = b

    merged.append(current)
    return merged


# -------------------------------------------------------------
# 聚类支持（用于数学行识别等）
# -------------------------------------------------------------

def cluster_by_distance(points: List[Tuple[float, float]], threshold=30):
    """
    将点按距离聚类。用于识别引用编号、数学公式区域等。
    """
    if not points:
        return []

    clusters = []
    current = [points[0]]

    for p in points[1:]:
        if distance(p, current[-1]) < threshold:
            current.append(p)
        else:
            clusters.append(current)
            current = [p]

    clusters.append(current)
    return clusters


# -------------------------------------------------------------
# 文件与路径工具
# -------------------------------------------------------------

def ensure_dir(path: str):
    """确保文件夹存在"""
    if not os.path.exists(path):
        os.makedirs(path)


# -------------------------------------------------------------
# Markdown 辅助工具
# -------------------------------------------------------------

def escape_markdown(text: str) -> str:
    """转义 MD 特殊字符"""
    escape_chars = r"\`*_{}[]()#+-.!"
    for c in escape_chars:
        text = text.replace(c, "\\" + c)
    return text
