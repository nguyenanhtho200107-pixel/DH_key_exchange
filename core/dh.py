import math
import secrets

# Các Hàm Toán Học

def mod_exp(base: int, exp: int, mod: int, return_steps: bool = False):
    """Tính (base^exp) % mod bằng thuật toán bình phương và nhân liên tiếp."""
    if mod <= 0 or exp < 0:
        raise ValueError("Modulo p phải > 0 và exp >= 0.")
    result = 1
    curr_base = base % mod
    temp_exp = exp
    steps = []
    step_idx = 0
    while temp_exp > 0:
        bit = temp_exp & 1
        if bit == 1:
            result = (result * curr_base) % mod
        steps.append({"step": step_idx, "bit": bit, "curr_base": curr_base, "result_so_far": result})
        curr_base = (curr_base * curr_base) % mod
        temp_exp >>= 1
        step_idx += 1
    return (result, steps) if return_steps else result


def custom_sha256_bytes(data: bytes) -> bytes:
    """Tự cài đặt thuật toán băm SHA-256 từ đầu bằng Python thuần."""
    H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
    K = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    ]
    length = len(data) * 8
    data += b'\x80'
    while (len(data) * 8) % 512 != 448:
        data += b'\x00'
    data += length.to_bytes(8, byteorder='big')

    for i in range(0, len(data), 64):
        chunk = data[i:i+64]
        w = [int.from_bytes(chunk[j:j+4], 'big') for j in range(0, 64, 4)] + [0] * 48
        for j in range(16, 64):
            s0 = ((w[j-15] >> 7) | (w[j-15] << 25)) ^ ((w[j-15] >> 18) | (w[j-15] << 14)) ^ (w[j-15] >> 3)
            s1 = ((w[j-2] >> 17) | (w[j-2] << 15)) ^ ((w[j-2] >> 19) | (w[j-2] << 13)) ^ (w[j-2] >> 10)
            w[j] = (w[j-16] + s0 + w[j-7] + s1) & 0xFFFFFFFF

        a, b, c, d, e, f, g, h = H
        for j in range(64):
            S1 = ((e >> 6) | (e << 26)) ^ ((e >> 11) | (e << 21)) ^ ((e >> 25) | (e << 7))
            ch = (e & f) ^ ((~e) & g)
            temp1 = (h + S1 + ch + K[j] + w[j]) & 0xFFFFFFFF
            S0 = ((a >> 2) | (a << 30)) ^ ((a >> 13) | (a << 19)) ^ ((a >> 22) | (a << 10))
            maj = (a & b) ^ (a & c) ^ (b & c)
            temp2 = (S0 + maj) & 0xFFFFFFFF

            h, g, f = g, f, e
            e = (d + temp1) & 0xFFFFFFFF
            d, c, b = c, b, a
            a = (temp1 + temp2) & 0xFFFFFFFF

        H = [(x + y) & 0xFFFFFFFF for x, y in zip(H, [a, b, c, d, e, f, g, h])]

    return b''.join(x.to_bytes(4, 'big') for x in H)


#  Kiểm Tra Tham Số, Sinh Số Tham Số, Nhóm RFC 3526


def is_prime_miller_rabin(n: int, k: int = 15) -> bool:
    """Kiểm tra số nguyên tố bằng Miller-Rabin (cơ số ngẫu nhiên từ secrets)."""
    if n <= 1: return False
    if n <= 3: return True
    if n % 2 == 0: return False
    r, d = 0, n - 1
    while d % 2 == 0:
        r += 1
        d //= 2
    for _ in range(k):
        a = 2 + secrets.randbelow(n - 3)          # a thuộc [2, n-2]
        x = mod_exp(a, d, n)
        if x == 1 or x == n - 1: continue
        for _ in range(r - 1):
            x = mod_exp(x, 2, n)
            if x == n - 1: break
        else: return False
    return True


def validate_pub(y: int, p: int, q: int = None) -> bool:
    """Kiểm tra khoá công khai y.
    - Luôn chặn y ngoài [2, p-2] (loại 0, 1, p-1, ...).
    - Nếu truyền q (bậc của nhóm con mà g sinh ra) thì kiểm tra thêm y^q = 1 (mod p)
      để chặn tấn công nhóm con nhỏ. Khi g là căn nguyên thuỷ (bậc p-1) thì KHÔNG
      truyền q, vì khi đó mọi y trong [2, p-2] đều hợp lệ (ví dụ p=23, g=5, B=19)."""
    if y < 2 or y > p - 2:
        return False
    if q is not None and mod_exp(y, q, p) != 1:
        return False
    return True


def validate_dh_params(p: int, g: int) -> bool:
    """Kiểm tra p nguyên tố và g nằm trong (1, p)."""
    if not is_prime_miller_rabin(p):
        print(" -> Lỗi: p không phải là số nguyên tố!")
        return False
    if g <= 1 or g >= p:
        print(" -> Lỗi: Cơ số g phải thuộc khoảng (1, p)!")
        return False
    return True


def find_generator(p: int) -> int:
    """Tìm căn nguyên thuỷ g mod p (phân tích p-1 bằng chia thử, chỉ phù hợp p nhỏ)."""
    if p == 2: return 1
    phi = p - 1
    factors, n, d = [], phi, 2
    while d * d <= n:
        if n % d == 0:
            factors.append(d)
            while n % d == 0: n //= d
        d += 1
    if n > 1: factors.append(n)
    for g in range(2, p):
        if all(mod_exp(g, phi // q, p) != 1 for q in factors):
            return g
    return -1


def gen_params(bits: int = 16) -> tuple[int, int]:
    """Sinh safe prime p = 2q + 1 (q nguyên tố) và căn nguyên thuỷ g."""
    while True:
        q = secrets.randbits(bits - 1) | (1 << (bits - 2)) | 1
        if is_prime_miller_rabin(q):
            p = 2 * q + 1
            if is_prime_miller_rabin(p):
                g = find_generator(p)
                if g != -1: return p, g


# p của nhóm 14 trong RFC 3526 (2048 bit), g = 2.
# p = 2^2048 - 2^1984 - 1 + 2^64 * ( floor(2^1918 * pi) + 124476 )
RFC_3526_2048_P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E08"
    "8A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B"
    "302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9"
    "A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE6"
    "49286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8"
    "FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C"
    "180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF695581718"
    "3995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFF"
    "FFFFFFFF", 16)
RFC_3526_2048_G = 2


# Toán Tử Cho SAS Và Chữ Ký Số

def sas_code(A: int, B: int, K: int) -> str:
    """Mã xác thực ngắn (SAS, 4 ký tự hex) = SHA-256 của (A, B, K) mà MỘT bên nhìn thấy."""
    return custom_sha256_bytes(f"{A}|{B}|{K}".encode()).hex()[:4].upper()


def rsa_keygen(bits: int = 64):
    """RSA đồ chơi để ký giá trị DH. KHÔNG dùng trong thực tế (khoá quá nhỏ)."""
    def rand_prime():
        while True:
            c = secrets.randbits(bits // 2) | (1 << (bits // 2 - 1)) | 1
            if is_prime_miller_rabin(c): return c
    e = 65537
    while True:
        p, q = rand_prime(), rand_prime()
        phi = (p - 1) * (q - 1)
        if p != q and math.gcd(e, phi) == 1:
            return (p * q, e), (p * q, pow(e, -1, phi))     # (khoá công khai), (khoá riêng)


def _digest_int(msg: str, n: int) -> int:
    return int.from_bytes(custom_sha256_bytes(msg.encode()), 'big') % n


def rsa_sign(msg: str, priv) -> int:
    n, d = priv
    return mod_exp(_digest_int(msg, n), d, n)


def rsa_verify(msg: str, sig: int, pub) -> bool:
    n, e = pub
    return mod_exp(sig, e, n) == _digest_int(msg, n)


#  Nhập Tham Số


# Bộ mặc định = ví dụ ở mục 4.2 của báo cáo (bỏ trống rồi bấm Enter để dùng).
MAC_DINH = {"p": 23, "g": 5, "a": 6, "b": 15, "c": 3}

# Chỉ phân tích p-1 bằng chia thử khi p đủ nhỏ (căn bậc hai <= 10^6).
GIOI_HAN_PHAN_TICH = 10 ** 12


class NguoiDungThoat(Exception):
    """Người dùng bấm Ctrl+C / Ctrl+D hoặc hết dữ liệu nhập."""


def doc_dong(loi_nhac: str) -> str:
    """input() an toàn: Ctrl+C, Ctrl+D hoặc hết dữ liệu thì thoát gọn, không báo lỗi."""
    try:
        return input(loi_nhac)
    except (EOFError, KeyboardInterrupt):
        print()
        raise NguoiDungThoat()


def hoi_so_nguyen(nhan: str, mac_dinh: int = None, toi_thieu: int = None, toi_da: int = None) -> int:
    """Hỏi một số nguyên trong [toi_thieu, toi_da]; nhập sai thì hỏi lại.
    Bỏ trống = lấy giá trị mặc định (nếu mặc định nằm trong khoảng cho phép)."""
    if mac_dinh is not None and ((toi_thieu is not None and mac_dinh < toi_thieu)
                                 or (toi_da is not None and mac_dinh > toi_da)):
        print(f" (Giá trị mặc định {mac_dinh} nằm ngoài khoảng cho phép với tham số hiện tại, hãy nhập số khác)")
        mac_dinh = None
    khoang = ""
    if toi_thieu is not None and toi_da is not None:
        khoang = f" ({toi_thieu} đến {toi_da})"
    goi_y = f" [Enter = {mac_dinh}]" if mac_dinh is not None else ""
    while True:
        s = doc_dong(f"{nhan}{khoang}{goi_y}: ").strip()
        if s == "" and mac_dinh is not None:
            return mac_dinh
        try:
            v = int(s)
        except ValueError:
            print(" -> Lỗi: phải nhập một số nguyên!")
            continue
        if toi_thieu is not None and v < toi_thieu:
            print(f" -> Lỗi: giá trị phải >= {toi_thieu}!")
            continue
        if toi_da is not None and v > toi_da:
            print(f" -> Lỗi: giá trị phải <= {toi_da}!")
            continue
        return v


def la_can_nguyen_thuy(p: int, g: int):
    """True/False nếu g là căn nguyên thuỷ mod p; None nếu p quá lớn để phân tích p-1."""
    if p > GIOI_HAN_PHAN_TICH:
        return None
    n, d, factors = p - 1, 2, []
    while d * d <= n:
        if n % d == 0:
            factors.append(d)
            while n % d == 0:
                n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return all(mod_exp(g, (p - 1) // q, p) != 1 for q in factors)


def canh_bao_tham_so(p: int, g: int) -> list:
    """In cảnh báo tham số yếu (không chặn chương trình). Trả về danh sách cảnh báo."""
    ds = []
    if p.bit_length() < 2048:
        ds.append(f"p chỉ {p.bit_length()} bit (< 2048): đủ để học, KHÔNG an toàn trong thực tế (NIST khuyến nghị >= 2048 bit).")
    if p > 3 and not is_prime_miller_rabin((p - 1) // 2):
        ds.append("p không phải safe prime (p = 2q + 1 với q nguyên tố): dễ bị tấn công Pohlig-Hellman nếu p-1 chỉ có ước nguyên tố nhỏ.")
    kq = la_can_nguyen_thuy(p, g)
    if kq is False:
        ds.append(f"g = {g} không phải căn nguyên thuỷ mod {p}: các luỹ thừa của g chỉ phủ một phần nhóm, không gian khoá nhỏ hơn p-1.")
    elif kq is None:
        ds.append("p quá lớn nên bỏ qua việc kiểm tra g có phải căn nguyên thuỷ hay không.")
    for s in ds:
        print(f" ⚠ Cảnh báo: {s}")
    return ds


def nhap_tham_so_dh(can_mallory: bool = False):
    """Nhập p, g, a, b (và c của Mallory nếu can_mallory=True).
    Khoá bí mật phải nằm trong [2, p-2] (a=0, 1 hoặc p-1 cho khoá công khai/khoá chung yếu).
    Trả về (p, g, a, b, c), hoặc None nếu p/g không hợp lệ."""
    p = hoi_so_nguyen("Nhập mod p", MAC_DINH["p"], 2)
    g = hoi_so_nguyen("Nhập cơ số g", MAC_DINH["g"], 2)
    if not validate_dh_params(p, g):
        return None
    if p < 5:
        print(" -> Lỗi: p phải >= 5 để có khoá bí mật nằm trong [2, p-2]!")
        return None
    canh_bao_tham_so(p, g)
    a = hoi_so_nguyen("Nhập khoá bí mật Alice (a)", MAC_DINH["a"], 2, p - 2)
    b = hoi_so_nguyen("Nhập khoá bí mật Bob (b)", MAC_DINH["b"], 2, p - 2)
    c = hoi_so_nguyen("Nhập khoá bí mật Mallory (c)", MAC_DINH["c"], 2, p - 2) if can_mallory else None
    return p, g, a, b, c


# Mô Phỏng Tấn Công MITM

def run_mitm_simulation(p: int, g: int, a: int, b: int, c: int):
    """In mô phỏng MITM và TRẢ VỀ (K_alice, K_bob, K_mal_alice, K_mal_bob) để CLI dùng tiếp."""
    print("\n" + "=" * 50)
    print("MÔ PHỎNG TẤN CÔNG MAN-IN-THE-MIDDLE")
    print("=" * 50)
    A, B = mod_exp(g, a, p), mod_exp(g, b, p)
    M = mod_exp(g, c, p)                             # Mallory dùng cùng M cho cả hai phía

    K_alice = mod_exp(M, a, p)                       # Alice nhận M thay cho B
    K_bob = mod_exp(M, b, p)                         # Bob nhận M thay cho A
    K_mal_alice = mod_exp(A, c, p)                   # Mallory tính khoá với Alice
    K_mal_bob = mod_exp(B, c, p)                     # Mallory tính khoá với Bob

    print(f"Tham số công khai: p = {p}, g = {g}")
    print(f"Alice (a={a}) gửi A = {A} | Bob (b={b}) gửi B = {B}")
    print(f"Mallory (c={c}) chặn cả hai và gửi M = g^c = {M} cho mỗi bên")
    if not validate_pub(M, p):
        print(f"Lưu ý: M = {M} nằm ngoài [2, p-2], bên nào có validate_pub sẽ từ chối M ngay.")
    print(f"- Alice tính K = M^a = {K_alice}   | Mallory tính A^c = {K_mal_alice}  -> {'KHỚP' if K_alice == K_mal_alice else 'LỆCH'}")
    print(f"- Bob   tính K = M^b = {K_bob}   | Mallory tính B^c = {K_mal_bob}  -> {'KHỚP' if K_bob == K_mal_bob else 'LỆCH'}")
    if K_alice != K_bob:
        print(f"=> Alice và Bob giữ hai khoá KHÁC nhau ({K_alice} và {K_bob}), Mallory nắm cả hai và đọc/sửa tin được.")
    else:
        print(f"=> Hai khoá tình cờ TRÙNG nhau ({K_alice}) do tham số quá nhỏ/đặc biệt, nhưng Mallory vẫn biết khoá này.")
    return K_alice, K_bob, K_mal_alice, K_mal_bob



# Mô Phỏng Phòng Thủ: SAS Và Chữ Ký Số


def run_defense_simulation(p: int, g: int, a: int, b: int, c: int):
    A, B = mod_exp(g, a, p), mod_exp(g, b, p)
    M = mod_exp(g, c, p)

    print("\n" + "=" * 50)
    print("PHÒNG THỦ 1: SO KHỚP MÃ SAS")
    print("=" * 50)
    K = mod_exp(B, a, p)
    print(f"[Không có Mallory] Alice thấy (A={A}, B={B}, K={K}) -> SAS = {sas_code(A, B, K)}")
    print(f"                   Bob   thấy (A={A}, B={B}, K={K}) -> SAS = {sas_code(A, B, K)}  => KHỚP")
    K_alice, K_bob = mod_exp(M, a, p), mod_exp(M, b, p)
    sas_a = sas_code(A, M, K_alice)                  # Alice thấy B bị đổi thành M
    sas_b = sas_code(M, B, K_bob)                    # Bob thấy A bị đổi thành M
    print(f"[Có Mallory]       Alice thấy (A={A}, B={M}, K={K_alice}) -> SAS = {sas_a}")
    print(f"                   Bob   thấy (A={M}, B={B}, K={K_bob}) -> SAS = {sas_b}  => {'KHỚP' if sas_a == sas_b else 'LỆCH, phát hiện MITM'}")

    print("\n" + "=" * 50)
    print("PHÒNG THỦ 2: CHỮ KÝ SỐ (RSA đồ chơi 64 bit)")
    print("=" * 50)
    pub_a, priv_a = rsa_keygen()
    sig_A = rsa_sign(f"DH-pub:{A}", priv_a)
    ok_that = rsa_verify(f"DH-pub:{A}", sig_A, pub_a)
    ok_gia = rsa_verify(f"DH-pub:{M}", sig_A, pub_a)
    print(f"Alice ký A = {A} bằng khoá riêng; Bob đã biết khoá công khai của Alice.")
    print(f"[Không có Mallory] Bob kiểm tra chữ ký của A = {A}: {ok_that}")
    print(f"[Có Mallory]       Mallory đổi A thành M = {M} nhưng không thể ký lại.")
    if ok_gia:
        print(f"                   Bob kiểm tra (M = {M}, chữ ký cũ): {ok_gia}  -> M trùng A nên thực chất không có gì bị thay đổi")
    else:
        print(f"                   Bob kiểm tra (M = {M}, chữ ký cũ): {ok_gia}  -> từ chối, phát hiện MITM")



# Input


def kiem_tra_khoa_cong_khai(ten: str, y: int, p: int) -> bool:
    """In kết quả validate_pub; nếu không hợp lệ thì giải thích vì sao phải dừng."""
    ok = validate_pub(y, p)
    print(f"   => Validate {ten}: {ok}")
    if not ok:
        print(f"   => Lỗi: khoá công khai {ten} = {y} nằm ngoài [2, p-2] nên khoá chung bị lộ (ai cũng đoán được).")
    return ok


def nhap_tay_truc_tiep():
    print("\n" + "=" * 50)
    print("NHẬP THAM SỐ TRAO ĐỔI KHOÁ DIFFIE-HELLMAN")
    print("=" * 50)

    tham_so = nhap_tham_so_dh()
    if tham_so is None:
        return
    p, co_so, mu_a, mu_b, _ = tham_so

    print("\n--- QUÁ TRÌNH TÍNH TOÁN CHI TIẾT ---")

    a_pub, steps_a = mod_exp(co_so, mu_a, p, return_steps=True)
    print(f"\n1. Alice tính A = g^a mod p = {co_so}^{mu_a} mod {p}:")
    for st in steps_a:
        print(f"   - Vòng {st['step']}: Bit={st['bit']} | Lũy thừa={st['curr_base']} | Kết quả={st['result_so_far']}")
    print(f"   => Khoá công khai Alice (A) = {a_pub}")
    ok_a = kiem_tra_khoa_cong_khai("A", a_pub, p)

    b_pub, steps_b = mod_exp(co_so, mu_b, p, return_steps=True)
    print(f"\n2. Bob tính B = g^b mod p = {co_so}^{mu_b} mod {p}:")
    for st in steps_b:
        print(f"   - Vòng {st['step']}: Bit={st['bit']} | Lũy thừa={st['curr_base']} | Kết quả={st['result_so_far']}")
    print(f"   => Khoá công khai Bob (B) = {b_pub}")
    ok_b = kiem_tra_khoa_cong_khai("B", b_pub, p)

    if not (ok_a and ok_b):
        print("\n=> DỪNG: có khoá công khai không hợp lệ, không tính khoá chung. Hãy chọn lại a, b hoặc g.")
        return

    a_chung = mod_exp(b_pub, mu_a, p)
    b_chung = mod_exp(a_pub, mu_b, p)
    print("\n--- KẾT QUẢ TÍNH KHOÁ CHUNG ---")
    print(f"Alice tính (B^a mod p): {a_chung}")
    print(f"Bob   tính (A^b mod p): {b_chung}")

    if a_chung == b_chung:
        print(f"\n=> XÁC NHẬN: Khoá chung K = {a_chung} TRÙNG KHỚP!")
        print(f"=> Mã xác thực SAS (4 ký tự): [{sas_code(a_pub, b_pub, a_chung)}]")
    else:
        print("\n=> Hai khoá KHÔNG khớp (kiểm tra lại tham số).")

    # Dùng luôn bộ (p, g, a, b) vừa nhập để mô phỏng MITM, chỉ hỏi thêm c của Mallory.
    tiep = doc_dong("\nChạy tiếp mô phỏng MITM với đúng bộ tham số này? (y/N): ").strip().lower()
    if tiep == "y":
        mu_c = hoi_so_nguyen("Nhập khoá bí mật Mallory (c)", MAC_DINH["c"], 2, p - 2)
        run_mitm_simulation(p, co_so, mu_a, mu_b, mu_c)
        run_defense_simulation(p, co_so, mu_a, mu_b, mu_c)


def nhap_tay_mitm():
    print("\n" + "=" * 50)
    print("NHẬP THAM SỐ CHO MÔ PHỎNG MITM (giống phần nhập DH, thêm c của Mallory)")
    print("=" * 50)

    tham_so = nhap_tham_so_dh(can_mallory=True)
    if tham_so is None:
        return
    p, g, a, b, c = tham_so
    A, B = mod_exp(g, a, p), mod_exp(g, b, p)
    loi = [f"{ten} = {y}" for ten, y in (("A", A), ("B", B)) if not validate_pub(y, p)]
    if loi:
        print(f"\n=> DỪNG: {' và '.join(loi)} nằm ngoài [2, p-2] (khoá công khai không hợp lệ). Hãy chọn lại a, b hoặc g.")
        return
    run_mitm_simulation(p, g, a, b, c)
    run_defense_simulation(p, g, a, b, c)


def kiem_tra_rfc3526():
    print("\n--- Nhóm 14 RFC 3526 (2048-bit) ---")
    P = RFC_3526_2048_P
    print(f"Độ dài p: {P.bit_length()} bit")
    print(f"p là số nguyên tố      : {is_prime_miller_rabin(P, 5)}")
    print(f"(p-1)/2 là số nguyên tố: {is_prime_miller_rabin((P - 1) // 2, 5)}  (safe prime)")
    a = secrets.randbits(256) | 1
    b = secrets.randbits(256) | 1
    A, B = mod_exp(RFC_3526_2048_G, a, P), mod_exp(RFC_3526_2048_G, b, P)
    print(f"Trao đổi DH với nhóm này cho cùng khoá: {mod_exp(B, a, P) == mod_exp(A, b, P)}")
    print(f"validate_pub(A) với q=(p-1)/2: {validate_pub(A, P, (P - 1) // 2)}")


def main():
    print("=" * 50)
    print("CHỌN CHẾ ĐỘ CHẠY:")
    print("1: Nhập tay p, g, a, b từ bàn phím (có thể chạy tiếp MITM với cùng tham số)")
    print("2: Mô phỏng MITM và phòng thủ (nhập p, g, a, b, c như chế độ 1)")
    print("3: Sinh safe prime (p, g) và kiểm tra nhóm RFC 3526")
    print("=" * 50)

    chon = doc_dong("Nhập lựa chọn (1/2/3, mặc định là 1): ").strip()

    if chon == "2":
        nhap_tay_mitm()
    elif chon == "3":
        print("\n--- Sinh tham số gen_params(p, g) ---")
        p_auto, g_auto = gen_params(bits=12)
        print(f"Sinh thành công: p = {p_auto}, g = {g_auto}")
        print(f"Kiểm tra generator: {find_generator(p_auto) == g_auto}")
        kiem_tra_rfc3526()
    else:
        nhap_tay_truc_tiep()


if __name__ == "__main__":
    try:
        main()
    except NguoiDungThoat:
        print("Đã dừng chương trình.")
