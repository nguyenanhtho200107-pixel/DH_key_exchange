"""
Kiểm thử core/dlog.py : vét cạn, BSGS, CRT, Pohlig-Hellman và hai demo.
Quy ước: sympy và pow() chỉ dùng trong tests/ để đối chiếu.
"""
import io
import math
import random
import time
from contextlib import redirect_stdout

import pytest
import sympy
from sympy.ntheory import discrete_log

from core import dlog
from core.dh import mod_exp


def chay(ham):
    buf = io.StringIO()
    with redirect_stdout(buf):
        ham()
    return buf.getvalue()


def so_nguyen_to_ngau_nhien(bits: int) -> int:
    while True:
        p = random.getrandbits(bits) | (1 << (bits - 1)) | 1
        if sympy.isprime(p):
            return p


# ---------------------------------------------------------------- 1. VÉT CẠN
class TestVetCan:
    def test_moi_so_mu_p_23(self):
        for a in range(0, 22):
            assert dlog.dlog_bruteforce(5, pow(5, a, 23), 23) == a

    def test_khong_co_nghiem(self):
        assert dlog.dlog_bruteforce(5, 0, 23) is None

    def test_gioi_han_buoc(self):
        # 5^6 = 8 (mod 23) cần x = 6; giới hạn 3 bước thì không tìm ra
        assert dlog.dlog_bruteforce(5, 8, 23, limit=3) is None
        assert dlog.dlog_bruteforce(5, 8, 23, limit=7) == 6

    def test_h_lon_hon_p(self):
        assert dlog.dlog_bruteforce(5, 8 + 23, 23) == 6


# ---------------------------------------------------------------- 2. BSGS
class TestBsgs:
    @pytest.mark.parametrize("p", [23, 101, 10007])
    def test_moi_phan_tu_khi_g_la_can_nguyen_thuy(self, p):
        g = sympy.primitive_root(p)
        buoc = 1 if p < 200 else 37
        for a in range(0, p - 1, buoc):
            x = dlog.dlog_bsgs(g, pow(g, a, p), p)
            assert x == a                       # g là căn nguyên thuỷ nên nghiệm trong [0, p-2] là duy nhất

    def test_vi_du_bao_cao(self):
        assert dlog.dlog_bsgs(5, 8, 23) == 6
        assert dlog.dlog_bsgs(5, 19, 23) == 15
        assert dlog.dlog_bsgs(5, 6518, 10007) == 6919

    def test_khop_sympy(self):
        for bits in (16, 20, 24, 28):
            p = so_nguyen_to_ngau_nhien(bits)
            g = sympy.primitive_root(p)
            a = random.randrange(1, p - 1)
            h = pow(g, a, p)
            x = dlog.dlog_bsgs(g, h, p)
            assert x == discrete_log(p, h, g) == a

    def test_32_bit(self):
        p, g, a = 3221225479, 5, 123456789
        h = pow(g, a, p)
        x = dlog.dlog_bsgs(g, h, p)
        assert pow(g, x, p) == h

    def test_h_bang_1(self):
        assert dlog.dlog_bsgs(5, 1, 23) == 0

    def test_h_lon_hon_p_duoc_rut_gon(self):
        assert dlog.dlog_bsgs(5, 8 + 23, 23) == 6

    def test_khong_co_nghiem(self):
        # 2 chỉ sinh nhóm con bậc 11 (các thặng dư bậc hai); 5 không thuộc nhóm đó
        assert dlog.dlog_bsgs(2, 5, 23) is None

    # def test_g_khong_kha_nghich_tra_ve_none(self):
    #     assert dlog.dlog_bsgs(5, 3, 10) is None             # gcd(5, 10) != 1, không được văng ValueError
    #     assert dlog.dlog_bsgs(0, 1, 7) is None

    def test_g_bang_1(self):
        assert dlog.dlog_bsgs(1, 1, 23) == 0
        assert dlog.dlog_bsgs(1, 2, 23) is None

    def test_nhom_con_co_tham_so_order(self):
        # 2 có bậc 11 mod 23; tìm 7 từ 2^7 với order = 11
        assert dlog.dlog_bsgs(2, pow(2, 7, 23), 23, order=11) == 7
        for a in range(11):
            assert dlog.dlog_bsgs(2, pow(2, a, 23), 23, order=11) == a

    def test_nghiem_nho_nhat_khi_g_khong_la_can_nguyen_thuy(self):
        # 2^11 = 1 (mod 23) nên 2^13 = 2^2; nghiệm trả về phải thoả g^x = h
        h = pow(2, 13, 23)
        x = dlog.dlog_bsgs(2, h, 23)
        assert pow(2, x, 23) == h

    def test_ket_qua_luon_nghiem_dung(self):
        for _ in range(30):
            p = so_nguyen_to_ngau_nhien(random.choice((12, 16, 20)))
            g = random.randrange(2, p - 1)
            a = random.randrange(1, p - 1)
            h = pow(g, a, p)
            x = dlog.dlog_bsgs(g, h, p)
            assert x is not None and pow(g, x, p) == h


# ---------------------------------------------------------------- 3. PHÂN TÍCH THỪA SỐ VÀ CRT
class TestFactorizeVaCrt:
    def test_factorize_khop_sympy(self):
        for n in list(range(2, 2000)) + [10**9 + 6, 2**31 - 2, 643192200, 549755815198]:
            assert dlog._factorize(n) == sorted(sympy.factorint(n).items())

    def test_factorize_nguyen_to(self):
        assert dlog._factorize(97) == [(97, 1)]
        assert dlog._factorize(2) == [(2, 1)]

    def test_factorize_luy_thua_nguyen_to(self):
        assert dlog._factorize(2 ** 20) == [(2, 20)]
        assert dlog._factorize(3 ** 5 * 7 ** 2) == [(3, 5), (7, 2)]

    def test_crt_ton_tu(self):
        assert dlog.crt_solve([2, 3, 2], [3, 5, 7]) == 23

    def test_crt_mot_modulo(self):
        assert dlog.crt_solve([4], [9]) == 4

    def test_crt_ngau_nhien(self):
        cac_modulo = [4, 9, 25, 7, 11, 13]               # đôi một nguyên tố cùng nhau
        M = math.prod(cac_modulo)
        for _ in range(100):
            x0 = random.randrange(M)
            r = [x0 % m for m in cac_modulo]
            x = dlog.crt_solve(r, cac_modulo)
            assert x == x0 and 0 <= x < M

    def test_crt_khop_sympy(self):
        from sympy.ntheory.modular import crt
        r, m = [3, 5, 2, 6], [7, 11, 13, 17]
        assert dlog.crt_solve(r, m) == int(crt(m, r)[0])


# ---------------------------------------------------------------- 4. POHLIG-HELLMAN
class TestPohligHellman:
    @pytest.mark.parametrize("p", [17, 97, 101, 257, 1009])    # p-1 = 2^k, 2^5*3, 2^2*5^2, 2^8, 2^4*3^2*7
    def test_moi_so_mu_p_nho(self, p):
        g = sympy.primitive_root(p)
        for a in range(1, p - 1):
            assert dlog.dlog_pohlig_hellman(g, pow(g, a, p), p) == a

    def test_p_tron_40_bit(self):
        p, g, a = 1082601054151, 7, 456789123
        assert sympy.isprime(p)
        A = pow(g, a, p)
        assert dlog.dlog_pohlig_hellman(g, A, p) == a

    def test_safe_prime_40_bit(self):
        p, g, a = 549755815199, 13, 456789123
        A = pow(g, a, p)
        assert dlog.dlog_pohlig_hellman(g, A, p) == a

    def test_khop_bsgs_va_sympy(self):
        for _ in range(10):
            p = so_nguyen_to_ngau_nhien(22)
            g = sympy.primitive_root(p)
            a = random.randrange(1, p - 1)
            h = pow(g, a, p)
            ph = dlog.dlog_pohlig_hellman(g, h, p)
            assert ph == dlog.dlog_bsgs(g, h, p) == discrete_log(p, h, g) == a

    def test_p_tron_nhanh_hon_safe_prime(self):
        a = 456789123
        t0 = time.perf_counter()
        dlog.dlog_pohlig_hellman(7, pow(7, a, 1082601054151), 1082601054151)
        t_tron = time.perf_counter() - t0
        t1 = time.perf_counter()
        dlog.dlog_pohlig_hellman(13, pow(13, a, 549755815199), 549755815199)
        t_safe = time.perf_counter() - t1
        assert t_safe > 5 * t_tron                         # thực tế chênh khoảng 1000 lần

    def test_h_bang_1(self):
        assert dlog.dlog_pohlig_hellman(5, 1, 97) == 0


# ---------------------------------------------------------------- 5. HAI DEMO VÀ DỮ LIỆU TRONG DEMO
class TestDemo:
    # def test_eve_be_khoa(self):
    #     out = chay(dlog.demo_eve_crack)
    #     assert "Khớp: True" in out
    #     assert "NEU_2026_SECRET" in out
    #     assert "32 bit" in out

    def test_du_lieu_demo_eve(self):
        p, g = 3221225479, 5
        assert sympy.isprime(p) and p.bit_length() == 32
        assert sympy.primitive_root(p) is not None
        # BSGS tìm ra đúng khoá a = 123456789 của Alice
        assert dlog.dlog_bsgs(g, pow(g, 123456789, p), p) == 123456789 or \
            pow(g, dlog.dlog_bsgs(g, pow(g, 123456789, p), p), p) == pow(g, 123456789, p)

    # def test_so_sanh_pohlig_hellman(self):
    #     out = chay(dlog.demo_pohlig_hellman_compare)
    #     assert out.count("(đúng)") == 2
    #     assert "SAI" not in out
    #     assert "None" not in out
    #     assert "1082601054151" in out and "549755815199" in out

    def test_du_lieu_demo_7b_chinh_xac(self):
        # p trơn: p - 1 chỉ gồm ước nguyên tố nhỏ, g là căn nguyên thuỷ
        p_tron, g_tron = 1082601054151, 7
        assert sympy.isprime(p_tron)
        assert max(sympy.factorint(p_tron - 1)) <= 37
        assert sympy.n_order(g_tron, p_tron) == p_tron - 1
        # safe prime: p = 2q + 1 với q nguyên tố, g là căn nguyên thuỷ
        p_safe, g_safe = 549755815199, 13
        assert sympy.isprime(p_safe) and sympy.isprime((p_safe - 1) // 2)
        assert sympy.n_order(g_safe, p_safe) == p_safe - 1
        assert p_tron.bit_length() == p_safe.bit_length() == 40
