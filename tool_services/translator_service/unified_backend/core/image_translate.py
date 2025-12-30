# core/image_translate.py

import hashlib
import random
import requests
from typing import Dict, Any
import logging
from ..config import settings

logger = logging.getLogger(__name__)

# SDK 接口需要的固定参数（来自官方 Demo）
CUID = "APICUID"
MAC = "mac"

def get_file_md5(content: bytes) -> str:
    """计算图片字节内容的 MD5"""
    return hashlib.md5(content).hexdigest()

def translate_image_bytes(content: bytes) -> Dict[str, Any]:
    # 1. 检查图片大小（<= 2MB）
    if len(content) > 2 * 1024 * 1024:
        return {"error_code": 52006, "error_msg": "图片大小超过2MB"}

    # 2. 计算图片的 MD5（用于签名）
    file_md5 = get_file_md5(content)
    
    # 3. 生成随机 salt（官方 Demo 使用 32768-65536 范围）
    salt = str(random.randint(32768, 65536))
    
    # 4. 生成签名（严格按照官方 Demo 顺序！）
    sign_str = settings.BAIDU_APP_ID + file_md5 + salt + CUID + MAC + settings.BAIDU_SECRET_KEY
    sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    # 5. 构建请求参数
    params = {
        'from': 'en',      
        'to': 'zh',        
        'appid': settings.BAIDU_APP_ID,
        'salt': salt,
        'sign': sign,
        'cuid': CUID,
        'mac': MAC
    }

    # 6. 准备文件
    files = {'image': ('image.png', content, 'application/octet-stream')}

    # 7. 发送请求
    url = "https://fanyi-api.baidu.com/api/trans/sdk/picture"
    try:
        response = requests.post(url, params=params, files=files)
        return response.json()
    except Exception as e:
        logger.error(f"请求失败: {e}")
        return {"error_code": -1, "error_msg": str(e)}
