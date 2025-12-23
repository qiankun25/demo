from typing import Any, Dict, List, Optional


def reduce_works(works: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [reduce_work(w) for w in works if isinstance(w, dict)]


def reduce_work(w: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 OpenAlex Work 精简为下游最常用字段：
    - 基本：id/doi/title/year/date/cited_by_count/type
    - open_access：含 oa_status/any_repository_has_fulltext 等（若存在）
    - pdf 候选：best_oa_location / locations 的 pdf_url + landing_page_url
    - authors：display_name 列表（用于展示/调试）
    """
    out: Dict[str, Any] = {
        "id": w.get("id"),
        "doi": w.get("doi"),
        "title": w.get("display_name") or w.get("title"),
        "publication_year": w.get("publication_year"),
        "publication_date": w.get("publication_date"),
        "type": w.get("type"),
        "cited_by_count": w.get("cited_by_count"),
    }

    out["open_access"] = _pick_dict(w.get("open_access"))
    out["best_oa_location"] = _reduce_location(w.get("best_oa_location"))
    out["primary_location"] = _reduce_location(w.get("primary_location"))
    out["locations"] = _reduce_locations(w.get("locations"))
    out["authors"] = _extract_authors(w.get("authorships"))

    # 提取一个最优 pdf_url 便于 downloader 直接使用
    out["pdf_url"] = _first_pdf_url(out)

    # 清理 None
    return {k: v for k, v in out.items() if v is not None}


def _pick_dict(x: Any) -> Optional[Dict[str, Any]]:
    return x if isinstance(x, dict) else None


def _reduce_location(loc: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(loc, dict):
        return None
    # 只保留对下载/展示有用的字段
    keep = {
        "pdf_url": loc.get("pdf_url"),
        "landing_page_url": loc.get("landing_page_url"),
        "is_oa": loc.get("is_oa"),
        "license": loc.get("license"),
        "version": loc.get("version"),
    }
    src = loc.get("source")
    if isinstance(src, dict):
        keep["source"] = {
            "id": src.get("id"),
            "display_name": src.get("display_name"),
            "issn": src.get("issn"),
        }
    return {k: v for k, v in keep.items() if v is not None}


def _reduce_locations(locs: Any) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(locs, list):
        return None
    out = []
    for loc in locs:
        r = _reduce_location(loc)
        if r:
            out.append(r)
    return out


def _extract_authors(authorships: Any) -> Optional[List[str]]:
    if not isinstance(authorships, list):
        return None
    names: List[str] = []
    for a in authorships:
        if not isinstance(a, dict):
            continue
        author = a.get("author")
        if isinstance(author, dict):
            n = str(author.get("display_name") or "").strip()
            if n:
                names.append(n)
    # 去重保持顺序
    seen = set()
    out: List[str] = []
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _first_pdf_url(reduced: Dict[str, Any]) -> Optional[str]:
    # best_oa_location.pdf_url
    bol = reduced.get("best_oa_location")
    if isinstance(bol, dict) and bol.get("pdf_url"):
        return str(bol["pdf_url"])
    # locations[].pdf_url
    locs = reduced.get("locations")
    if isinstance(locs, list):
        for loc in locs:
            if isinstance(loc, dict) and loc.get("pdf_url"):
                return str(loc["pdf_url"])
    # primary_location.pdf_url
    pl = reduced.get("primary_location")
    if isinstance(pl, dict) and pl.get("pdf_url"):
        return str(pl["pdf_url"])
    return None

