from .qwen_term_extract import extract_terms
from .baidu_term_calibrate import calibrate_term


def extract_and_calibrate_terms(text: str) -> list[dict]:
    """
    返回结构化术语表
    """

    terms = extract_terms(text)

    results = []
    for term in terms:
        try:
            zh = calibrate_term(term)
        except Exception:
            zh = ""

        results.append({
            "source": term,
            "target": zh,
        })

    return results
