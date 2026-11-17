"""
Kiểm thử app/cli.py : nhập liệu an toàn, kiểm tra tham số, các mục demo 1-6, menu và chế độ --auto.
Quy ước: pow() chỉ dùng trong tests/ để đối chiếu.
"""
import os
import re
import subprocess
import sys

import pytest

from app import cli
from core import dh


@pytest.fixture
def nhap(monkeypatch):
    """Giả lập bàn phím: nhap(['23', '5']) rồi mỗi lần input() lấy một phần tử; hết dữ liệu thì EOFError.
    Trả về danh sách các câu hỏi đã hiện (prompt)."""
    def dat(cac_gia_tri):
        hang = list(cac_gia_tri)
        cau_hoi = []

        het_du_lieu = []

        def gia_input(loi_nhac=""):
            cau_hoi.append(loi_nhac)
            if not hang:
                het_du_lieu.append(1)
                if len(het_du_lieu) > 50:          # chương trình cứ hỏi mãi khi hết dữ liệu = vòng lặp vô hạn
                    raise AssertionError("input() bị gọi lặp vô hạn sau khi hết dữ liệu nhập")
                raise EOFError
            return hang.pop(0)
        monkeypatch.setattr("builtins.input", gia_input)
        return cau_hoi
    return dat


# ---------------------------------------------------------------- 1. NHẬP LIỆU AN TOÀN
class TestDocSoAnToan:
    def test_loi_roi_dung(self, nhap, capsys):
        nhap(["abc", "", "0", "11", "7"])
        assert cli.doc_so_an_toan("x: ", None, 1, 10) == 7
        out = capsys.readouterr().out
        assert out.count("không phải là số nguyên") == 2          # "abc" và chuỗi rỗng khi không có mặc định
        assert "lớn hơn hoặc bằng 1" in out
        assert "nhỏ hơn hoặc bằng 10" in out

    def test_mac_dinh(self, nhap):
        nhap([""])
        assert cli.doc_so_an_toan("x: ", 23, 5) == 23

    def test_so_thuc_va_so_am(self, nhap, capsys):
        nhap(["1.5", "-3", "9"])
        assert cli.doc_so_an_toan("x: ", None, 1) == 9
        out = capsys.readouterr().out
        assert out.count("không phải là số nguyên") == 1          # "1.5"
        assert "lớn hơn hoặc bằng 1" in out                       # "-3"

    def test_khoang_trong_hai_dau(self, nhap):
        nhap(["  42  "])
        assert cli.doc_so_an_toan("x: ", None, 1) == 42

    def test_het_du_lieu_dung_mac_dinh(self, nhap):
        nhap([])
        assert cli.doc_so_an_toan("x: ", 9, 1) == 9

    def test_het_du_lieu_khong_mac_dinh_dung_min(self, nhap):
        nhap([])
        assert cli.doc_so_an_toan("x: ", None, 4) == 4

    def test_ctrl_c(self, monkeypatch):
        def ngat(_=""):
            raise KeyboardInterrupt
        monkeypatch.setattr("builtins.input", ngat)
        assert cli.doc_so_an_toan("x: ", 5, 1) == 5


class TestHoiSo:
    def test_ghi_khoang_vao_cau_hoi(self, nhap):
        cau_hoi = nhap([""])
        assert cli.hoi_so("a", 6, 2, 21) == 6
        assert "[2 đến 21]" in cau_hoi[0] and "Enter = 6" in cau_hoi[0]

    def test_bo_mac_dinh_ngoai_khoang(self, nhap, capsys):
        cau_hoi = nhap(["4"])
        assert cli.hoi_so("b", 15, 2, 9) == 4
        assert "nằm ngoài khoảng cho phép" in capsys.readouterr().out
        assert "Enter =" not in cau_hoi[0]

    def test_khong_gioi_han_tren(self, nhap):
        cau_hoi = nhap(["77"])
        assert cli.hoi_so("p", 23, 5) == 77
        assert "[>= 5]" in cau_hoi[0]


class TestHoiThamSoDh:
    def test_auto(self):
        assert cli.hoi_tham_so_dh(can_mallory=True, auto=True) == (23, 5, 6, 15, 3)
        assert cli.hoi_tham_so_dh(can_mallory=False, auto=True) == (23, 5, 6, 15, None)

    def test_enter_het_la_mac_dinh(self, nhap):
        nhap([""] * 5)
        assert cli.hoi_tham_so_dh(can_mallory=True) == (23, 5, 6, 15, 3)

    def test_p_khong_nguyen_to(self, nhap, capsys):
        nhap(["24", "5"])
        assert cli.hoi_tham_so_dh() is None
        assert "không phải là số nguyên tố" in capsys.readouterr().out

    def test_g_bang_1_bi_tu_choi_roi_nhap_lai(self, nhap, capsys):
        nhap(["23", "1", "2", "6", "15"])                          # g = 1 bị chặn (>= 2); g = 2 được nhận kèm cảnh báo
        assert cli.hoi_tham_so_dh() == (23, 2, 6, 15, None)
        out = capsys.readouterr().out
        assert "lớn hơn hoặc bằng 2" in out
        assert "KHÔNG phải" in out or "không phải căn nguyên thuỷ" in out

    def test_g_bang_p(self, nhap, capsys):
        nhap(["23", "23"])
        assert cli.hoi_tham_so_dh() is None
        assert "Cơ số g" in capsys.readouterr().out

    def test_khoa_rieng_p_tru_1_bi_tu_choi(self, nhap, capsys):
        nhap(["23", "5", "22", "21", "15"])
        assert cli.hoi_tham_so_dh() == (23, 5, 21, 15, None)
        assert "nhỏ hơn hoặc bằng 21" in capsys.readouterr().out

    def test_khoa_rieng_bang_1_bi_tu_choi(self, nhap, capsys):
        nhap(["23", "5", "1", "2", "3"])
        assert cli.hoi_tham_so_dh() == (23, 5, 2, 3, None)
        assert "lớn hơn hoặc bằng 2" in capsys.readouterr().out

    def test_khoa_bob_bang_1_bi_tu_choi(self, nhap, capsys):
        nhap(["23", "5", "6", "1", "3"])
        assert cli.hoi_tham_so_dh() == (23, 5, 6, 3, None)
        assert "lớn hơn hoặc bằng 2" in capsys.readouterr().out

    def test_khoa_bob_p_tru_1_bi_tu_choi(self, nhap, capsys):
        nhap(["23", "5", "6", "22", "3"])
        assert cli.hoi_tham_so_dh() == (23, 5, 6, 3, None)
        assert "nhỏ hơn hoặc bằng 21" in capsys.readouterr().out

    def test_khoa_mallory_ngoai_khoang_bi_tu_choi(self, nhap, capsys):
        nhap(["23", "5", "6", "15", "1", "22", "4"])
        assert cli.hoi_tham_so_dh(can_mallory=True) == (23, 5, 6, 15, 4)
        out = capsys.readouterr().out
        assert "lớn hơn hoặc bằng 2" in out and "nhỏ hơn hoặc bằng 21" in out

    def test_mac_dinh_ngoai_khoang_khi_p_nho(self, nhap, capsys):
        # p = 11: b mặc định 15 > p - 2 = 9 nên phải bị bỏ và hỏi lại
        nhap(["11", "2", "", "", "4"])
        assert cli.hoi_tham_so_dh() == (11, 2, 6, 4, None)
        assert "nằm ngoài khoảng cho phép" in capsys.readouterr().out

    def test_canh_bao_tham_so_yeu(self, nhap, capsys):
        nhap([""] * 4)
        cli.hoi_tham_so_dh()
        assert "Cảnh báo" in capsys.readouterr().out                # p = 23 chỉ 5 bit


class TestKhoaCongKhaiHopLe:
    def test_hop_le(self, capsys):
        assert cli.khoa_cong_khai_hop_le(23, 8, 19) is True
        assert "hợp lệ" in capsys.readouterr().out

    @pytest.mark.parametrize("A,B,chuoi", [(1, 19, "A = 1"), (8, 22, "B = 22"), (0, 19, "A = 0"), (23, 19, "A = 23")])
    def test_khong_hop_le(self, A, B, chuoi, capsys):
        assert cli.khoa_cong_khai_hop_le(23, A, B) is False
        assert chuoi in capsys.readouterr().out

    def test_ca_hai_deu_sai(self, capsys):
        assert cli.khoa_cong_khai_hop_le(23, 1, 22) is False
        out = capsys.readouterr().out
        assert "A = 1" in out and "B = 22" in out


# ---------------------------------------------------------------- 2. BẢNG TỪNG BƯỚC
class TestInBangModExp:
    def test_tra_ve_va_in_dung(self, capsys):
        kq = cli.in_bang_mod_exp(5, 6, 23, "A")
        out = capsys.readouterr().out
        assert kq == 8 == pow(5, 6, 23)
        assert "[Chi tiết tính A = 5^6 mod 23]" in out
        assert "=> Kết quả A = 8" in out

    def test_cac_dong_khop_steps(self, capsys):
        cli.in_bang_mod_exp(5, 15, 23, "B")
        out = capsys.readouterr().out
        _, steps = dh.mod_exp(5, 15, 23, return_steps=True)
        dong_so_lieu = re.findall(r"^\s+(\d+)\s+\| (\d)\s+\| (\d+)\s+\| (\d+)$", out, re.M)
        assert len(dong_so_lieu) == len(steps) == 4
        for (vong, bit, co_so, kq), st in zip(dong_so_lieu, steps):
            assert (int(vong), int(bit), int(co_so), int(kq)) == (st["step"], st["bit"], st["curr_base"], st["result_so_far"])

    def test_so_lon(self, capsys):
        assert cli.in_bang_mod_exp(123456789, 987654321, 1000003, "X") == pow(123456789, 987654321, 1000003)
        capsys.readouterr()


# ---------------------------------------------------------------- 3. CÁC MỤC DEMO
class TestMuc1:
    def test_auto_khop_bao_cao(self, capsys):
        cli.demo_1_dh_nho(auto=True)
        out = capsys.readouterr().out
        assert "A (Khóa công khai Alice) = 8" in out
        assert "B (Khóa công khai Bob) = 19" in out
        assert "K_Alice = 2, K_Bob = 2" in out
        assert "khớp nhau" in out and "[FD65]" in out

    def test_tham_so_nguoi_dung(self, nhap, capsys):
        nhap(["101", "2", "17", "33"])
        cli.demo_1_dh_nho()
        K = pow(pow(2, 17, 101), 33, 101)
        assert f"K_Alice = {K}, K_Bob = {K}" in capsys.readouterr().out

    def test_dung_khi_khoa_cong_khai_khong_hop_le(self, nhap, capsys):
        nhap(["7", "2", "3", "4"])                                # g = 2 mod 7 có bậc 3, a = 3 cho A = 1
        cli.demo_1_dh_nho()
        out = capsys.readouterr().out
        assert "DỪNG" in out and "KẾT QUẢ" not in out

    def test_p_khong_nguyen_to_khong_chay(self, nhap, capsys):
        nhap(["24", "5"])
        cli.demo_1_dh_nho()
        out = capsys.readouterr().out
        assert "KẾT QUẢ" not in out and "Chi tiết tính" not in out


class TestMuc2:
    def test_auto(self, capsys):
        cli.demo_2_dh_lon_va_ban_ro(auto=True)
        out = capsys.readouterr().out
        assert "RFC 3526 Group 14 (2048 bits)" in out
        assert "KHÔI PHỤC ĐÚNG 100%" in out
        assert "validate_pub" in out

    def test_ban_ro_tieng_viet(self, nhap, capsys):
        nhap(["", "", "Chào Thầy Cô, đây là demo!"])
        cli.demo_2_dh_lon_va_ban_ro()
        out = capsys.readouterr().out
        assert "Chào Thầy Cô, đây là demo!" in out and "KHÔI PHỤC ĐÚNG 100%" in out

    def test_khoa_bang_1_bi_tu_choi(self, nhap, capsys):
        nhap(["1", "", "", ""])
        cli.demo_2_dh_lon_va_ban_ro()
        assert "lớn hơn hoặc bằng 2" in capsys.readouterr().out

    def test_cau_mau_khi_bo_trong(self, nhap, capsys):
        nhap(["", "", ""])
        cli.demo_2_dh_lon_va_ban_ro()
        assert "Xin chao Thay Co!" in capsys.readouterr().out


class TestMuc3:
    def test_ma_hoa_hai_tep(self, thu_muc_tam, monkeypatch, capsys):
        monkeypatch.setattr(cli, "benchmark_file_encryption", lambda: print("[bảng đo giả]"))
        cli.demo_3_tep_that()
        out = capsys.readouterr().out
        assert out.count("khôi phục đúng") == 2
        assert "[bảng đo giả]" in out
        for ten in ("thong_diep.txt", "thong_diep_ma_hoa.txt.enc", "thong_diep_khoi_phuc.txt",
                    "anh_mau.png", "anh_mau_ma_hoa.png.enc", "anh_mau_khoi_phuc.png"):
            assert os.path.exists(os.path.join("samples", ten)), ten


class TestMuc4:
    def test_auto(self, capsys):
        cli.demo_4_mitm(auto=True)
        out = capsys.readouterr().out
        assert "M = g^c = 10" in out
        assert "K_Alice = 6" in out and "K_Mal_Bob = 5" in out
        assert "'Chuyen 5,000,000 VND cho Bob'" in out                         # Mallory đọc được tin gốc
        assert "'Chuyen 5,000,000 VND cho tai khoan Mallory'" in out           # Bob nhận tin đã bị sửa
        assert "Bob hoàn toàn không biết" in out

    def test_dung_khi_tham_so_xau(self, nhap, capsys):
        nhap(["7", "2", "3", "4", "2"])
        cli.demo_4_mitm()
        out = capsys.readouterr().out
        assert "DỪNG" in out and "Mallory chặn" not in out

    def test_tham_so_tuy_y(self, nhap, capsys):
        nhap(["101", "2", "17", "33", "9"])
        cli.demo_4_mitm()
        out = capsys.readouterr().out
        M = pow(2, 9, 101)
        assert f"M = g^c = {M}" in out
        assert f"K_Alice = {pow(M, 17, 101)}" in out


class TestMuc5:
    def test_auto(self, capsys):
        cli.demo_5_phong_chong_mitm(auto=True)
        out = capsys.readouterr().out
        assert "FD65" in out
        assert "LỆCH, phát hiện MITM" in out
        assert "chữ ký của A = 8: True" in out
        assert "chữ ký cũ): False" in out

    def test_dung_khi_tham_so_xau(self, nhap, capsys):
        nhap(["24", "5"])
        cli.demo_5_phong_chong_mitm()
        out = capsys.readouterr().out
        assert "PHÒNG THỦ 1" not in out and "PHÒNG THỦ 2" not in out


class TestMuc6:
    def test_mac_dinh(self, nhap, capsys):
        nhap(["", "", ""])
        cli.demo_6_bsgs_tuong_tac()
        out = capsys.readouterr().out
        assert "a = 6919" in out
        assert f"5^6919 mod 10007 = {pow(5, 6919, 10007)}" in out

    def test_p_khong_nguyen_to(self, nhap, capsys):
        nhap(["10"])
        cli.demo_6_bsgs_tuong_tac()
        assert "không phải số nguyên tố" in capsys.readouterr().out

    def test_chan_p_qua_lon(self, nhap, capsys):
        nhap([str(10 ** 13), "10007", "", ""])
        cli.demo_6_bsgs_tuong_tac()
        out = capsys.readouterr().out
        assert "nhỏ hơn hoặc bằng" in out and "a = 6919" in out

    def test_khong_co_nghiem(self, nhap, capsys):
        nhap(["23", "2", "5"])                                    # 2 chỉ sinh nhóm con bậc 11, A = 5 nằm ngoài
        cli.demo_6_bsgs_tuong_tac()
        assert "Không tồn tại" in capsys.readouterr().out

    def test_g_va_A_ngoai_khoang(self, nhap, capsys):
        nhap(["23", "23", "1", "5", "23", "8"])                   # g = 23 và A = 23 bị chặn, nhập lại g = 1 -> chặn, g = 5, A = 8
        cli.demo_6_bsgs_tuong_tac()
        out = capsys.readouterr().out
        assert "nhỏ hơn hoặc bằng 22" in out and "a = 6" in out


# ---------------------------------------------------------------- 4. MENU VÀ --auto
class TestMenu:
    def test_thoat(self, nhap, monkeypatch, capsys):
        nhap(["0"])
        monkeypatch.setattr(sys, "argv", ["cli"])
        cli.main()
        assert "Đã thoát chương trình" in capsys.readouterr().out

    def test_chon_sai_roi_thoat(self, nhap, monkeypatch, capsys):
        nhap(["9", "0"])
        monkeypatch.setattr(sys, "argv", ["cli"])
        cli.main()
        assert "chọn số từ 0 đến 8" in capsys.readouterr().out

    def test_het_du_lieu_thoat_gon(self, nhap, monkeypatch, capsys):
        nhap([])
        monkeypatch.setattr(sys, "argv", ["cli"])
        cli.main()
        assert "Đã thoát chương trình" in capsys.readouterr().out

    @pytest.mark.parametrize("so,ten_ham", [
        ("1", "demo_1_dh_nho"), ("2", "demo_2_dh_lon_va_ban_ro"), ("3", "demo_3_tep_that"),
        ("4", "demo_4_mitm"), ("5", "demo_5_phong_chong_mitm"), ("6", "demo_6_bsgs_tuong_tac"),
        ("7", "demo_eve_crack"), ("8", "run_bsgs_benchmark"),
    ])
    def test_moi_lua_chon_goi_dung_ham(self, so, ten_ham, nhap, monkeypatch):
        da_goi = []
        for ten in ("demo_1_dh_nho", "demo_2_dh_lon_va_ban_ro", "demo_3_tep_that", "demo_4_mitm",
                    "demo_5_phong_chong_mitm", "demo_6_bsgs_tuong_tac", "demo_eve_crack",
                    "demo_pohlig_hellman_compare", "run_bsgs_benchmark"):
            monkeypatch.setattr(cli, ten, lambda *a, _t=ten, **k: da_goi.append(_t))
        nhap([so, "0"])
        monkeypatch.setattr(sys, "argv", ["cli"])
        cli.main()
        assert ten_ham in da_goi
        if so == "7":
            assert da_goi == ["demo_eve_crack", "demo_pohlig_hellman_compare"]      # Mục 7 chạy cả hai demo

    def test_co_auto_goi_chay_tu_dong(self, monkeypatch):
        da_goi = []
        monkeypatch.setattr(cli, "chay_tu_dong_toan_bo", lambda: da_goi.append(1))
        monkeypatch.setattr(sys, "argv", ["cli", "--auto"])
        cli.main()
        assert da_goi == [1]

    def test_thu_tu_trong_che_do_auto(self, monkeypatch, capsys):
        thu_tu = []
        for ten in ("demo_1_dh_nho", "demo_2_dh_lon_va_ban_ro", "demo_3_tep_that", "demo_4_mitm",
                    "demo_5_phong_chong_mitm", "demo_eve_crack", "demo_pohlig_hellman_compare", "run_bsgs_benchmark"):
            monkeypatch.setattr(cli, ten, lambda *a, _t=ten, **k: thu_tu.append((_t, a, k)))
        cli.chay_tu_dong_toan_bo()
        assert [t[0] for t in thu_tu] == [
            "demo_1_dh_nho", "demo_2_dh_lon_va_ban_ro", "demo_3_tep_that", "demo_4_mitm",
            "demo_5_phong_chong_mitm", "demo_eve_crack", "demo_pohlig_hellman_compare", "run_bsgs_benchmark"]
        assert thu_tu[0][2] == {"auto": True} and thu_tu[-1][2] == {"repeats": 2}
        assert "HOÀN TẤT" in capsys.readouterr().out


@pytest.mark.cham
def test_chay_auto_dau_cuoi(thu_muc_tam):
    """Chạy thật `python -m app.cli --auto` trong thư mục tạm (khoảng 10 giây)."""
    goc = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env = dict(os.environ, PYTHONPATH=goc, PYTHONIOENCODING="utf-8")
    kq = subprocess.run([sys.executable, "-m", "app.cli", "--auto"], cwd=thu_muc_tam, env=env,
                        capture_output=True, text=True, encoding="utf-8", timeout=240)
    assert kq.returncode == 0, kq.stderr[-500:]
    assert "Traceback" not in kq.stdout + kq.stderr
    assert "HOÀN TẤT" in kq.stdout
    for muc in ("MỤC 1", "MỤC 2", "MỤC 3", "DEMO 7A", "DEMO 7B", "MỤC 8"):
        assert muc in kq.stdout, muc
    assert (thu_muc_tam / "docs" / "benchmark.csv").exists()
    assert (thu_muc_tam / "samples" / "anh_mau_khoi_phuc.png").exists()
