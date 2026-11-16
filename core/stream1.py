# File: core/stream.py
"""
Mã dòng (stream cipher) dùng khóa chung Diffie-Hellman để mã hóa văn bản và tệp.

Cấu trúc (chỉ dùng SHA-256 tự cài đặt `custom_sha256_bytes` trong core/dh.py,
KHÔNG dùng thư viện băm có sẵn của Python):

  1. Rút khóa : dk = SHA256("DH-STREAM-KDF-v1|" || bytes(K))      (K là khóa chung DH, số nguyên)
  2. Luồng khóa: block_i = SHA256(dk || nonce || i)  với i = 0, 1, 2, ... (i là số 8 byte, big-endian)
                 keystream = block_0 || block_1 || ...           (mỗi khối 32 byte)
  3. Mã hóa   : ciphertext = plaintext XOR keystream (giải mã cũng là phép XOR đó)

Với văn bản, `encrypt_text_hex` sinh nonce 8 byte ngẫu nhiên cho mỗi lần mã hóa và đặt nó ở đầu
chuỗi Hex, nên cùng một bản rõ và cùng một khóa vẫn cho bản mã khác nhau.

LƯU Ý (mức độ bài tập lớn): đây là mã minh họa. Nó KHÔNG có xác thực toàn vẹn (kẻ tấn công lật bit
bản mã thì lật đúng bit tương ứng của bản rõ) và dùng lại cùng (khóa, nonce) cho hai bản rõ sẽ lộ
phép XOR của chúng. Trong thực tế hãy dùng AES-GCM hoặc ChaCha20-Poly1305.
"""

import secrets

from core.dh import custom_sha256_bytes

TIEN_TO_KDF = b"DH-STREAM-KDF-v1|"
KICH_THUOC_KHOI = 32      # SHA-256 cho ra 32 byte mỗi lần gọi
KICH_THUOC_NONCE = 8      # byte


def _khoa_sang_bytes(key) -> bytes:
    """Đổi khóa chung (số nguyên không âm, hoặc bytes) sang bytes."""
    if isinstance(key, bool):
        raise TypeError("Khóa phải là số nguyên hoặc bytes, không phải bool.")
    if isinstance(key, int):
        if key < 0:
            raise ValueError("Khóa phải là số nguyên không âm.")
        return key.to_bytes(max(1, (key.bit_length() + 7) // 8), "big")
    if isinstance(key, (bytes, bytearray)):
        return bytes(key)
    raise TypeError("Khóa phải là số nguyên hoặc bytes.")


def derive_key(key) -> bytes:
    """Bước 1: rút khóa 32 byte từ khóa chung DH."""
    return custom_sha256_bytes(TIEN_TO_KDF + _khoa_sang_bytes(key))


def keystream(key, length: int, nonce: bytes = b"") -> bytes:
    """Bước 2: sinh `length` byte luồng khóa từ (khóa, nonce) bằng SHA-256 ở chế độ đếm."""
    if length < 0:
        raise ValueError("length phải >= 0.")
    dk = derive_key(key)
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += custom_sha256_bytes(dk + nonce + counter.to_bytes(8, "big"))
        counter += 1
    return bytes(out[:length])


def keystream_xor(data: bytes, key, nonce: bytes = b"") -> bytes:
    """Bước 3: XOR dữ liệu với luồng khóa. Gọi lại với cùng (key, nonce) sẽ giải mã."""
    if not data:
        return b""
    ks = keystream(key, len(data), nonce)
    x = int.from_bytes(data, "big") ^ int.from_bytes(ks, "big")
    return x.to_bytes(len(data), "big")


def encrypt_text_hex(text: str, key) -> str:
    """Mã hóa chuỗi (UTF-8, hỗ trợ tiếng Việt có dấu). Trả về Hex = nonce (8 byte) || bản mã."""
    nonce = secrets.token_bytes(KICH_THUOC_NONCE)
    cipher = keystream_xor(text.encode("utf-8"), key, nonce)
    return (nonce + cipher).hex()


def decrypt_text_hex(hex_text: str, key) -> str:
    """Giải mã chuỗi Hex tạo bởi encrypt_text_hex.
    Khóa sai sẽ ra chuỗi vô nghĩa (ký tự lỗi được thay bằng U+FFFD), không văng lỗi giải mã UTF-8."""
    raw = bytes.fromhex(hex_text)          # Hex sai định dạng -> ValueError
    if len(raw) < KICH_THUOC_NONCE:
        raise ValueError("Chuỗi Hex quá ngắn: thiếu nonce 8 byte ở đầu.")
    nonce, cipher = raw[:KICH_THUOC_NONCE], raw[KICH_THUOC_NONCE:]
    return keystream_xor(cipher, key, nonce).decode("utf-8", errors="replace")
