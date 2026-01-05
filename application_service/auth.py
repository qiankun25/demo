import bcrypt
import hashlib


def _pre_hash_password(password: str) -> bytes:
    """使用 SHA256 预哈希密码，确保输入 bcrypt 的密码不超过 72 字节"""
    # 使用 SHA256 哈希，然后取前 32 字节（而不是 hexdigest）
    # 这样输入 bcrypt 的是 32 字节，远小于 72 字节限制
    return hashlib.sha256(password.encode('utf-8')).digest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        # hashed_password 是字符串格式的 bcrypt hash
        # 先对明文密码进行 SHA256 哈希，然后验证
        pre_hashed = _pre_hash_password(plain_password)
        # bcrypt.checkpw 需要 bytes 类型的密码和 hash
        return bcrypt.checkpw(pre_hashed, hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    # 先对密码进行 SHA256 哈希，然后使用 bcrypt 哈希结果
    # SHA256 digest 是固定的 32 字节，远小于 bcrypt 的 72 字节限制
    pre_hashed = _pre_hash_password(password)
    # 生成 bcrypt hash，使用默认的轮数（12）
    hashed = bcrypt.hashpw(pre_hashed, bcrypt.gensalt())
    return hashed.decode('utf-8')

