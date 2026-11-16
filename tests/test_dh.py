"""
Bộ kiểm thử cho core/dh.py (phần Lead).

Quy ước: hashlib, sympy, mpmath và pow() ba tham số CHỈ được dùng trong tests/ để đối chiếu.
Ba lớp kiểm thử: (1) ca tự viết TC1-TC5, (2) test biên, (3) đối chiếu chuẩn (RFC, pow, hashlib, sympy).
"""
import hashlib
import random
import subprocess
import sys
import textwrap

import mpmath
import pytest
import sympy

from core import dh

random.seed(20261114)  # cố định để chạy lại ra cùng kết quả


# ==============================================================================
# LỚP 1: CÁC CA TỰ VIẾT TC1-TC5
# ==============================================================================

class TestTC1_DH_p23:
    """TC1: p=23, g=5, a=6, b=15 -> A=8, B=19, khoá=2."""
    p, g, a, b = 23, 5, 6, 15

    def test_khoa_cong_khai(self):
        assert dh.mod_exp(self.g, self.a, self.p) == 8
        assert dh.mod_exp(self.g, self.b, self.p) == 19

    def test_khoa_chung(self):
        A, B = 8, 19
        assert dh.mod_exp(B, self.a, self.p) == 2
        assert dh.mod_exp(A, self.b, self.p) == 2


class TestTC2_DH_64bit:
    """TC2: p nguyên tố 64 bit, g ngẫu nhiên -> hai bên cùng khoá."""

    @staticmethod
    def _prime_64():
        while True:
            c = random.getrandbits(64) | (1 << 63) | 1
            if dh.is_prime_miller_rabin(c):
                return c

    def test_hai_ben_cung_khoa(self):
        for _ in range(5):
            p = self._prime_64()
            assert p.bit_length() == 64
            g = random.randrange(2, p - 1)
            a, b = random.randrange(2, p - 1), random.randrange(2, p - 1)
            A, B = dh.mod_exp(g, a, p), dh.mod_exp(g, b, p)
            assert dh.mod_exp(B, a, p) == dh.mod_exp(A, b, p)

    def test_gen_params_16_bit(self):
        p, g = dh.gen_params(16)
        assert dh.is_prime_miller_rabin(p) and dh.is_prime_miller_rabin((p - 1) // 2)
        assert dh.la_can_nguyen_thuy(p, g) is True


class TestTC3_KhoaCongKhaiXau:
    """TC3: khoá công khai 0, 1, p-1 bị từ chối."""

    @pytest.mark.parametrize("y", [0, 1, 22])
    def test_bi_tu_choi(self, y):
        assert dh.validate_pub(y, 23) is False

    @pytest.mark.parametrize("y", [23, 24, 100, -1, -22])
    def test_ngoai_khoang_cung_bi_tu_choi(self, y):
        assert dh.validate_pub(y, 23) is False

    @pytest.mark.parametrize("y", [2, 5, 8, 19, 21])
    def test_hop_le_duoc_chap_nhan(self, y):
        assert dh.validate_pub(y, 23) is True

    def test_nhom_con_nho(self):
        # g = 4 sinh nhóm con bậc q = 11 trong Z_23*; 5 không nằm trong nhóm con đó
        assert dh.validate_pub(4, 23, 11) is True
        assert dh.validate_pub(5, 23, 11) is False


class TestTC4_MITM:
    """TC4: MITM với p=23, m(c)=3 -> 8, 19, 10, 6, 5; Alice và Bob khác khoá."""
    p, g, a, b, c = 23, 5, 6, 15, 3

    def test_gia_tri_so(self):
        p, g = self.p, self.g
        A, B, M = (dh.mod_exp(g, x, p) for x in (self.a, self.b, self.c))
        assert (A, B, M) == (8, 19, 10)
        k_alice, k_bob = dh.mod_exp(M, self.a, p), dh.mod_exp(M, self.b, p)
        assert (k_alice, k_bob) == (6, 5)
        assert k_alice != k_bob
        # Mallory tính được cả hai khoá
        assert dh.mod_exp(A, self.c, p) == k_alice
        assert dh.mod_exp(B, self.c, p) == k_bob

    def test_output_mo_phong(self, capsys):
        dh.run_mitm_simulation(self.p, self.g, self.a, self.b, self.c)
        out = capsys.readouterr().out
        assert "M = g^c = 10" in out
        assert "KHÁC nhau (6 và 5)" in out
        assert out.count("KHỚP") == 2 and "LỆCH" not in out


class TestTC5_SAS_ChuKy:
    """TC5: SAS và chữ ký, có và không có Mallory."""
    p, g, a, b, c = 23, 5, 6, 15, 3

    def setup_method(self):
        p, g = self.p, self.g
        self.A, self.B, self.M = (dh.mod_exp(g, x, p) for x in (self.a, self.b, self.c))

    def test_khong_mallory_sas_khop(self):
        K = dh.mod_exp(self.B, self.a, self.p)
        assert dh.sas_code(self.A, self.B, K) == dh.sas_code(self.A, self.B, dh.mod_exp(self.A, self.b, self.p))

    def test_co_mallory_sas_lech(self):
        p = self.p
        sas_a = dh.sas_code(self.A, self.M, dh.mod_exp(self.M, self.a, p))
        sas_b = dh.sas_code(self.M, self.B, dh.mod_exp(self.M, self.b, p))
        assert sas_a != sas_b

    def test_dinh_dang_sas(self):
        s = dh.sas_code(8, 19, 2)
        assert len(s) == 4 and s == s.upper() and all(ch in "0123456789ABCDEF" for ch in s)

    def test_chu_ky_hop_le(self):
        pub, priv = dh.rsa_keygen()
        sig = dh.rsa_sign(f"DH-pub:{self.A}", priv)
        assert dh.rsa_verify(f"DH-pub:{self.A}", sig, pub) is True

    def test_mallory_khong_ky_lai_duoc(self):
        pub, priv = dh.rsa_keygen()
        sig = dh.rsa_sign(f"DH-pub:{self.A}", priv)
        assert dh.rsa_verify(f"DH-pub:{self.M}", sig, pub) is False

    def test_mo_phong_phong_thu_in_ket_qua(self, capsys):
        dh.run_defense_simulation(self.p, self.g, self.a, self.b, self.c)
        out = capsys.readouterr().out
        assert "=> KHỚP" in out and "LỆCH, phát hiện MITM" in out
        assert "từ chối, phát hiện MITM" in out


# ==============================================================================
# LỚP 2: TEST BIÊN
# ==============================================================================

class TestBien_ModExp:
    @pytest.mark.parametrize("base,exp,mod", [
        (5, 0, 7), (5, 1, 7), (0, 5, 7), (0, 0, 7), (10, 3, 1), (100, 5, 7),
        (7, 1, 13), (-3, 3, 7), (2, 10, 1000), (1, 10**9, 97),
    ])
    def test_khop_pow(self, base, exp, mod):
        assert dh.mod_exp(base, exp, mod) == pow(base, exp, mod)

    @pytest.mark.parametrize("mod", [0, -5])
    def test_mod_khong_hop_le(self, mod):
        with pytest.raises(ValueError):
            dh.mod_exp(2, 3, mod)

    def test_exp_am(self):
        with pytest.raises(ValueError):
            dh.mod_exp(2, -1, 7)


class TestBien_IsPrime:
    @pytest.mark.parametrize("n,expected", [
        (-7, False), (0, False), (1, False), (2, True), (3, True), (4, False),
        (97, True), (10**6, False),
        (561, False), (1105, False), (1729, False),          # số Carmichael
        (2**61 - 1, True),                                    # Mersenne nguyên tố
        (2**67 - 1, False),                                   # Mersenne hợp số
        (2**89 - 1, True),
    ])
    def test_ca_dac_biet(self, n, expected):
        assert dh.is_prime_miller_rabin(n) is expected
        assert sympy.isprime(n) is expected                   # đối chiếu độc lập

    def test_so_chan_lon(self):
        assert dh.is_prime_miller_rabin(2**64) is False


class TestBien_FindGenerator:
    @pytest.mark.parametrize("p", [3, 5, 7, 11, 13, 23, 101])
    def test_sinh_du_p_tru_1_gia_tri(self, p):
        g = dh.find_generator(p)
        assert {pow(g, k, p) for k in range(p - 1)} == set(range(1, p))

    def test_p_bang_2(self):
        assert dh.find_generator(2) == 1

    def test_la_can_nguyen_thuy(self):
        assert dh.la_can_nguyen_thuy(23, 5) is True
        assert dh.la_can_nguyen_thuy(23, 2) is False  # 2 có bậc 11 mod 23
        assert dh.la_can_nguyen_thuy(23, 4) is False
        assert dh.la_can_nguyen_thuy(dh.GIOI_HAN_PHAN_TICH + 1, 2) is None


class TestBien_GenParams:
    @pytest.mark.parametrize("bits", [3, 4, 5, 8, 12])
    def test_nhieu_lan_chay(self, bits):
        for _ in range(5):
            p, g = dh.gen_params(bits)
            q = (p - 1) // 2
            assert p == 2 * q + 1
            assert sympy.isprime(p) and sympy.isprime(q)
            assert dh.la_can_nguyen_thuy(p, g) is True

    @pytest.mark.parametrize("bits", [0, 1, 2])
    def test_bits_qua_nho_khong_treo(self, bits):
        """gen_params(2) từng treo vô hạn (q luôn bằng 1). Chạy ở tiến trình riêng, quá 5 giây là lỗi."""
        code = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {sys.path[0]!r})
            from core import dh
            try:
                dh.gen_params({bits})
                print("RETURNED")
            except ValueError:
                print("VALUEERROR")
        """)
        try:
            r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            pytest.fail(f"gen_params({bits}) bị treo (> 5 giây)")
        assert "VALUEERROR" in r.stdout, r.stdout + r.stderr


class TestBien_ValidateParams:
    @pytest.mark.parametrize("p,g", [(21, 5), (22, 5), (1, 2), (23, 1), (23, 23), (23, 40), (23, 0)])
    def test_tham_so_sai(self, p, g, capsys):
        assert dh.validate_dh_params(p, g) is False
        assert "Lỗi" in capsys.readouterr().out

    def test_tham_so_dung(self):
        assert dh.validate_dh_params(23, 5) is True

    def test_canh_bao_khong_chan(self, capsys):
        ds = dh.canh_bao_tham_so(23, 4)              # g=4 không phải căn nguyên thuỷ
        assert any("không phải căn nguyên thuỷ" in s for s in ds)
        assert any("< 2048" in s for s in ds)
        ds = dh.canh_bao_tham_so(13, 2)              # 13 không phải safe prime ((13-1)/2 = 6)
        assert any("safe prime" in s for s in ds)

    def test_khong_canh_bao_safe_prime_khi_dung(self):
        ds = dh.canh_bao_tham_so(23, 5)
        assert not any("safe prime" in s or "căn nguyên thuỷ" in s for s in ds)


class TestBien_Stream_SHA:
    @pytest.mark.parametrize("n", [0, 1, 3, 55, 56, 57, 63, 64, 65, 119, 120, 128, 1000])
    def test_sha256_bien_do_dai_khoi(self, n):
        data = bytes(random.getrandbits(8) for _ in range(n))
        assert dh.custom_sha256_bytes(data) == hashlib.sha256(data).digest()

    def test_vector_chuan(self):
        assert dh.custom_sha256_bytes(b"abc").hex() == \
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        assert dh.custom_sha256_bytes(b"").hex() == \
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_tieng_viet(self):
        data = "Xin chào, Việt Nam".encode()
        assert dh.custom_sha256_bytes(data) == hashlib.sha256(data).digest()


# ==============================================================================
# LỚP 3: ĐỐI CHIẾU CHUẨN
# ==============================================================================

class TestDoiChieu_Pow:
    @pytest.mark.parametrize("bits,so_bo", [(8, 1000), (64, 1000), (512, 300), (2048, 100)])
    def test_mod_exp_khop_pow(self, bits, so_bo):
        for _ in range(so_bo):
            m = random.getrandbits(bits) | (1 << (bits - 1)) | 1
            base, e = random.getrandbits(bits + 8), random.getrandbits(bits)
            assert dh.mod_exp(base, e, m) == pow(base, e, m)


class TestDoiChieu_MillerRabin:
    def test_so_nho_khop_sympy(self):
        sai = [n for n in range(0, 3000) if dh.is_prime_miller_rabin(n) != sympy.isprime(n)]
        assert sai == []

    def test_so_64_bit_khop_sympy(self):
        for _ in range(200):
            n = random.getrandbits(64) | (1 << 63) | 1
            assert dh.is_prime_miller_rabin(n) == sympy.isprime(n)


class TestDoiChieu_RFC3526:
    P = dh.RFC_3526_2048_P
    G = dh.RFC_3526_2048_G

    def test_dai_2048_bit(self):
        assert self.P.bit_length() == 2048

    def test_cong_thuc_pi(self):
        """p = 2^2048 - 2^1984 - 1 + 2^64 * (floor(2^1918 * pi) + 124476), theo RFC 3526."""
        mpmath.mp.prec = 2300
        phan_pi = int(mpmath.floor(mpmath.mpf(2) ** 1918 * mpmath.pi))
        assert self.P == 2**2048 - 2**1984 - 1 + 2**64 * (phan_pi + 124476)

    def test_la_nguyen_to(self):
        assert dh.is_prime_miller_rabin(self.P, 5)
        assert sympy.isprime(self.P)

    def test_safe_prime(self):
        q = (self.P - 1) // 2
        assert dh.is_prime_miller_rabin(q, 5)
        assert sympy.isprime(q)

    def test_phien_dh_tron_ven(self):
        a, b = random.getrandbits(256) | 1, random.getrandbits(256) | 1
        A, B = dh.mod_exp(self.G, a, self.P), dh.mod_exp(self.G, b, self.P)
        assert dh.mod_exp(B, a, self.P) == dh.mod_exp(A, b, self.P)
        assert dh.validate_pub(A, self.P, (self.P - 1) // 2) is True

    def test_ham_kiem_tra_in_ket_qua(self, capsys):
        dh.kiem_tra_rfc3526()
        out = capsys.readouterr().out
        assert "2048 bit" in out and out.count("True") == 4


# ==============================================================================
# TÍNH TAY ĐỐI CHIẾU
# ==============================================================================

class TestTinhTay:
    def test_bien_buoc_5_mu_6_mod_23(self):
        """Tính tay 5^6 mod 23: 6 = 110 (nhị phân), đọc từ bit thấp: 0, 1, 1."""
        kq, steps = dh.mod_exp(5, 6, 23, return_steps=True)
        assert kq == 8
        assert [s["bit"] for s in steps] == [0, 1, 1]
        assert [s["curr_base"] for s in steps] == [5, 2, 4]          # 5, 5^2=25=2, 2^2=4
        assert [s["result_so_far"] for s in steps] == [1, 2, 8]      # 1, 1*2=2, 2*4=8

    def test_bien_buoc_5_mu_15_mod_23(self):
        kq, steps = dh.mod_exp(5, 15, 23, return_steps=True)
        assert kq == 19
        assert [s["curr_base"] for s in steps] == [5, 2, 4, 16]
        assert [s["result_so_far"] for s in steps] == [5, 10, 17, 19]

    def test_ba_vi_du(self):
        assert (dh.mod_exp(5, 6, 23), dh.mod_exp(5, 15, 23), dh.mod_exp(19, 6, 23)) == (8, 19, 2)
        assert (dh.mod_exp(5, 3, 23), dh.mod_exp(8, 3, 23) if False else dh.mod_exp(10, 6, 23),
               dh.mod_exp(10, 15, 23)) == (10, 6, 5)


# ==============================================================================
# CLI: NHẬP LIỆU XẤU
# ==============================================================================

def _gia_lap_input(monkeypatch, dong):
    it = iter(dong)

    def fake(_prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    monkeypatch.setattr("builtins.input", fake)


class TestCLI:
    def test_nhap_chu_so_am_roi_enter_mac_dinh(self, monkeypatch, capsys):
        _gia_lap_input(monkeypatch, ["abc", "-4", "", ])
        assert dh.hoi_so_nguyen("x", 6, 2, 21) == 6
        out = capsys.readouterr().out
        assert "phải nhập một số nguyên" in out and "phải >= 2" in out

    def test_nhap_ngoai_khoang(self, monkeypatch):
        _gia_lap_input(monkeypatch, ["99", "5"])
        assert dh.hoi_so_nguyen("x", None, 2, 21) == 5

    def test_chuoi_rong_khong_mac_dinh_hoi_lai(self, monkeypatch):
        _gia_lap_input(monkeypatch, ["", "  ", "7"])
        assert dh.hoi_so_nguyen("x", None, 2, 21) == 7

    def test_het_du_lieu_thoat_gon(self, monkeypatch):
        _gia_lap_input(monkeypatch, [])
        with pytest.raises(dh.NguoiDungThoat):
            dh.hoi_so_nguyen("x", None)

    def test_bo_qua_mac_dinh_ngoai_khoang(self, monkeypatch, capsys):
        _gia_lap_input(monkeypatch, ["", "3"])
        assert dh.hoi_so_nguyen("x", 6, 2, 4) == 3
        assert "nằm ngoài khoảng cho phép" in capsys.readouterr().out

    def test_tham_so_mac_dinh(self, monkeypatch):
        _gia_lap_input(monkeypatch, ["", "", "", ""])
        assert dh.nhap_tham_so_dh() == (23, 5, 6, 15, None)

    def test_p_khong_nguyen_to_bi_tu_choi(self, monkeypatch):
        _gia_lap_input(monkeypatch, ["22", "5"])
        assert dh.nhap_tham_so_dh() is None

    def test_g_bang_p_bi_tu_choi(self, monkeypatch):
        _gia_lap_input(monkeypatch, ["23", "23"])
        assert dh.nhap_tham_so_dh() is None

    def test_p_qua_nho(self, monkeypatch, capsys):
        _gia_lap_input(monkeypatch, ["3", "2"])
        assert dh.nhap_tham_so_dh() is None
        assert "p phải >= 5" in capsys.readouterr().out

    def test_khoa_bi_mat_ngoai_khoang_bi_hoi_lai(self, monkeypatch):
        _gia_lap_input(monkeypatch, ["23", "5", "22", "1", "6", "15"])
        assert dh.nhap_tham_so_dh() == (23, 5, 6, 15, None)

    def test_chay_tron_luong_dh(self, monkeypatch, capsys):
        _gia_lap_input(monkeypatch, ["", "", "", "", "n"])
        dh.nhap_tay_truc_tiep()
        out = capsys.readouterr().out
        assert "A) = 8" in out and "(B) = 19" in out and "K = 2 TRÙNG KHỚP" in out

    def test_chay_tron_luong_mitm(self, monkeypatch, capsys):
        _gia_lap_input(monkeypatch, ["", "", "", "", ""])
        dh.nhap_tay_mitm()
        out = capsys.readouterr().out
        assert "M = g^c = 10" in out and "phát hiện MITM" in out

    def test_dung_khi_khoa_cong_khai_xau(self, monkeypatch, capsys):
        # p=7, g=6 (g = p-1): A = 6^a mod 7 là 1 hoặc 6 -> không hợp lệ
        _gia_lap_input(monkeypatch, ["7", "6", "2", "3"])
        dh.nhap_tay_truc_tiep()
        out = capsys.readouterr().out
        assert "DỪNG" in out and "khoá chung" in out.lower()
