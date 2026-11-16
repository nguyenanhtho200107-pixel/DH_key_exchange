"""
Kiểm thử app/filecrypt.py (phần CLI): tạo tệp mẫu, mã hoá và giải mã tệp bằng khoá DH, bảng đo tốc độ.
Mọi tệp được ghi trong thư mục tạm (fixture thu_muc_tam), không đụng thư mục thật của repo.
"""
import hashlib
import os
import re
import struct
import zlib

import pytest

from app import filecrypt
from core.stream import keystream_xor


def doc(duong_dan):
    with open(duong_dan, "rb") as f:
        return f.read()


def bam_sha256(du_lieu: bytes) -> str:
    return hashlib.sha256(du_lieu).hexdigest()


def tach_chunk_png(du_lieu: bytes):
    """Tách các chunk PNG: trả về danh sách (loại, dữ liệu, crc_dung)."""
    assert du_lieu[:8] == b"\x89PNG\r\n\x1a\n"
    vi_tri, ds = 8, []
    while vi_tri < len(du_lieu):
        n = struct.unpack(">I", du_lieu[vi_tri:vi_tri + 4])[0]
        loai = du_lieu[vi_tri + 4:vi_tri + 8]
        data = du_lieu[vi_tri + 8:vi_tri + 8 + n]
        crc = struct.unpack(">I", du_lieu[vi_tri + 8 + n:vi_tri + 12 + n])[0]
        ds.append((loai, data, crc == (zlib.crc32(loai + data) & 0xFFFFFFFF)))
        vi_tri += 12 + n
    return ds


# ---------------------------------------------------------------- 1. TỆP MẪU
class TestTepMau:
    def test_tao_hai_tep(self, thu_muc_tam):
        txt, png = filecrypt.ensure_sample_files()
        assert txt == os.path.join("samples", "thong_diep.txt")
        assert png == os.path.join("samples", "anh_mau.png")
        assert os.path.isdir("samples")

    def test_noi_dung_van_ban(self, thu_muc_tam):
        txt, _ = filecrypt.ensure_sample_files()
        with open(txt, encoding="utf-8") as f:
            noi_dung = f.read()
        assert "Diffie-Hellman" in noi_dung and "ĐẠI HỌC KINH TẾ QUỐC DÂN" in noi_dung
        assert noi_dung.count("\n") == 3

    def test_png_hop_le(self, thu_muc_tam):
        _, png = filecrypt.ensure_sample_files()
        du_lieu = doc(png)
        chunks = tach_chunk_png(du_lieu)
        assert [c[0] for c in chunks] == [b"IHDR", b"IDAT", b"IEND"]
        assert all(c[2] for c in chunks)                              # CRC của mọi chunk đều đúng
        rong, cao, sau_bit, kieu_mau, nen, loc, xen = struct.unpack(">IIBBBBB", chunks[0][1])
        assert (rong, cao, sau_bit, kieu_mau, nen, loc, xen) == (120, 120, 8, 2, 0, 0, 0)
        dong_tho = zlib.decompress(chunks[1][1])
        assert len(dong_tho) == 120 * (1 + 120 * 3)                   # mỗi dòng: 1 byte bộ lọc + 120 điểm ảnh RGB
        assert all(dong_tho[i * 361] == 0 for i in range(120))        # bộ lọc 0 ở đầu mỗi dòng
        assert 40_000 < len(du_lieu) < 50_000                         # khoảng 43 KB như ghi trong tài liệu

    def test_gia_tri_diem_anh_dung_cong_thuc(self, thu_muc_tam):
        _, png = filecrypt.ensure_sample_files()
        dong_tho = zlib.decompress(tach_chunk_png(doc(png))[1][1])
        for y, x in ((0, 0), (5, 7), (119, 119), (60, 100)):
            bd = y * 361 + 1 + x * 3
            assert tuple(dong_tho[bd:bd + 3]) == ((x * 2) % 256, (y * 2) % 256, ((x + y) * 3) % 256)

    def test_tao_png_kich_thuoc_tuy_y(self, thu_muc_tam):
        filecrypt._generate_sample_png("nho.png", 10, 4)
        chunks = tach_chunk_png(doc("nho.png"))
        assert struct.unpack(">II", chunks[0][1][:8]) == (10, 4)
        assert len(zlib.decompress(chunks[1][1])) == 4 * (1 + 10 * 3)

    def test_goi_lai_khong_ghi_de(self, thu_muc_tam):
        txt, png = filecrypt.ensure_sample_files()
        with open(txt, "w", encoding="utf-8") as f:
            f.write("nội dung do người dùng sửa")
        goc_png = doc(png)
        filecrypt.ensure_sample_files()
        with open(txt, encoding="utf-8") as f:
            assert f.read() == "nội dung do người dùng sửa"
        assert doc(png) == goc_png


# ---------------------------------------------------------------- 2. MÃ HOÁ / GIẢI MÃ TỆP
class TestDemoFile:
    def test_tep_van_ban(self, thu_muc_tam, capsys):
        txt, _ = filecrypt.ensure_sample_files()
        goc = doc(txt)
        assert filecrypt.demo_file(txt) is True
        out = capsys.readouterr().out
        assert "khôi phục đúng" in out and f"({len(goc)} bytes)" in out
        assert doc(os.path.join("samples", "thong_diep_khoi_phuc.txt")) == goc

    def test_tep_anh(self, thu_muc_tam, capsys):
        _, png = filecrypt.ensure_sample_files()
        goc = doc(png)
        assert filecrypt.demo_file(png) is True
        capsys.readouterr()
        kp = doc(os.path.join("samples", "anh_mau_khoi_phuc.png"))
        assert kp == goc
        assert all(c[2] for c in tach_chunk_png(kp))                  # ảnh khôi phục vẫn là PNG hợp lệ

    def test_ban_ma_khac_ban_goc_va_cung_do_dai(self, thu_muc_tam, capsys):
        txt, _ = filecrypt.ensure_sample_files()
        goc = doc(txt)
        filecrypt.demo_file(txt)
        capsys.readouterr()
        ma = doc(os.path.join("samples", "thong_diep_ma_hoa.txt.enc"))
        assert len(ma) == len(goc) and ma != goc

    def test_ban_ma_khop_luong_khoa_cua_khoa_chung(self, thu_muc_tam, capsys):
        # khoá chung DH của tham số mặc định: p = 2^64 - 59, g = 5, a = 135792468, b = 246813579
        p, g, a, b = 18446744073709551557, 5, 135792468, 246813579
        K = pow(pow(g, b, p), a, p)
        txt, _ = filecrypt.ensure_sample_files()
        goc = doc(txt)
        filecrypt.demo_file(txt)
        capsys.readouterr()
        assert doc(os.path.join("samples", "thong_diep_ma_hoa.txt.enc")) == keystream_xor(goc, K)

    def test_tep_goc_khong_bi_sua(self, thu_muc_tam, capsys):
        txt, png = filecrypt.ensure_sample_files()
        truoc = (bam_sha256(doc(txt)), bam_sha256(doc(png)))
        filecrypt.demo_file(txt)
        filecrypt.demo_file(png)
        capsys.readouterr()
        assert (bam_sha256(doc(txt)), bam_sha256(doc(png))) == truoc

    @pytest.mark.parametrize("noi_dung", [b"", b"x", bytes(range(256)) * 40, os.urandom(100 * 1024)])
    def test_tep_tuy_y(self, thu_muc_tam, capsys, noi_dung):
        with open("bat_ky.bin", "wb") as f:
            f.write(noi_dung)
        assert filecrypt.demo_file("bat_ky.bin") is True
        capsys.readouterr()
        assert doc("bat_ky_khoi_phuc.bin") == noi_dung
        assert len(doc("bat_ky_ma_hoa.bin.enc")) == len(noi_dung)

    def test_ten_tep_ket_qua_theo_duoi(self, thu_muc_tam, capsys):
        with open("bao_cao.final.txt", "wb") as f:
            f.write(b"abc")
        filecrypt.demo_file("bao_cao.final.txt")
        capsys.readouterr()
        assert os.path.exists("bao_cao.final_ma_hoa.txt.enc") and os.path.exists("bao_cao.final_khoi_phuc.txt")

    def test_tham_so_tuy_y(self, thu_muc_tam, capsys):
        with open("a.txt", "wb") as f:
            f.write("Tiếng Việt có dấu".encode("utf-8"))
        assert filecrypt.demo_file("a.txt", p=1000003, g=2, a=12345, b=54321) is True
        out = capsys.readouterr().out
        K = pow(pow(2, 54321, 1000003), 12345, 1000003)
        assert f"Khóa chung DH     : {K}" in out

    def test_tep_khong_ton_tai(self, thu_muc_tam):
        with pytest.raises(FileNotFoundError):
            filecrypt.demo_file("khong_co.txt")

    def test_in_thoi_gian(self, thu_muc_tam, capsys):
        txt, _ = filecrypt.ensure_sample_files()
        filecrypt.demo_file(txt)
        out = capsys.readouterr().out
        assert re.search(r"Mã hóa = \d+\.\d{2} ms \| Giải mã = \d+\.\d{2} ms", out)


# ---------------------------------------------------------------- 3. BẢNG ĐO THEO KÍCH THƯỚC
class TestBangDo:
    def test_dinh_dang_bang(self, monkeypatch, capsys):
        # thay mã dòng bằng hàm nhanh để chỉ kiểm tra định dạng và logic bảng
        monkeypatch.setattr(filecrypt, "keystream_xor", lambda d, k: bytes(b ^ 0x5A for b in d))
        filecrypt.benchmark_file_encryption()
        out = capsys.readouterr().out
        hang = re.findall(r"^\s+(\S+(?: \S+)*?)\s+\| (\d+)\s+\| ([\d.]+)\s+\| ([\d.]+)\s*$", out, re.M)
        assert [h[1] for h in hang] == ["1024", "10240", "102400", "1048576"]
        assert [h[0] for h in hang] == ["1 KB", "10 KB", "100 KB", "1 MB (1024 KB)"]
        assert all(float(h[2]) >= 0 and float(h[3]) >= 0 for h in hang)

    @pytest.mark.cham
    def test_do_that_1_mb(self, capsys):
        filecrypt.benchmark_file_encryption()
        out = capsys.readouterr().out
        assert "1 MB (1024 KB)" in out and "1048576" in out
