# File: app/filecrypt.py
"""
Module mã hóa và giải mã tệp thực tế (văn bản .txt và ảnh .png) bằng khóa chung Diffie-Hellman.
"""

import os
import time
import zlib
import struct
from core.dh import mod_exp
from core.stream import keystream_xor

SAMPLES_DIR = "samples"

def _generate_sample_png(filepath: str, width: int = 120, height: int = 120):
    """Tạo một tệp ảnh PNG màu hợp lệ (~43 KB) lưu vào thư mục samples/."""
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)
        for x in range(width):
            r = (x * 2) % 256
            g = (y * 2) % 256
            b = ((x + y) * 3) % 256
            raw_data.extend([r, g, b])

    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = struct.pack(">I", len(data)) + chunk_type + data
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return chunk + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw_data), level=0)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + make_chunk(b"IHDR", ihdr)
        + make_chunk(b"IDAT", idat)
        + make_chunk(b"IEND", b"")
    )
    with open(filepath, "wb") as f:
        f.write(png_bytes)

def ensure_sample_files():
    """Đảm bảo thư mục samples/ có sẵn tệp văn bản tiếng Việt và tệp ảnh nhỏ."""
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    txt_path = os.path.join(SAMPLES_DIR, "thong_diep.txt")
    png_path = os.path.join(SAMPLES_DIR, "anh_mau.png")

    if not os.path.exists(txt_path):
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(
                "ĐẠI HỌC KINH TẾ QUỐC DÂN (NEU) - BÀI TẬP LỚN AN TOÀN BẢO MẬT THÔNG TIN\n"
                "Chủ đề: Trao đổi khóa Diffie-Hellman, bài toán Logarit rời rạc và tấn công MITM.\n"
                "Kiểm thử mã hóa tệp văn bản tiếng Việt có dấu bằng khóa phiên DH thật.\n"
            )
    if not os.path.exists(png_path):
        _generate_sample_png(png_path)

    return txt_path, png_path

def demo_file(input_path: str, p: int = 18446744073709551557, g: int = 5, a: int = 135792468, b: int = 246813579):
    """
    Hai bên Alice và Bob chạy DH thật bằng mod_exp, lấy khóa chung đưa vào keystream_xor
    để mã hóa tệp, giải mã sang tệp khác và đọc nhị phân đối chiếu.
    """
    # 1. Phiên trao đổi khóa DH thật bằng mod_exp của Dev
    A = mod_exp(g, a, p)
    B = mod_exp(g, b, p)
    K_alice = mod_exp(B, a, p)
    K_bob = mod_exp(A, b, p)
    assert K_alice == K_bob, "Lỗi: Khóa chung DH không trùng khớp!"

    # 2. Đọc tệp gốc ở chế độ nhị phân
    with open(input_path, "rb") as f:
        original_bytes = f.read()

    base, ext = os.path.splitext(input_path)
    enc_path = f"{base}_ma_hoa{ext}.enc"
    dec_path = f"{base}_khoi_phuc{ext}"

    # 3. Mã hóa tệp với khóa của Alice
    t0 = time.perf_counter()
    cipher_bytes = keystream_xor(original_bytes, K_alice)
    t_enc = (time.perf_counter() - t0) * 1000
    with open(enc_path, "wb") as f:
        f.write(cipher_bytes)

    # 4. Giải mã tệp với khóa của Bob
    t1 = time.perf_counter()
    recovered_bytes = keystream_xor(cipher_bytes, K_bob)
    t_dec = (time.perf_counter() - t1) * 1000
    with open(dec_path, "wb") as f:
        f.write(recovered_bytes)

    # 5. Đọc nhị phân hai tệp để so sánh
    with open(input_path, "rb") as f_orig, open(dec_path, "rb") as f_rec:
        matched = (f_orig.read() == f_rec.read())

    print(f"\n  * Tệp đầu vào       : {input_path} ({len(original_bytes)} bytes)")
    print(f"  * Khóa chung DH     : {K_alice}")
    print(f"  * Tệp bản mã đã lưu : {enc_path}")
    print(f"  * Tệp giải mã đã lưu: {dec_path}")
    print(f"  * Thời gian thực thi: Mã hóa = {t_enc:.2f} ms | Giải mã = {t_dec:.2f} ms")
    if matched:
        print("  => Kết quả kiểm tra nhị phân: khôi phục đúng")
    else:
        print("  => Kết quả kiểm tra nhị phân: LỖI (không khớp)")
    return matched

def benchmark_file_encryption():
    """
    Đo thời gian mã hóa theo kích thước tệp (1 KB, 10 KB, 100 KB, 1 MB) và in bảng.
    """
    sizes_kb = [1, 10, 100, 1024]
    shared_key = 9876543210123456789
    print("\n  [BẢNG ĐO THỜI GIAN MÃ HÓA & GIẢI MÃ THEO KÍCH THƯỚC TỆP]")
    print(f"  {'Kích thước':<16} | {'Số Byte':<12} | {'Mã hóa (ms)':<15} | {'Giải mã (ms)':<15}")
    print("  " + "-" * 64)

    for kb in sizes_kb:
        n_bytes = kb * 1024
        data = os.urandom(n_bytes)

        t0 = time.perf_counter()
        enc = keystream_xor(data, shared_key)
        t_enc = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        dec = keystream_xor(enc, shared_key)
        t_dec = (time.perf_counter() - t1) * 1000

        assert dec == data
        label = f"{kb} KB" if kb < 1024 else "1 MB (1024 KB)"
        print(f"  {label:<16} | {n_bytes:<12} | {t_enc:<15.2f} | {t_dec:<15.2f}")