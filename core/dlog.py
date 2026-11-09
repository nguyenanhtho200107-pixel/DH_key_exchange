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
    """
    1. Thuật toán vét cạn: thử lần lượt x = 0, 1, 2, ... cho đến khi g^x ≡ h (mod p).
    """
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
    """
    2. Thuật toán Baby-Step Giant-Step (BSGS - Shanks):
    Đặt m = ceil(√n) và viết x = i*m + j (với 0 <= i, j < m).
    g^(i*m + j) ≡ h (mod p) <=> g^j ≡ h * (g^(-m)) ^ i (mod p).
    Độ phức tạp: O(√p) thời gian và O(√p) bộ nhớ.
    """
    if math.gcd(g % p, p) != 1:      # g không khả nghịch mod p thì không có logarit
        return None
    n = order if order is not None else (p - 1)
    m = math.isqrt(n) + 1

    # Baby-step: Lưu bảng băm {g^j mod p : j}
    baby_table = {}
    cur = 1
    g_mod = g % p
    for j in range(m):
        if cur not in baby_table:
            baby_table[cur] = j
        cur = (cur * g_mod) % p

    # Tính nghịch đảo mô-đun g^(-m) mod p
    g_inv = pow(g, -1, p)
    g_inv_m = mod_exp(g_inv, m, p)

    # Giant-step: Tìm va chạm trong bảng
    gamma = h % p
    for i in range(m):
        if gamma in baby_table:
            x = i * m + baby_table[gamma]
            if mod_exp(g, x, p) == (h % p):
                return x
        gamma = (gamma * g_inv_m) % p
    return None

def _factorize(n: int):
    """Phân tích n ra thừa số nguyên tố: trả về danh sách [(q_i, e_i), ...]."""
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
    """
    Định lý số dư Trung Hoa (Chinese Remainder Theorem - CRT):
    Giải hệ phương trình đồng dư x ≡ r_i (mod m_i).
    """
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
    """
    3. Thuật toán Pohlig-Hellman:
    Khai thác trường hợp p - 1 trơn (smooth), chia bài toán lớn về các nhóm con cấp q_i^e_i,
    giải bằng BSGS rồi ghép nghiệm bằng CRT.
    """
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
    """
    Demo 'Eve bẻ khóa' (p ~ 32-bit): Eve chỉ thấy (p, g, A, B) và bản mã,
    chạy BSGS tìm ra a, tính khóa chung K và giải mã tin nhắn.
    """
    print("\n" + "=" * 68)
    print(" DEMO 7A: EVE BẺ KHÓA DIFFIE-HELLMAN (p ~ 32-BIT) BẰNG BSGS")
    print("=" * 68)
    p = 3221225479  # Số nguyên tố 32-bit
    g = 5
    a_alice = 123456789
    b_bob = 987654321

    A = mod_exp(g, a_alice, p)
    B = mod_exp(g, b_bob, p)
    K_chung = mod_exp(B, a_alice, p)

    tin_goc = "Mat khau kho du lieu: NEU_2026_SECRET"
    ban_ma_hex = encrypt_text_hex(tin_goc, K_chung)

    print(f"  [Bước 1] Eve nghe lén trên mạng thu được các tham số công khai:")
    print(f"           p = {p} ({p.bit_length()} bit), g = {g}")
    print(f"           A = {A}, B = {B}")
    print(f"           Bản mã (Hex) = {ban_ma_hex}")

    print(f"\n  [Bước 2] Eve chạy thuật toán Baby-Step Giant-Step (BSGS) giải {g}^a ≡ {A} (mod {p})...")
    t0 = time.perf_counter()
    a_eve = dlog_bsgs(g, A, p)
    dt = time.perf_counter() - t0
    print(f"           -> Tìm ra khóa riêng của Alice: a = {a_eve} (Khớp: {a_eve == a_alice})")
    print(f"           -> Thời gian chạy BSGS        : {dt:.4f} giây")

    K_eve = mod_exp(B, a_eve, p)
    tin_eve_doc = decrypt_text_hex(ban_ma_hex, K_eve)
    print(f"\n  [Bước 3] Eve tính khóa chung K = B^a mod p = {K_eve}")
    print(f"  [Bước 4] Eve giải mã bản mã thu được bản rõ: '{tin_eve_doc}'")

def demo_pohlig_hellman_compare():
    """
    Demo Pohlig-Hellman: So sánh thời gian bẻ khóa giữa p có (p-1) trơn và Safe Prime
    (cùng cỡ 40-bit, cùng khóa riêng a).
    """
    print("\n" + "=" * 68)
    print(" DEMO 7B: SO SÁNH POHLIG-HELLMAN GIỮA (p-1) TRƠN VÀ SAFE PRIME")
    print("=" * 68)

    # p nguyên tố 40-bit, p - 1 = 2 * 3 * 5^2 * 7 * 11^2 * 17 * 19 * 23 * 31 * 37 (rất trơn); g = 7 là căn nguyên thủy
    p_smooth = 1082601054151
    g_smooth = 7
    a_secret = 456789123
    A_smooth = mod_exp(g_smooth, a_secret, p_smooth)

    # Safe Prime 40-bit: p = 2q + 1 với q = 274877907599 nguyên tố; g = 13 là căn nguyên thủy
    p_safe = 549755815199
    g_safe = 13
    A_safe = mod_exp(g_safe, a_secret, p_safe)

    t0 = time.perf_counter()
    res_smooth = dlog_pohlig_hellman(g_smooth, A_smooth, p_smooth)
    time_smooth = time.perf_counter() - t0

    t1 = time.perf_counter()
    res_safe = dlog_pohlig_hellman(g_safe, A_safe, p_safe)
    time_safe = time.perf_counter() - t1

    ok_smooth = res_smooth is not None and mod_exp(g_smooth, res_smooth, p_smooth) == A_smooth
    ok_safe = res_safe is not None and mod_exp(g_safe, res_safe, p_safe) == A_safe

    print(f"  {'Trường hợp khảo sát':<30} | {'Giá trị p':<14} | {'Thời gian (giây)':<18} | {'Khóa tìm được'}")
    print("  " + "-" * 82)
    print(f"  {'1. p có (p-1) trơn (Smooth)':<30} | {p_smooth:<14} | {time_smooth:<18.6f} | a = {res_smooth} ({'đúng' if ok_smooth else 'SAI'})")
    print(f"  {'2. Safe Prime (p = 2q + 1)':<30} | {p_safe:<14} | {time_safe:<18.6f} | a = {res_safe} ({'đúng' if ok_safe else 'SAI'})")
    ti_le = time_safe / time_smooth if time_smooth > 0 else float('inf')
    print(f"\n  => Safe prime chậm hơn p có (p-1) trơn khoảng {ti_le:,.0f} lần (cùng cỡ 40-bit).")
    print("     Khi (p-1) trơn, Pohlig-Hellman bẻ khóa gần như tức thì; vì vậy DH phải dùng Safe Prime.")
    print("     Lưu ý: p chỉ 40-bit nên safe prime vẫn bị bẻ trong chưa đầy 1 giây; thực tế cần p >= 2048-bit.")
