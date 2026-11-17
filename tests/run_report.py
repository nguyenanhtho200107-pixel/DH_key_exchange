"""
Báo cáo kiểm thử DH (core/dh.py): chạy trực tiếp `python tests/run_report.py` .
In: bảng TC1-TC5, đối chiếu mod_exp với pow(), đối chiếu khác, kiểm tra RFC 3526,
tính tay so với chương trình, dòng tổng kết "x/y đạt". Đồng thời ghi docs/test_log.txt.
Thoát với mã 0 nếu tất cả đạt, 1 nếu có mục lỗi.

Quy ước: hashlib, sympy, mpmath và pow() chỉ được dùng trong tests/ để đối chiếu.
"""
import hashlib
import os
import random
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import mpmath
import sympy

from core import dh

random.seed(20261114)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------- ghi song song ra file log
class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


results = []  # (ok: bool)


def ghi(ok: bool) -> str:
    results.append(bool(ok))
    return "PASS" if ok else "FAIL"


def tieu_de(s: str):
    print("\n" + "=" * 78)
    print(s)
    print("=" * 78)


def hang(*cot, rong=(6, 30, 30, 30, 6)):
    print("  ".join(str(c).ljust(w) if i < len(cot) - 1 else str(c) for i, (c, w) in enumerate(zip(cot, rong))))


# ---------------------------------------------------------------- 1. BẢNG TC1-TC5
def tc1():
    p, g, a, b = 23, 5, 6, 15
    A, B = dh.mod_exp(g, a, p), dh.mod_exp(g, b, p)
    K1, K2 = dh.mod_exp(B, a, p), dh.mod_exp(A, b, p)
    return "p=23,g=5,a=6,b=15", "A=8, B=19, khoá=2", f"A={A}, B={B}, khoá={K1}", (A, B, K1, K2) == (8, 19, 2, 2)


def tc2():
    so_lan, dung = 5, 0
    for _ in range(so_lan):
        while True:
            p = random.getrandbits(64) | (1 << 63) | 1
            if dh.is_prime_miller_rabin(p):
                break
        g, a, b = random.randrange(2, p - 1), random.randrange(2, p - 1), random.randrange(2, p - 1)
        A, B = dh.mod_exp(g, a, p), dh.mod_exp(g, b, p)
        dung += dh.mod_exp(B, a, p) == dh.mod_exp(A, b, p)
    return f"p,g ngẫu nhiên 64 bit ({so_lan} lần)", "Hai bên cùng khoá", f"{dung}/{so_lan} cùng khoá", dung == so_lan


def tc3():
    kq = {y: dh.validate_pub(y, 23) for y in (0, 1, 22)}
    return "Khoá công khai 0, 1, p-1 (p=23)", "Bị từ chối", "từ chối " + str([y for y, v in kq.items() if not v]), not any(kq.values())


def tc4():
    p, g, a, b, c = 23, 5, 6, 15, 3
    A, B, M = (dh.mod_exp(g, x, p) for x in (a, b, c))
    ka, kb = dh.mod_exp(M, a, p), dh.mod_exp(M, b, p)
    ok = (A, B, M, ka, kb) == (8, 19, 10, 6, 5) and ka != kb
    return "MITM p=23, m=3", "8,19,10,6,5; khác khoá", f"{A},{B},{M},{ka},{kb}; " + ("khác khoá" if ka != kb else "TRÙNG"), ok


def tc5():
    p, g, a, b, c = 23, 5, 6, 15, 3
    A, B, M = (dh.mod_exp(g, x, p) for x in (a, b, c))
    K = dh.mod_exp(B, a, p)
    sas_ok = dh.sas_code(A, B, K) == dh.sas_code(A, B, dh.mod_exp(A, b, p))
    sas_a = dh.sas_code(A, M, dh.mod_exp(M, a, p))
    sas_b = dh.sas_code(M, B, dh.mod_exp(M, b, p))
    pub, priv = dh.rsa_keygen()
    sig = dh.rsa_sign(f"DH-pub:{A}", priv)
    ky_that = dh.rsa_verify(f"DH-pub:{A}", sig, pub)
    ky_gia = dh.rsa_verify(f"DH-pub:{M}", sig, pub)
    thuc_te = (f"không Mallory: SAS {'khớp' if sas_ok else 'lệch'}; có Mallory: SAS "
               f"{'lệch' if sas_a != sas_b else 'khớp'}, chữ ký giả {'bị từ chối' if not ky_gia else 'được nhận'}")
    ok = sas_ok and sas_a != sas_b and ky_that and not ky_gia
    return "DH + SAS + chữ ký, có/không Mallory", "Không: OK. Có: SAS lệch, ABORT", thuc_te, ok


def bang_tc():
    tieu_de("1. BẢNG CA TỰ VIẾT TC1-TC5")
    hang("Ca", "Đầu vào", "Mong đợi", "Thực tế", "Kết quả", rong=(4, 40, 28, 52, 6))
    print("-" * 78)
    for ten, f in (("TC1", tc1), ("TC2", tc2), ("TC3", tc3), ("TC4", tc4), ("TC5", tc5)):
        dau_vao, mong_doi, thuc_te, ok = f()
        hang(ten, dau_vao, mong_doi, thuc_te, ghi(ok), rong=(4, 40, 28, 52, 6))


# ---------------------------------------------------------------- 2. mod_exp vs pow()
def doi_chieu_pow():
    tieu_de("2. ĐỐI CHIẾU mod_exp VỚI pow() (pow chỉ dùng trong tests/)")
    for bits, so_bo in ((8, 1000), (64, 1000), (512, 300), (2048, 100)):
        khop = 0
        for _ in range(so_bo):
            m = random.getrandbits(bits) | (1 << (bits - 1)) | 1
            base, e = random.getrandbits(bits + 8), random.getrandbits(bits)
            khop += dh.mod_exp(base, e, m) == pow(base, e, m)
        print(f"  mod_exp vs pow, {bits:>4} bit: {khop}/{so_bo} bộ số khớp   [{ghi(khop == so_bo)}]")
    ca_bien = [(5, 0, 7), (0, 5, 7), (0, 0, 7), (10, 3, 1), (-3, 3, 7), (100, 5, 7)]
    khop = sum(dh.mod_exp(*t) == pow(*t) for t in ca_bien)
    print(f"  mod_exp vs pow, ca biên (exp=0, base=0, mod=1, base âm, base>mod): {khop}/{len(ca_bien)}   [{ghi(khop == len(ca_bien))}]")


def doi_chieu_khac():
    tieu_de("3. ĐỐI CHIẾU KHÁC")
    sai = [n for n in range(0, 3000) if dh.is_prime_miller_rabin(n) != sympy.isprime(n)]
    print(f"  Miller-Rabin vs sympy.isprime, n = 0..2999: {3000 - len(sai)}/3000 khớp   [{ghi(not sai)}]")
    carmichael = [561, 1105, 1729]
    ok = all(not dh.is_prime_miller_rabin(n) for n in carmichael) and dh.is_prime_miller_rabin(2**61 - 1)
    print(f"  Số Carmichael {carmichael} là hợp số, 2^61-1 là nguyên tố: {ok}   [{ghi(ok)}]")
    khop = 0
    for _ in range(100):
        n = random.getrandbits(64) | (1 << 63) | 1
        khop += dh.is_prime_miller_rabin(n) == sympy.isprime(n)
    print(f"  Miller-Rabin vs sympy, 100 số ngẫu nhiên 64 bit: {khop}/100 khớp   [{ghi(khop == 100)}]")
    mau = [bytes(random.getrandbits(8) for _ in range(n)) for n in (0, 1, 55, 56, 63, 64, 65, 120, 1000)]
    mau += [b"abc", "Xin chào, Việt Nam".encode()]
    khop = sum(dh.custom_sha256_bytes(d) == hashlib.sha256(d).digest() for d in mau)
    print(f"  SHA-256 tự cài vs hashlib, {len(mau)} mẫu (biên khối 55/56/63/64/65): {khop}/{len(mau)} khớp   [{ghi(khop == len(mau))}]")
    p, g = dh.gen_params(16)
    q = (p - 1) // 2
    ok = sympy.isprime(p) and sympy.isprime(q) and dh.la_can_nguyen_thuy(p, g) is True
    print(f"  gen_params(16): p={p}, g={g}, q=(p-1)/2={q}; p và q nguyên tố, g căn nguyên thuỷ: {ok}   [{ghi(ok)}]")


# ---------------------------------------------------------------- 4. RFC 3526
def kiem_tra_rfc():
    tieu_de("4. KIỂM TRA p NHÓM 14 RFC 3526 (2048 bit, g = 2)")
    P, G = dh.RFC_3526_2048_P, dh.RFC_3526_2048_G
    ok = P.bit_length() == 2048
    print(f"  p dài đúng 2048 bit (thực tế {P.bit_length()}): {ok}   [{ghi(ok)}]")
    ok = dh.is_prime_miller_rabin(P, 5) and sympy.isprime(P)
    print(f"  is_prime(p) (Miller-Rabin của nhóm và sympy): {ok}   [{ghi(ok)}]")
    q = (P - 1) // 2
    ok = dh.is_prime_miller_rabin(q, 5) and sympy.isprime(q)
    print(f"  (p-1)/2 cũng nguyên tố (safe prime): {ok}   [{ghi(ok)}]")
    mpmath.mp.prec = 2300
    phan_pi = int(mpmath.floor(mpmath.mpf(2) ** 1918 * mpmath.pi))
    ok = P == 2**2048 - 2**1984 - 1 + 2**64 * (phan_pi + 124476)
    print(f"  p khớp công thức RFC: 2^2048 - 2^1984 - 1 + 2^64*(floor(2^1918*pi)+124476): {ok}   [{ghi(ok)}]")
    a, b = random.getrandbits(256) | 1, random.getrandbits(256) | 1
    A, B = dh.mod_exp(G, a, P), dh.mod_exp(G, b, P)
    ok = dh.mod_exp(B, a, P) == dh.mod_exp(A, b, P) and dh.validate_pub(A, P, q)
    print(f"  Phiên DH trọn vẹn với (p, g=2): hai bên cùng khoá, khoá công khai hợp lệ: {ok}   [{ghi(ok)}]")


# ---------------------------------------------------------------- 5. TÍNH TAY
def tinh_tay():
    tieu_de("5. TÍNH TAY SO VỚI CHƯƠNG TRÌNH (p = 23, g = 5)")
    hang("Đại lượng", "Tính tay", "Chương trình", "Kết quả", rong=(30, 12, 14, 6))
    print("-" * 78)
    p, g = 23, 5
    muc = [
        ("A = 5^6 mod 23", 8, dh.mod_exp(g, 6, p)),
        ("B = 5^15 mod 23", 19, dh.mod_exp(g, 15, p)),
        ("Khoá chung = 19^6 mod 23", 2, dh.mod_exp(19, 6, p)),
        ("M = 5^3 mod 23 (Mallory, c=3)", 10, dh.mod_exp(g, 3, p)),
        ("Alice-Mallory = 10^6 mod 23", 6, dh.mod_exp(10, 6, p)),
        ("Bob-Mallory = 10^15 mod 23", 5, dh.mod_exp(10, 15, p)),
        ("a: tìm x để 5^x mod 23 = 8", 6, next((x for x in range(1, p) if dh.mod_exp(g, x, p) == 8), None)),
    ]
    for ten, tay, ct in muc:
        hang(ten, tay, ct, ghi(tay == ct), rong=(30, 12, 14, 6))
    _, steps = dh.mod_exp(5, 6, 23, return_steps=True)
    cb = [s["curr_base"] for s in steps]
    kq = [s["result_so_far"] for s in steps]
    ok = cb == [5, 2, 4] and kq == [1, 2, 8]
    print(f"  Từng bước 5^6 mod 23 (6 = 110 nhị phân): bình phương {cb}, kết quả {kq}   [{ghi(ok)}]")
    print("  Lưu ý: dòng 'a = 6' kiểm tra bằng cách thử lần lượt g^x, không phải BSGS (BSGS nằm ở core/dlog.py, có test riêng).")


# ---------------------------------------------------------------- MAIN
def main():
    bat_dau = time.time()
    print("BÁO CÁO KIỂM THỬ DIFFIE-HELLMAN")
    print(time.strftime("Chạy lúc: %Y-%m-%d %H:%M:%S"))
    bang_tc()
    doi_chieu_pow()
    doi_chieu_khac()
    kiem_tra_rfc()
    tinh_tay()
    dat, tong = sum(results), len(results)
    tieu_de("TỔNG KẾT")
    print(f"  {dat}/{tong} đạt  ({'TẤT CẢ ĐẠT' if dat == tong else str(tong - dat) + ' MỤC LỖI'})   [{time.time() - bat_dau:.1f} giây]")
    return 0 if dat == tong else 1


if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "test_log.txt"), "w", encoding="utf-8") as f:
        goc = sys.stdout
        sys.stdout = Tee(goc, f)
        try:
            ma = main()
        finally:
            sys.stdout = goc
    sys.exit(ma)
