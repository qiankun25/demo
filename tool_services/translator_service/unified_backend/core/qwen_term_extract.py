from dashscope import Generation
from ..config import settings


def extract_terms(text: str, lang: str = "en") -> list[str]:
    """
    使用 Qwen 抽取术语
    """

    prompt = f"""
你是一个学术术语抽取助手。
请从以下 {lang} 学术文本中抽取关键术语。

要求：
1. 只返回术语列表
2. 每个术语一行
3. 不要解释
4. 不要编号

文本：
{text}
"""

    response = Generation.call(
        model="qwen-plus",
        api_key=settings.DASHSCOPE_API_KEY,
        prompt=prompt,
        result_format="message",
        temperature=0.1,
        max_tokens=1024,
    )

    if response.status_code != 200:
        raise RuntimeError(response.message)

    content = response.output.choices[0].message.content
    if isinstance(content, list):
        content = content[0]["text"]

    terms = [
        line.strip()
        for line in content.split("\n")
        if line.strip()
    ]

    # 简单去重
    return list(dict.fromkeys(terms))
