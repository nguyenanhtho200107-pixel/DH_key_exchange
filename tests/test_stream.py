"""
Kiểm thử core/stream.py : mã dòng dùng SHA-256 tự viết ở chế độ đếm.

Cấu trúc đang kiểm thử:
    dk        = SHA256("DH-STREAM-KDF-v1|" || bytes(K))
    block_i   = SHA256(dk || nonce || i)   (i là số 8 byte big-endian, mỗi khối 32 byte)
    cipher    = plain XOR keystream
    văn bản   : hex = nonce(8 byte) || cipher
Quy ước: hashlib chỉ dùng trong tests/ để đối chiếu.
"""
import hashlib
import os

import pytest

from core import dh, stream


def luong_khoa_tham_chieu(khoa_bytes: bytes, do_dai: int, nonce: bytes = b"") -> bytes:
    """Cài đặt độc lập bằng hashlib để đối chiếu với core/stream.py."""
    dk = hashlib.sha256(b"DH-STREAM-KDF-v1|" + khoa_bytes).digest()
    out = b""
    i = 0
    while len(out) < do_dai:
        out += hashlib.sha256(dk + nonce + i.to_bytes(8, "big")).digest()
        i += 1
    return out[:do_dai]


def int_sang_bytes(k: int) -> bytes:
    return k.to_bytes(max(1, (k.bit_length() + 7) // 8), "big")


# ---------------------------------------------------------------- 1. RÚT KHOÁ VÀ LUỒNG KHOÁ
class TestLuongKhoa:
    @pytest.mark.parametrize("do_dai", [0, 1, 31, 32, 33, 64, 100, 1000])
    def test_khop_hashlib_tham_chieu(self, do_dai):
        for khoa in (1, 2, 123456789, 2**64 + 7):
            assert stream.keystream(khoa, do_dai) == luong_khoa_tham_chieu(int_sang_bytes(khoa), do_dai)

    def test_khop_hashlib_co_nonce(self):
        nonce = bytes(range(8))
        assert stream.keystream(99, 100, nonce) == luong_khoa_tham_chieu(int_sang_bytes(99), 100, nonce)

    def test_derive_key_khop_hashlib(self):
        assert stream.derive_key(123456789) == hashlib.sha256(b"DH-STREAM-KDF-v1|" + int_sang_bytes(123456789)).digest()

    def test_hang_so(self):
        assert stream.TIEN_TO_KDF == b"DH-STREAM-KDF-v1|"
        assert stream.KICH_THUOC_KHOI == 32
        assert stream.KICH_THUOC_NONCE == 8

    def test_vector_co_dinh(self):
        # vector đã đối chiếu với hashlib; đổi thuật toán sẽ làm test này đỏ
        assert stream.keystream(2, 8).hex() == "e765bb89de52f4f8"
        assert stream.keystream_xor(b"abc", 2).hex() == "8607d8"

    def test_xac_dinh(self):
        assert stream.keystream(99, 100) == stream.keystream(99, 100)

    def test_tien_to(self):
        assert stream.keystream(5, 100)[:40] == stream.keystream(5, 40)

    def test_khoa_hoac_nonce_khac_cho_luong_khac(self):
        assert stream.keystream(1, 32) != stream.keystream(2, 32)
        assert stream.keystream(1, 32, b"a") != stream.keystream(1, 32, b"b")
        assert stream.keystream(1, 32, b"") != stream.keystream(1, 32, b"\x00")

    def test_do_dai_am(self):
        with pytest.raises(ValueError):
            stream.keystream(1, -1)

    def test_tinh_chat_thong_ke(self):
        # luồng khoá gần như đều: trung bình byte ~127,5 và mỗi giá trị byte xuất hiện
        ks = stream.keystream(2026, 32768)
        tb = sum(ks) / len(ks)
        assert 126.5 < tb < 128.5
        assert len(set(ks)) == 256

    def test_hieu_ung_tuyet_lo(self):
        # đổi khoá 1 đơn vị thì khoảng một nửa số bit của luồng khoá thay đổi
        a, b = stream.keystream(1000, 1000), stream.keystream(1001, 1000)
        bit_khac = sum(bin(x ^ y).count("1") for x, y in zip(a, b))
        ti_le = bit_khac / (8 * 1000)
        assert 0.47 < ti_le < 0.53


# ---------------------------------------------------------------- 2. KHOÁ ĐẦU VÀO
class TestLoaiKhoa:
    def test_khoa_int_va_bytes_tuong_duong(self):
        assert stream.keystream(258, 64) == stream.keystream(b"\x01\x02", 64)
        assert stream.keystream(258, 64) == stream.keystream(bytearray(b"\x01\x02"), 64)

    def test_khoa_bang_khong(self):
        assert stream.keystream(0, 16) == luong_khoa_tham_chieu(b"\x00", 16)

    def test_khoa_2048_bit(self):
        P, G = dh.RFC_3526_2048_P, dh.RFC_3526_2048_G
        a, b = 12345678901234567890, 98765432109876543210
        K1 = dh.mod_exp(dh.mod_exp(G, b, P), a, P)
        K2 = dh.mod_exp(dh.mod_exp(G, a, P), b, P)
        du_lieu = "khoá chung DH 2048-bit".encode()
        assert stream.keystream_xor(stream.keystream_xor(du_lieu, K1), K2) == du_lieu
        assert stream.keystream(K1, 64) == luong_khoa_tham_chieu(int_sang_bytes(K1), 64)

    def test_khoa_am(self):
        with pytest.raises(ValueError):
            stream.keystream_xor(b"abc", -5)

    @pytest.mark.parametrize("sai", [True, False, "khoa", 3.14, None, [1, 2]])
    def test_khoa_sai_kieu(self, sai):
        with pytest.raises(TypeError):
            stream.keystream_xor(b"abc", sai)


# ---------------------------------------------------------------- 3. keystream_xor
class TestKeystreamXor:
    @pytest.mark.parametrize("n", [0, 1, 7, 8, 31, 32, 33, 64, 255, 1000, 5000])
    def test_khu_hoi(self, n):
        du_lieu = os.urandom(n)
        ma = stream.keystream_xor(du_lieu, 424242)
        assert len(ma) == n
        assert stream.keystream_xor(ma, 424242) == du_lieu

    def test_rong(self):
        assert stream.keystream_xor(b"", 7) == b""

    def test_khop_xor_voi_luong_khoa_tham_chieu(self):
        du_lieu = os.urandom(777)
        ks = luong_khoa_tham_chieu(int_sang_bytes(31337), 777)
        assert stream.keystream_xor(du_lieu, 31337) == bytes(x ^ y for x, y in zip(du_lieu, ks))

    def test_ban_ma_khac_ban_ro(self):
        assert stream.keystream_xor(bytes(100), 5) != bytes(100)

    def test_khoa_sai_khong_giai_ma_duoc(self):
        ban_ro = b"Chuyen 5,000,000 VND cho Bob"
        ma = stream.keystream_xor(ban_ro, 6)
        assert stream.keystream_xor(ma, 5) != ban_ro

    def test_nonce_sai_khong_giai_ma_duoc(self):
        ban_ro = b"du lieu bi mat"
        ma = stream.keystream_xor(ban_ro, 6, b"nonce_01")
        assert stream.keystream_xor(ma, 6, b"nonce_02") != ban_ro
        assert stream.keystream_xor(ma, 6, b"nonce_01") == ban_ro

    def test_du_lieu_nhi_phan_day_du(self):
        du_lieu = bytes(range(256)) * 4
        assert stream.keystream_xor(stream.keystream_xor(du_lieu, 77), 77) == du_lieu

    def test_tuyen_tinh_xor(self):
        # E(a) xor E(b) = a xor b khi dùng cùng (khoá, nonce): đặc tính của mã dòng (lý do không được tái dùng nonce)
        a, b = os.urandom(200), os.urandom(200)
        ea, eb = stream.keystream_xor(a, 9), stream.keystream_xor(b, 9)
        assert bytes(x ^ y for x, y in zip(ea, eb)) == bytes(x ^ y for x, y in zip(a, b))

    def test_khong_toan_ven(self):
        # mã không có xác thực: lật bit bản mã thì lật đúng bit tương ứng của bản rõ (tài liệu hoá hạn chế đã nêu trong báo cáo)
        ban_ro = b"Chuyen 5,000,000 VND cho Bob"
        ma = bytearray(stream.keystream_xor(ban_ro, 6))
        ma[7] ^= 0x01
        kq = stream.keystream_xor(bytes(ma), 6)
        assert kq != ban_ro and kq[:7] == ban_ro[:7] and kq[8:] == ban_ro[8:]
        assert kq[7] == ban_ro[7] ^ 0x01

    @pytest.mark.cham
    def test_toc_do_100kb(self):
        import time
        du_lieu = os.urandom(100 * 1024)
        t = time.perf_counter()
        stream.keystream_xor(du_lieu, 12345)
        assert time.perf_counter() - t < 20          # mốc rất rộng: thực tế khoảng 0,3 giây


# ---------------------------------------------------------------- 4. VĂN BẢN HEX
class TestVanBanHex:
    @pytest.mark.parametrize("van_ban", [
        "", "a", "Xin chao Thay Co!", "Đại học Kinh tế Quốc dân — bảo mật thông tin",
        "Mật khẩu: NEU_2026 🔐", "x" * 5000, "dòng 1\ndòng 2\n\ttab",
    ])
    def test_khu_hoi(self, van_ban):
        assert stream.decrypt_text_hex(stream.encrypt_text_hex(van_ban, 123456789), 123456789) == van_ban

    def test_dinh_dang_hex(self):
        van_ban = "Đại học"
        h = stream.encrypt_text_hex(van_ban, 7)
        int(h, 16)
        assert h == h.lower()
        assert len(h) == 2 * (stream.KICH_THUOC_NONCE + len(van_ban.encode("utf-8")))

    def test_nonce_ngau_nhien(self):
        h1, h2 = stream.encrypt_text_hex("cung ban ro", 7), stream.encrypt_text_hex("cung ban ro", 7)
        assert h1 != h2
        assert h1[:16] != h2[:16]
        assert stream.decrypt_text_hex(h1, 7) == stream.decrypt_text_hex(h2, 7) == "cung ban ro"

    def test_cau_truc_nonce_va_ban_ma(self, monkeypatch):
        monkeypatch.setattr(stream.secrets, "token_bytes", lambda n: b"\x00" * n)
        h = stream.encrypt_text_hex("abc", 2)
        assert h[:16] == "00" * 8
        assert h[16:] == stream.keystream_xor(b"abc", 2, b"\x00" * 8).hex()

    def test_khoa_sai(self):
        goc = "Chuyen 5,000,000 VND cho Bob"
        h = stream.encrypt_text_hex(goc, 6)
        kq = stream.decrypt_text_hex(h, 5)           # khoá sai: không văng lỗi UTF-8, chỉ ra chuỗi vô nghĩa
        assert isinstance(kq, str) and kq != goc

    def test_hex_hoa_duoc_chap_nhan(self):
        h = stream.encrypt_text_hex("Xin chào", 11)
        assert stream.decrypt_text_hex(h.upper(), 11) == "Xin chào"

    def test_hex_sai_dinh_dang(self):
        with pytest.raises(ValueError):
            stream.decrypt_text_hex("zz-khong-phai-hex", 1)
        with pytest.raises(ValueError):
            stream.decrypt_text_hex("abc", 1)            # số ký tự lẻ

    def test_hex_ngan_hon_nonce(self):
        with pytest.raises(ValueError):
            stream.decrypt_text_hex("abcd", 1)
        with pytest.raises(ValueError):
            stream.decrypt_text_hex("", 1)

    def test_chi_co_nonce(self):
        assert stream.decrypt_text_hex("00" * 8, 1) == ""


# ---------------------------------------------------------------- 5. QUY ƯỚC DỰ ÁN
class TestQuyUoc:
    def test_khong_dung_hashlib_trong_ma_nguon(self):
        with open(stream.__file__, encoding="utf-8") as f:
            assert "hashlib" not in f.read()

    def test_dung_sha256_tu_viet_cua_dh(self):
        assert stream.custom_sha256_bytes is dh.custom_sha256_bytes
