# File: app/cli.py
"""
Giao diện dòng lệnh (CLI) điều khiển toàn bộ bài Demo Diffie-Hellman & Bài toán Logarit rời rạc.
Cách chạy:
  - Chế độ Menu tương tác : python -m app.cli
  - Chế độ tự động (--auto): python -m app.cli --auto
"""

import sys
from core.dh import (
    mod_exp,
    sas_code,
    run_mitm_simulation,
    run_defense_simulation,
    validate_pub,
    validate_dh_params,
    canh_bao_tham_so,
    is_prime_miller_rabin,
    RFC_3526_2048_P,
    RFC_3526_2048_G,
)
from core.stream import encrypt_text_hex, decrypt_text_hex
from core.dlog import dlog_bsgs, demo_eve_crack, demo_pohlig_hellman_compare
from app.filecrypt import ensure_sample_files, demo_file, benchmark_file_encryption
from app.benchmark import run_bsgs_benchmark

# BSGS cần bảng ~sqrt(p) phần tử; chặn p quá lớn để không tràn bộ nhớ (10^12 ~ 40 bit).
GIOI_HAN_P_BSGS = 10 ** 12


# ==============================================================================
# 1. HÀM NHẬP LIỆU AN TOÀN
# ==============================================================================

def doc_so_an_toan(loi_nhac: str, mac_dinh: int = None, min_val: int = 1, max_val: int = None) -> int:
    """
    Hàm bọc input() có xử lý lỗi: không bao giờ để chương trình văng Traceback khi nhập sai.
    Nếu nhấn Enter trống sẽ tự động dùng giá trị mặc định. Giá trị phải nằm trong [min_val, max_val].
    """
    while True:
        try:
            raw = input(loi_nhac).strip()
            if raw == "" and mac_dinh is not None:
                return mac_dinh
            val = int(raw)
            if val < min_val:
                print(f"  [!] Lỗi: Vui lòng nhập số nguyên lớn hơn hoặc bằng {min_val}.")
                continue
            if max_val is not None and val > max_val:
                print(f"  [!] Lỗi: Vui lòng nhập số nguyên nhỏ hơn hoặc bằng {max_val}.")
                continue
            return val
        except ValueError:
            print("  [!] Lỗi: Đầu vào không phải là số nguyên hợp lệ! Vui lòng nhập lại.")
        except (EOFError, KeyboardInterrupt):
            print("\n  [!] Đã hủy nhập, sử dụng giá trị mặc định.")
            return mac_dinh if mac_dinh is not None else min_val


def hoi_so(nhan: str, mac_dinh: int = None, min_val: int = 1, max_val: int = None) -> int:
    """Hỏi một số nguyên, tự ghi khoảng cho phép vào câu hỏi.
    Nếu giá trị mặc định nằm ngoài khoảng (ví dụ a=15 khi p=11) thì bỏ mặc định và báo rõ."""
    if mac_dinh is not None and (mac_dinh < min_val or (max_val is not None and mac_dinh > max_val)):
        print(f"  (Giá trị mặc định {mac_dinh} nằm ngoài khoảng cho phép với tham số hiện tại, hãy nhập số khác.)")
        mac_dinh = None
    khoang = f" [{min_val} đến {max_val}]" if max_val is not None else f" [>= {min_val}]"
    goi_y = f" (Enter = {mac_dinh})" if mac_dinh is not None else ""
    return doc_so_an_toan(f"  {nhan}{khoang}{goi_y}: ", mac_dinh=mac_dinh, min_val=min_val, max_val=max_val)


def hoi_tham_so_dh(can_mallory: bool = False, auto: bool = False):
    """Nhập p, g, a, b (và c của Mallory) dùng chung cho Mục 1, 4, 5.
    Dùng validate_dh_params và canh_bao_tham_so của Dev; khoá bí mật phải nằm trong [2, p-2].
    Trả về (p, g, a, b, c) hoặc None nếu tham số không hợp lệ."""
    if auto:
        p, g, a, b, c = 23, 5, 6, 15, 3
        print(f"  [Chế độ --auto] Sử dụng tham số: p = {p}, g = {g}, a = {a}, b = {b}" + (f", c = {c}" if can_mallory else ""))
        if not validate_dh_params(p, g):
            return None
        return p, g, a, b, (c if can_mallory else None)

    p = hoi_so("Nhập số nguyên tố p", 23, 5)
    g = hoi_so("Nhập cơ số g", 5, 2)
    if not validate_dh_params(p, g):
        return None
    canh_bao_tham_so(p, g)
    a = hoi_so("Nhập khóa riêng a của Alice", 6, 2, p - 2)
    b = hoi_so("Nhập khóa riêng b của Bob", 15, 2, p - 2)
    c = hoi_so("Nhập khóa riêng c của Mallory", 3, 2, p - 2) if can_mallory else None
    return p, g, a, b, c


def khoa_cong_khai_hop_le(p: int, A: int, B: int) -> bool:
    """Kiểm tra A, B bằng validate_pub; nếu sai thì báo rõ khoá nào và dừng demo."""
    loi = [f"{ten} = {y}" for ten, y in (("A", A), ("B", B)) if not validate_pub(y, p)]
    if loi:
        print(f"\n  => DỪNG: {' và '.join(loi)} nằm ngoài [2, p-2] (khóa công khai không hợp lệ, khóa chung bị lộ).")
        print("     Hãy chọn lại a, b hoặc g.")
        return False
    print("  => Kiểm tra validate_pub cho A và B: hợp lệ")
    return True


def in_bang_mod_exp(base: int, exp: int, mod: int, ten_bien: str) -> int:
    """In bảng từng bước bình phương và nhân từ hàm mod_exp(..., return_steps=True) của Dev."""
    kq, steps = mod_exp(base, exp, mod, return_steps=True)
    print(f"\n  [Chi tiết tính {ten_bien} = {base}^{exp} mod {mod}]")
    print(f"  {'Vòng':<6} | {'Bit':<6} | {'Lũy thừa (curr_base)':<22} | {'Kết quả tạm (result_so_far)'}")
    print("  " + "-" * 64)
    for st in steps:
        print(f"  {st['step']:<6} | {st['bit']:<6} | {st['curr_base']:<22} | {st['result_so_far']}")
    print(f"  => Kết quả {ten_bien} = {kq}")
    return kq


# ==============================================================================
# 2. CÁC MỤC DEMO
# ==============================================================================

def demo_1_dh_nho(auto: bool = False):
    """Mục 1: DH số nhỏ (p = 23, g = 5, a = 6, b = 15 -> khóa chung = 2), in từng bước."""
    print("\n" + "=" * 68)
    print(" MỤC 1: TRAO ĐỔI KHÓA DIFFIE-HELLMAN SỐ NHỎ (IN BƯỚC TRUNG GIAN)")
    print("=" * 68)
    tham_so = hoi_tham_so_dh(can_mallory=False, auto=auto)
    if tham_so is None:
        return
    p, g, a, b, _ = tham_so

    A = in_bang_mod_exp(g, a, p, ten_bien="A (Khóa công khai Alice)")
    B = in_bang_mod_exp(g, b, p, ten_bien="B (Khóa công khai Bob)")
    if not khoa_cong_khai_hop_le(p, A, B):
        return
    K_alice = in_bang_mod_exp(B, a, p, ten_bien="K_Alice = B^a mod p")
    K_bob = in_bang_mod_exp(A, b, p, ten_bien="K_Bob   = A^b mod p")

    print(f"\n  => KẾT QUẢ: Khóa chung hai bên {'khớp nhau' if K_alice == K_bob else 'KHÔNG khớp'} (K_Alice = {K_alice}, K_Bob = {K_bob})")
    print(f"  => Mã xác thực SAS (4 ký tự từ custom_sha256_bytes): [{sas_code(A, B, K_alice)}]")


def demo_2_dh_lon_va_ban_ro(auto: bool = False):
    """Mục 2: DH số lớn 2048-bit (RFC 3526), nhập bản rõ và khóa, hiện bản mã Hex, giải mã lại."""
    print("\n" + "=" * 68)
    print(" MỤC 2: DH SỐ LỚN (2048-BIT) - MÃ HÓA & GIẢI MÃ TIN NHẮN TRỰC TIẾP")
    print("=" * 68)
    P, G = RFC_3526_2048_P, RFC_3526_2048_G
    if auto:
        a, b = 1234567890123456789, 9876543210987654321
        ban_ro = "Xin chao Thay Co! Day la demo trao doi khoa Diffie-Hellman."
        print(f"  [Chế độ --auto] Bản rõ đầu vào: '{ban_ro}'")
    else:
        a = hoi_so("Nhập khóa riêng a của Alice", 1234567890123456789, 2, P - 2)
        b = hoi_so("Nhập khóa riêng b của Bob", 9876543210987654321, 2, P - 2)
        ban_ro = input("  Nhập bản rõ cần mã hóa (Enter = dùng câu mẫu): ").strip()
        if not ban_ro:
            ban_ro = "Xin chao Thay Co! Day la demo trao doi khoa Diffie-Hellman."

    A = mod_exp(G, a, P)
    B = mod_exp(G, b, P)
    # g = 2 sinh nhóm con bậc q = (p-1)/2 của safe prime RFC 3526, nên kiểm tra thêm y^q = 1
    q = (P - 1) // 2
    if not (validate_pub(A, P, q) and validate_pub(B, P, q)):
        print("  => DỪNG: khóa công khai không hợp lệ (ngoài [2, p-2] hoặc không thuộc nhóm con). Hãy chọn lại a, b.")
        return
    K_alice = mod_exp(B, a, P)
    K_bob = mod_exp(A, b, P)

    ban_ma_hex = encrypt_text_hex(ban_ro, K_alice)
    ban_giai_ma = decrypt_text_hex(ban_ma_hex, K_bob)

    print(f"  * Tham số p           : Chuẩn RFC 3526 Group 14 ({P.bit_length()} bits)")
    print(f"  * Kiểm tra khóa A, B  : hợp lệ (validate_pub với q = (p-1)/2)")
    print(f"  * Khóa chung (rút gọn): {hex(K_alice)[:22]}...")
    print(f"  * Mã xác thực SAS     : [{sas_code(A, B, K_alice)}]")
    print(f"  * Bản rõ ban đầu      : {ban_ro}")
    print(f"  * Bản mã (Hex)        : {ban_ma_hex}")
    print(f"  * Giải mã ngược lại   : {ban_giai_ma}")
    print(f"  => Đối chiếu bản rõ   : {'KHÔI PHỤC ĐÚNG 100%' if ban_ro == ban_giai_ma else 'SAI LỆCH'}")


def demo_3_tep_that():
    """Mục 3: Mã hóa và giải mã tệp văn bản (.txt) và tệp ảnh (.png) thực tế."""
    print("\n" + "=" * 68)
    print(" MỤC 3: DEMO TRÊN DỮ LIỆU THẬT (TỆP VĂN BẢN .TXT & ẢNH .PNG)")
    print("=" * 68)
    txt_path, png_path = ensure_sample_files()
    demo_file(txt_path)
    demo_file(png_path)
    benchmark_file_encryption()


def demo_4_mitm(auto: bool = False):
    """Mục 4: Minh họa tấn công người đứng giữa (gọi run_mitm_simulation của Dev + đọc/sửa tin)."""
    if not auto:
        print("\n  [Nhập tham số cho mô phỏng MITM - Nhấn Enter để dùng mặc định]")
    tham_so = hoi_tham_so_dh(can_mallory=True, auto=auto)
    if tham_so is None:
        return
    p, g, a, b, c = tham_so
    if not khoa_cong_khai_hop_le(p, mod_exp(g, a, p), mod_exp(g, b, p)):
        return

    K_alice, K_bob, K_mal_alice, K_mal_bob = run_mitm_simulation(p, g, a, b, c)

    print("\n  [Minh họa Mallory chặn đọc và sửa nội dung tin nhắn trên đường truyền]")
    tin_alice = "Chuyen 5,000,000 VND cho Bob"
    cipher_from_alice = encrypt_text_hex(tin_alice, K_alice)
    mallory_read = decrypt_text_hex(cipher_from_alice, K_mal_alice)

    tin_gia_mao = "Chuyen 5,000,000 VND cho tai khoan Mallory"
    cipher_to_bob = encrypt_text_hex(tin_gia_mao, K_mal_bob)
    bob_read = decrypt_text_hex(cipher_to_bob, K_bob)

    print(f"  * Alice gửi đi          : '{tin_alice}' (Mã hóa bằng K_Alice = {K_alice})")
    print(f"  * Mallory chặn & đọc lén: '{mallory_read}'")
    print(f"  * Mallory sửa nội dung  : '{tin_gia_mao}' (Mã hóa lại bằng K_Mal_Bob = {K_mal_bob})")
    print(f"  * Bob giải mã nhận được : '{bob_read}' (Bob hoàn toàn không biết bị nghe lén!)")


def demo_5_phong_chong_mitm(auto: bool = False):
    """Mục 5: Cơ chế phòng chống MITM bằng SAS và Chữ ký số RSA tự viết của Dev (không dùng hashlib)."""
    if not auto:
        print("\n  [Nhập tham số kiểm tra Phòng thủ SAS & Chữ ký RSA - Nhấn Enter để dùng mặc định]")
    tham_so = hoi_tham_so_dh(can_mallory=True, auto=auto)
    if tham_so is None:
        return
    p, g, a, b, c = tham_so
    if not khoa_cong_khai_hop_le(p, mod_exp(g, a, p), mod_exp(g, b, p)):
        return

    run_defense_simulation(p, g, a, b, c)


def demo_6_bsgs_tuong_tac():
    """Mục 6: Bắt chước người dùng thật nhập p, g, A bất kỳ để tìm a bằng BSGS."""
    print("\n" + "=" * 68)
    print(" MỤC 6: CÔNG CỤ GIẢI LOGARIT RỜI RẠC BSGS TƯƠNG TÁC (TÌM a TỪ p, g, A)")
    print("=" * 68)
    p = hoi_so("Nhập số nguyên tố p", 10007, 3, GIOI_HAN_P_BSGS)
    if not is_prime_miller_rabin(p):
        print(f"  [!] Lỗi: p = {p} không phải số nguyên tố, BSGS ở đây chỉ áp dụng cho p nguyên tố.")
        return
    g = hoi_so("Nhập cơ số g", 5, 2, p - 1)
    A = hoi_so("Nhập giá trị công khai A", 6518, 1, p - 1)
    try:
        a = dlog_bsgs(g, A, p)
    except (ValueError, MemoryError) as e:
        print(f"  [!] Không giải được với bộ tham số này ({type(e).__name__}: {e}).")
        return
    if a is not None:
        print(f"  => Tìm thấy khóa riêng a = {a} (Kiểm tra bằng mod_exp: {g}^{a} mod {p} = {mod_exp(g, a, p)})")
    else:
        print("  => Không tồn tại số mũ a thỏa mãn bộ tham số trên.")


# ==============================================================================
# 3. CHẠY TỰ ĐỘNG & MENU CHÍNH
# ==============================================================================

def chay_tu_dong_toan_bo():
    """Chế độ --auto chạy liên hoàn kịch bản demo không cần gõ phím."""
    print("\n" + "#" * 68)
    print("   CHẾ ĐỘ CHẠY TỰ ĐỘNG (--auto) PHỤC VỤ DEMO TRỰC TIẾP TRÊN LỚP")
    print("#" * 68)
    demo_1_dh_nho(auto=True)
    demo_2_dh_lon_va_ban_ro(auto=True)
    demo_3_tep_that()
    demo_4_mitm(auto=True)
    demo_5_phong_chong_mitm(auto=True)
    demo_eve_crack()
    demo_pohlig_hellman_compare()
    run_bsgs_benchmark(repeats=2)
    print("\n" + "#" * 68)
    print("   HOÀN TẤT TOÀN BỘ KỊCH BẢN DEMO TỰ ĐỘNG")
    print("#" * 68)


def main():
    if "--auto" in sys.argv:
        chay_tu_dong_toan_bo()
        return

    while True:
        print("\n" + "=" * 68)
        print("   CHƯƠNG TRÌNH DEMO DIFFIE-HELLMAN, LOGARIT RỜI RẠC & MITM (CLI)")
        print("=" * 68)
        print("  1. DH số nhỏ (p = 23): In chi tiết từng bước mod_exp & mã SAS")
        print("  2. DH số lớn (2048-bit): Nhập bản rõ & khóa, hiện bản mã, giải mã")
        print("  3. Demo dữ liệu thật: Mã hóa & giải mã tệp văn bản (.txt) và ảnh (.png)")
        print("  4. Minh họa tấn công MITM: Mallory chặn khóa, đọc & sửa tin nhắn")
        print("  5. Phòng chống MITM: So khớp mã SAS & Chữ ký số RSA (custom_sha256_bytes)")
        print("  6. Bẻ khóa tương tác: Nhập (p, g, A) bất kỳ -> Tìm khóa riêng a bằng BSGS")
        print("  7. Demo Eve bẻ khóa 32-bit & So sánh Pohlig-Hellman ((p-1) trơn vs Safe Prime)")
        print("  8. Benchmark BSGS (16-36 bit), xuất biểu đồ docs/benchmark.png & ngoại suy 2048-bit")
        print("  0. Thoát chương trình")
        print("-" * 68)

        lua_chon = doc_so_an_toan("  Mời chọn mục demo (0 - 8): ", mac_dinh=0, min_val=0)
        if lua_chon == 0:
            print("  Đã thoát chương trình. Chúc nhóm bảo vệ đạt điểm tối đa!")
            break
        elif lua_chon == 1:
            demo_1_dh_nho(auto=False)
        elif lua_chon == 2:
            demo_2_dh_lon_va_ban_ro(auto=False)
        elif lua_chon == 3:
            demo_3_tep_that()
        elif lua_chon == 4:
            demo_4_mitm(auto=False)
        elif lua_chon == 5:
            demo_5_phong_chong_mitm(auto=False)
        elif lua_chon == 6:
            demo_6_bsgs_tuong_tac()
        elif lua_chon == 7:
            demo_eve_crack()
            demo_pohlig_hellman_compare()
        elif lua_chon == 8:
            run_bsgs_benchmark(repeats=3)
        else:
            print("  [!] Vui lòng chọn số từ 0 đến 8.")


if __name__ == "__main__":
    main()
