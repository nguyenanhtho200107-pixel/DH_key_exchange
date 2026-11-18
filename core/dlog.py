# File: core/dlog.py
"""
Cài đặt các thuật toán giải bài toán Logarit rời rạc (Discrete Logarithm Problem - DLP):
Tìm số mũ x sao cho: g^x ≡ h (mod p).
"""
import math
import time

from core.dh import mod_exp
from core.stream import encrypt_text_hex, decrypt_text_hex


def dlog_bruteforce(g: int, h: int, p: int, limit: int = 10**6):
    """1. Thuật toán vét cạn: thử lần lượt x = 0, 1, 2, ... cho đến khi g^x ≡ h (mod p)."""
    cur = 1
    g_mod = g % p
    target = h % p
    max_steps = min(p, limit)
    for x in range(max_steps):
        if cur == target:
            return x
        cur = (cur * g_mod) % p
    return None


def dlog_bsgs(g: int, h: int, p: int, order: int = None):
    """2. Thuật toán Baby-Step Giant-Step (BSGS - Shanks)."""
    g_mod = g % p
    h_mod = h % p

    if h_mod == 1:
        return 0
    if g_mod == 0 or math.gcd(g_mod, p) != 1:
        return None

    n = order if order is not None else (p - 1)
    m = math.isqrt(n) + 1

    baby_table = {}
    cur = 1
    for j in range(m):
        if cur not in baby_table:
            baby_table[cur] = j
        cur = (cur * g_mod) % p

    g_inv = pow(g_mod, -1, p)
    g_inv_m = mod_exp(g_inv, m, p)

    gamma = h_mod
    for i in range(m):
        if gamma in baby_table:
            x = i * m + baby_table[gamma]
            if mod_exp(g_mod, x, p) == h_mod:
                return x
        gamma = (gamma * g_inv_m) % p
    return None


def _factorize(n: int):
    """Phân tích n ra thừa số nguyên tố."""
    factors = []
    d = 2
    while d * d <= n:
        if n % d == 0:
            cnt = 0
            while n % d == 0:
                n //= d
                cnt += 1
            factors.append((d, cnt))
        d += 1 if d == 2 else 2
    if n > 1:
        factors.append((n, 1))
    return factors


def crt_solve(remainders, moduli):
    """Định lý số dư Trung Hoa (CRT)."""
    M = 1
    for m_i in moduli:
        M *= m_i
    x = 0
    for r_i, m_i in zip(remainders, moduli):
        M_i = M // m_i
        y_i = pow(M_i, -1, m_i)
        x = (x + r_i * M_i * y_i) % M
    return x


def dlog_pohlig_hellman(g: int, h: int, p: int):
    """3. Thuật toán Pohlig-Hellman."""
    n = p - 1
    factors = _factorize(n)
    remainders = []
    moduli = []

    for q, e in factors:
        q_e = q ** e
        g_i = mod_exp(g, n // q_e, p)
        h_i = mod_exp(h, n // q_e, p)
        x_i = dlog_bsgs(g_i, h_i, p, order=q_e)
        if x_i is None:
            return None
        remainders.append(x_i)
        moduli.append(q_e)

    return crt_solve(remainders, moduli)


def demo_eve_crack():
    print("\n" + "=" * 68)
    print(" DEMO 7A: EVE BẺ KHÓA DIFFIE-HELLMAN (p ~ 32-bit) BẰNG BSGS")
    print("=" * 68)
    p = 3221225479
    g = 5
    a_alice = 123456789
    b_bob = 987654321

    A = mod_exp(g, a_alice, p)
    B = mod_exp(g, b_bob, p)
    K_chung = mod_exp(B, a_alice, p)

    tin_goc = "Mat khau kho du lieu: NEU_2026_SECRET"
    ban_ma_hex = encrypt_text_hex(tin_goc, K_chung)

    print("  [Bước 1] Eve thu thập tham số công khai và bản mã.")
    print(f"           Bản mã (Hex) = {ban_ma_hex}")

    t0 = time.perf_counter()
    a_eve = dlog_bsgs(g, A, p)
    dt = time.perf_counter() - t0
    print(f"  [Bước 2] Tìm ra khóa riêng: a = {a_eve} (Thời gian: {dt:.4f}s)")

    K_eve = mod_exp(B, a_eve, p)
    tin_eve_doc = decrypt_text_hex(ban_ma_hex, K_eve)
    print(f"  [Bước 3] Giải mã thành công: '{tin_eve_doc}'")


def demo_pohlig_hellman_compare():
    print("\n" + "=" * 68)
    print(" DEMO 7B: SO SÁNH POHLIG-HELLMAN GIỮA (p-1) TRƠN VÀ SAFE PRIME")
    print("=" * 68)

    p_smooth = 1082601054151
    g_smooth = 7
    a_secret = 456789123
    A_smooth = mod_exp(g_smooth, a_secret, p_smooth)

    p_safe = 549755815199
    g_safe = 13
    A_safe = mod_exp(g_safe, a_secret, p_safe)

    t0 = time.perf_counter()
    res_smooth = dlog_pohlig_hellman(g_smooth, A_smooth, p_smooth)
    time_smooth = time.perf_counter() - t0

    t1 = time.perf_counter()
    res_safe = dlog_pohlig_hellman(g_safe, A_safe, p_safe)
    time_safe = time.perf_counter() - t1

    print(f"  1. p trơn (Smooth) thời gian : {time_smooth:.6f}s (a = {res_smooth})")
    print(f"  2. Safe Prime time          : {time_safe:.6f}s (a = {res_safe})")


if __name__ == "__main__":
    demo_eve_crack()
    demo_pohlig_hellman_compare()
