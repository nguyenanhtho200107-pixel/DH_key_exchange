"""
Kiểm thử app/benchmark.py : đo BSGS 16-36 bit, xuất CSV và biểu đồ, ngoại suy 2048-bit.
Mọi tệp được ghi trong thư mục tạm; sympy chỉ dùng để đối chiếu số nguyên tố.
"""
import csv
import math
import os
import sys

import pytest
import sympy

from app import benchmark


def chay_benchmark(capsys, repeats=1):
    benchmark.run_bsgs_benchmark(repeats=repeats)
    return capsys.readouterr().out


def doc_csv(duong_dan="docs/benchmark.csv"):
    with open(duong_dan, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


class TestDuLieuCoDinh:
    def test_sau_moc_16_den_36_bit(self):
        assert [b for b, _ in benchmark.BENCHMARK_PRIMES] == [16, 20, 24, 28, 32, 36]

    @pytest.mark.parametrize("bits,p", benchmark.BENCHMARK_PRIMES)
    def test_so_nguyen_to_dung_co_bit(self, bits, p):
        assert p.bit_length() == bits
        assert sympy.isprime(p)


class TestChayBenchmark:
    def test_ghi_csv_dung_cau_truc(self, thu_muc_tam, capsys):
        chay_benchmark(capsys)
        dong = doc_csv()
        assert dong[0][0].startswith("# Cau hinh may:")
        assert dong[1] == ["bit_length", "prime_p", "sqrt_p_steps", "avg_time_seconds", "loai_so_lieu"]
        assert len(dong) == 2 + 6 + 1                                  # chú thích, tiêu đề, 6 điểm đo, 1 dòng ngoại suy

    def test_so_lieu_do_hop_le(self, thu_muc_tam, capsys):
        chay_benchmark(capsys)
        dong_do = doc_csv()[2:8]
        for (bits, p), r in zip(benchmark.BENCHMARK_PRIMES, dong_do):
            assert int(r[0]) == bits and int(r[1]) == p
            assert int(r[2]) == math.isqrt(p)
            assert float(r[3]) > 0
            assert r[4] == "Thuc do (Measured)"

    def test_dong_ngoai_suy_khop_cong_thuc(self, thu_muc_tam, capsys):
        chay_benchmark(capsys)
        dong = doc_csv()
        thoi_gian_36 = float(dong[7][3])
        cuoi = dong[-1]
        assert cuoi[0] == "2048" and cuoi[1] == "2^2048" and cuoi[2] == "2^1024"
        assert cuoi[4] == "Uoc luong ngoai suy O(sqrt(p))"
        mong_doi = thoi_gian_36 * 2 ** ((2048 - 36) / 2)               # tăng 2012 bit => nhân 2^1006
        assert math.isclose(float(cuoi[3]), mong_doi, rel_tol=0.01)    # file chỉ lưu 3 chữ số có nghĩa

    def test_thoi_gian_tang_theo_do_dai_khoa(self, thu_muc_tam, capsys):
        chay_benchmark(capsys, repeats=2)
        t = [float(r[3]) for r in doc_csv()[2:8]]
        assert t[-1] > 20 * t[0]                                        # 36-bit chậm hơn 16-bit rất nhiều (lý thuyết ~1000 lần)

    def test_do_doc_dung_quy_luat_can_bac_hai(self, thu_muc_tam, capsys):
        chay_benchmark(capsys, repeats=2)
        dong = doc_csv()[2:8]
        x = [math.log2(int(r[2])) for r in dong]
        y = [math.log2(float(r[3])) for r in dong]
        n = len(x)
        mx, my = sum(x) / n, sum(y) / n
        do_doc = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sum((a - mx) ** 2 for a in x)
        assert 0.6 < do_doc < 1.4                                       # lý thuyết 1,0: thời gian ~ sqrt(p)

    def test_in_man_hinh(self, thu_muc_tam, capsys):
        out = chay_benchmark(capsys)
        assert "KHÔNG PHẢI số thực đo" in out
        assert "2^1024" in out and "Cấu hình máy chạy" in out
        assert "benchmark.csv" in out
        for _, p in benchmark.BENCHMARK_PRIMES:
            assert str(p) in out

    def test_tao_thu_muc_docs_neu_chua_co(self, thu_muc_tam, capsys):
        assert not os.path.exists("docs")
        chay_benchmark(capsys)
        assert os.path.isdir("docs")

    def test_chay_lai_ghi_de_csv(self, thu_muc_tam, capsys):
        chay_benchmark(capsys)
        chay_benchmark(capsys)
        assert len(doc_csv()) == 9


class TestBieuDo:
    def test_tao_png(self, thu_muc_tam, capsys):
        matplotlib = pytest.importorskip("matplotlib")
        matplotlib.use("Agg")
        chay_benchmark(capsys)
        with open("docs/benchmark.png", "rb") as f:
            dau = f.read(8)
        assert dau == b"\x89PNG\r\n\x1a\n"
        assert os.path.getsize("docs/benchmark.png") > 5_000

    def test_thieu_matplotlib_van_ghi_csv(self, thu_muc_tam, capsys, monkeypatch):
        monkeypatch.setitem(sys.modules, "matplotlib.pyplot", None)    # làm import báo ImportError
        out = chay_benchmark(capsys)
        assert "chưa cài matplotlib" in out
        assert not os.path.exists("docs/benchmark.png")
        assert len(doc_csv()) == 9                                      # CSV vẫn được ghi
