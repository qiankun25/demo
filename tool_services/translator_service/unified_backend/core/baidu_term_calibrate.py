import hashlib
import random
import requests
from ..config import settings


def _sign(appid, q, salt, secret):
    raw = f"{appid}{q}{salt}{secret}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def calibrate_term(term: str, from_lang="en", to_lang="zh") -> str:
    salt = random.randint(32768, 65536)
    sign = _sign(settings.BAIDU_APP_ID, term, salt, settings.BAIDU_SECRET_KEY)

    params = {
        "q": term,
        "from": from_lang,
        "to": to_lang,
        "appid": settings.BAIDU_APP_ID,
        "salt": salt,
        "sign": sign,
    }

    resp = requests.get(
        "https://fanyi-api.baidu.com/api/trans/vip/translate",
        params=params,
        timeout=5,
    )
    data = resp.json()

    if "trans_result" not in data:
        raise RuntimeError(data)

    return data["trans_result"][0]["dst"]
