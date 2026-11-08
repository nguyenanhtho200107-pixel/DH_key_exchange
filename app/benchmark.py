# File: app/benchmark.py
"""
Đo thời gian chạy BSGS cho p từ 16 đến 36 bit (lấy trung bình nhiều lần chạy),
lưu số liệu thô ra docs/benchmark.csv, vẽ biểu đồ trục log ra docs/benchmark.png,
và ngoại suy thời gian cho p = 2048-bit bằng quy luật O(√p).
"""

import os
import csv
import math
import time
import platform
from core.dh import mod_exp
from core.dlog import dlog_bsgs

BENCHMARK_PRIMES = [
    (16, 65521),
    (20, 1048573),
    (24, 16777213),
    (28, 268435399),
    (32, 4294967291),
    (36, 68719476731),
]

def run_bsgs_benchmark(repeats: int = 3):
    os.makedirs("docs", exist_ok=True)
    csv_path = os.path.join("docs", "benchmark.csv")
    png_path = os.path.join("docs", "benchmark.png")

    print("\n" + "=" * 72)
    print(" MỤC 8: BENCHMARK BSGS (16 - 36 BIT) & NGOẠI SUY KHÓA 2048-BIT")
    print("=" * 72)
    machine_info = (
        f"OS: {platform.system()} {platform.release()} | "
        f"CPU: {platform.processor()} | Python: {platform.python_version()}"
    )
    print(f"  Cấu hình máy chạy: {machine_info}")
    print(f"  Số lần đo lặp lấy trung bình mỗi cỡ bit: {repeats} lần\n")

    print(f"  {'Cỡ bit':<8} | {'Số nguyên tố p':<14} | {'Cỡ bảng √p':<14} | {'Thời gian TB (giây)':<20}")
    print("  " + "-" * 64)

    rows = []
    for bits, p in BENCHMARK_PRIMES:
        g = 2
        a = int(p * 0.73)
        A = mod_exp(g, a, p)

        elapsed_total = 0.0
        for _ in range(repeats):
            t0 = time.perf_counter()
            found_a = dlog_bsgs(g, A, p)
            elapsed_total += (time.perf_counter() - t0)
            assert found_a is not None and mod_exp(g, found_a, p) == A

        avg_sec = elapsed_total / repeats
        sqrt_p = math.isqrt(p)
        rows.append((bits, p, sqrt_p, avg_sec))
        print(f"  {bits:<8} | {p:<14} | {sqrt_p:<14} | {avg_sec:<20.6f}")

    # Ngoại suy cho 2048-bit theo quy luật O(√p) từ điểm đo 36-bit
    base_bits, _, _, base_time = rows[-1]
    factor = 2 ** ((2048 - base_bits) / 2.0)
    extrapolated_seconds = base_time * factor
    extrapolated_years = extrapolated_seconds / (365.25 * 24 * 3600)

    print("  " + "-" * 64)
    print("  [ƯỚC LƯỢNG NGOẠI SUY CHO p = 2048-BIT THEO QUY LUẬT O(√p)]")
    print("  * Lưu ý: Đây là con số ƯỚC LƯỢNG toán học theo hàm O(√p), KHÔNG PHẢI số thực đo.")
    print(f"  * Số phần tử bảng Baby-step ở 2048-bit : ~ 2^1024 ≈ 1.79 x 10^308 phần tử")
    print(f"  * Thời gian ước lượng bằng BSGS         : ~ {extrapolated_seconds:.2e} giây (~ {extrapolated_years:.2e} năm)")

    # 1. Xuất ra docs/benchmark.csv
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["# Cau hinh may: " + machine_info])
        writer.writerow(["bit_length", "prime_p", "sqrt_p_steps", "avg_time_seconds", "loai_so_lieu"])
        for bits, p, sqrt_p, avg_sec in rows:
            writer.writerow([bits, p, sqrt_p, f"{avg_sec:.6f}", "Thuc do (Measured)"])
        writer.writerow([2048, "2^2048", "2^1024", f"{extrapolated_seconds:.2e}", "Uoc luong ngoai suy O(sqrt(p))"])
    print(f"\n  [+] Đã xuất bảng số liệu CSV tại : {csv_path}")

    # 2. Vẽ biểu đồ matplotlib lưu ra docs/benchmark.png
    try:
        import matplotlib.pyplot as plt
        x_bits = [r[0] for r in rows]
        y_times = [r[3] for r in rows]

        plt.figure(figsize=(8, 5))
        plt.plot(x_bits, y_times, marker="o", color="#1f77b4", linewidth=2, label="Thời gian thực đo BSGS (giây)")
        plt.yscale("log")
        plt.xticks(x_bits)
        plt.xlabel("Độ dài bit của số nguyên tố p (bits)")
        plt.ylabel("Thời gian thực thi trung bình (giây - Trục Log)")
        plt.title("Thời gian bẻ khóa Logarit rời rạc bằng BSGS theo độ dài khóa p")
        plt.grid(True, which="both", linestyle="--", alpha=0.6)
        plt.legend()
        plt.tight_layout()
        plt.savefig(png_path, dpi=150)
        plt.close()
        print(f"  [+] Đã xuất biểu đồ trục log tại : {png_path}")
    except ImportError:
        print("  [!] Máy chưa cài matplotlib. Hãy chạy lệnh: pip install matplotlib")