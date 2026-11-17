"""
Kiểm thử app/gui.py : kiểm tra tham số, luồng chạy nền, các job demo.

Các test KHÔNG mở cửa sổ thật: đối tượng giao diện được dựng bằng object.__new__ với ô nhập giả,
nên chạy được cả khi máy không có màn hình. Nếu máy không có tkinter thì dùng tkinter giả tối thiểu.
Quy ước: pow() chỉ dùng trong tests/ để đối chiếu.
"""
import contextlib
import io
import os
import queue
import re
import sys
import threading
import time
import types

import pytest


def _cai_tkinter_gia_neu_thieu():
    try:
        import tkinter  # noqa: F401
        from tkinter import messagebox, filedialog, ttk  # noqa: F401
        return
    except ImportError:
        pass

    class W:
        def __init__(self, *a, **k):
            pass

        def __getattr__(self, ten):
            return lambda *a, **k: None

    tk = types.ModuleType("tkinter")
    tk.Tk = W
    for ten in ("Frame", "Label", "Entry", "Button", "Text", "Scrollbar", "LabelFrame", "StringVar", "PhotoImage"):
        setattr(tk, ten, W)
    for ten, gia_tri in dict(END="end", LEFT="left", RIGHT="right", X="x", Y="y", BOTH="both", FLAT="flat",
                             WORD="word", DISABLED="disabled", NORMAL="normal").items():
        setattr(tk, ten, gia_tri)
    ttk = types.ModuleType("tkinter.ttk")
    ttk.Notebook = W
    mb, fd = types.ModuleType("tkinter.messagebox"), types.ModuleType("tkinter.filedialog")
    tk.ttk, tk.messagebox, tk.filedialog = ttk, mb, fd
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": mb, "tkinter.filedialog": fd})


_cai_tkinter_gia_neu_thieu()
from app import gui as G  # noqa: E402
from core import dh  # noqa: E402


# ---------------------------------------------------------------- ĐỒ GIẢ
class Var:
    def __init__(self, v):
        self.v = str(v)

    def get(self):
        return self.v


class ManHinh:
    def __init__(self):
        self.t = ""

    def insert(self, _vi_tri, noi_dung):
        self.t += noi_dung

    def see(self, _):
        pass

    def delete(self, *a):
        self.t = ""


class Nut:
    def __init__(self):
        self.state = "normal"
        self.text = ""

    def config(self, **k):
        self.state = k.get("state", self.state)
        self.text = k.get("text", self.text)


class Tab:
    def __init__(self):
        self.da_chon = []

    def select(self, i):
        self.da_chon.append(i)


@pytest.fixture
def hop_thoai(monkeypatch):
    """Bắt các hộp thoại: danh sách (loại, nội dung)."""
    ds = []
    for ten in ("showerror", "showwarning", "showinfo"):
        monkeypatch.setattr(G.messagebox, ten, lambda t, m, _l=ten: ds.append((_l, m)), raising=False)
    return ds


@pytest.fixture
def tao():
    def _tao(p=23, g=5, a=6, b=15, c=3, dp=10007, dg=5, dA=6518, tin="Chuyen 5,000,000 VND cho Bob"):
        o = object.__new__(G.DiffieHellmanGUI)
        o.var_p, o.var_g, o.var_a, o.var_b, o.var_c = Var(p), Var(g), Var(a), Var(b), Var(c)
        o.var_dlog_p, o.var_dlog_g, o.var_dlog_A = Var(dp), Var(dg), Var(dA)
        o.var_msg = Var(tin)
        o.txt_out, o.notebook = ManHinh(), Tab()
        o._busy, o._q, o._on_done = False, queue.Queue(), None
        o._action_buttons = [Nut(), Nut()]
        o.lbl_status = Nut()
        o.after = lambda *a, **k: None
        o.da_goi_async = []
        return o
    return _tao


def doi_chay_xong(o, gioi_han=180):
    """Chờ luồng nền xong rồi đưa kết quả lên màn hình (thay cho vòng lặp after của Tk)."""
    t = time.time()
    while o._busy and time.time() - t < gioi_han:
        o._drain_queue()
        time.sleep(0.02)
    assert not o._busy, "luồng nền không kết thúc"


def chay_job(job):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        job()
    return buf.getvalue()


# ---------------------------------------------------------------- 1. KIỂM TRA THAM SỐ (Mục 1, 4, 5)
BANG_THAM_SO = [
    # (mô tả, (p, g, a, b, c), có hợp lệ không)
    ("mặc định", (23, 5, 6, 15, 3), True),
    ("khoá nhỏ nhất hợp lệ", (23, 5, 2, 3, 3), True),
    ("khoá lớn nhất hợp lệ a = p-2 (A = 14)", (23, 5, 21, 15, 3), True),
    ("a = p-1 = 22", (23, 5, 22, 15, 3), False),
    ("a = 1", (23, 5, 1, 15, 3), False),
    ("a = 0", (23, 5, 0, 15, 3), False),
    ("a âm", (23, 5, -4, 15, 3), False),
    ("b = 1", (23, 5, 6, 1, 3), False),
    ("c = p-1", (23, 5, 6, 15, 22), False),
    ("p hợp số", (24, 5, 6, 15, 3), False),
    ("p = 1", (1, 1, 1, 1, 1), False),
    ("p = 3 quá nhỏ", (3, 2, 2, 2, 2), False),
    ("g = 1", (23, 1, 6, 15, 3), False),
    ("g = p", (23, 23, 6, 15, 3), False),
    ("g không phải căn nguyên thuỷ", (23, 2, 6, 15, 3), False),
    ("A = p-1 (a = (p-1)/2 = 11)", (23, 5, 11, 15, 3), False),
    ("B = p-1 (b = 11)", (23, 5, 6, 11, 3), False),
    ("p=11,g=2,a=5 cho A = 10 = p-1", (11, 2, 5, 3, 3), False),
    ("p=7,g=3,a=3 cho A = 6 = p-1", (7, 3, 3, 2, 2), False),
    ("chữ thay số", (23, 5, "abc", 15, 3), False),
    ("ô trống", (23, 5, "", 15, 3), False),
    ("số thực", (23, 5, "6.5", 15, 3), False),
]


class TestKiemTraThamSo:
    @pytest.mark.parametrize("mo_ta,tham_so,hop_le", BANG_THAM_SO, ids=[b[0] for b in BANG_THAM_SO])
    def test_bang_tham_so(self, mo_ta, tham_so, hop_le, tao, hop_thoai):
        kq = tao(*tham_so)._validate_all_inputs(need_c=True)
        assert (kq is not None) == hop_le
        assert bool(hop_thoai) == (not hop_le)

    def test_tra_ve_dung_gia_tri(self, tao):
        assert tao()._validate_all_inputs() == (23, 5, 6, 15, 3, "g = 5 là phần tử sinh nguyên thủy hợp lệ của Z_23*.")

    def test_khong_can_c_thi_bo_qua_c(self, tao, hop_thoai):
        kq = tao(c="")._validate_all_inputs(need_c=False)
        assert kq is not None and kq[4] is None and not hop_thoai

    def test_can_c_ma_c_trong_thi_bao_loi(self, tao, hop_thoai):
        assert tao(c="")._validate_all_inputs(need_c=True) is None
        assert hop_thoai and "c" in hop_thoai[0][1]

    def test_loi_hien_tren_man_hinh_va_hop_thoai(self, tao, hop_thoai):
        o = tao(a=22)
        assert o._validate_all_inputs() is None
        assert "KIỂM TRA THAM SỐ THẤT BẠI" in o.txt_out.t and "a" in o.txt_out.t
        assert hop_thoai[0][0] == "showwarning" and "22" in hop_thoai[0][1]

    def test_nhieu_loi_cung_luc(self, tao, hop_thoai):
        o = tao(p=23, g=2, a=22, b=0)
        assert o._validate_all_inputs() is None
        dong_loi = [d for d in hop_thoai[0][1].splitlines() if d.startswith("- ")]
        assert len(dong_loi) == 3                         # g không phải căn nguyên thuỷ, a = 22, b = 0

    def test_p_lon_khong_kiem_tra_can_nguyen_thuy(self, tao, hop_thoai):
        # p = 2^61 - 1 vượt giới hạn phân tích: chỉ ghi chú, không báo lỗi
        p = 2 ** 61 - 1
        kq = tao(p=p, g=3, a=12345, b=67890, c=555)._validate_all_inputs()
        assert kq is not None and "quá lớn" in kq[5] and not hop_thoai

    def test_p_hop_so_bao_loi_nguyen_to(self, tao, hop_thoai):
        o = tao(p=24)
        assert o._validate_all_inputs() is None
        assert "KHÔNG PHẢI SỐ NGUYÊN TỐ" in hop_thoai[0][1]


class TestCheckPrimitiveRoot:
    def test_cac_truong_hop(self):
        assert G.check_primitive_root(5, 23)[0] is True
        assert G.check_primitive_root(2, 23)[0] is False
        assert G.check_primitive_root(3, 2 ** 61 - 1)[0] is None
        for g in range(2, 23):
            kq, _ = G.check_primitive_root(g, 23)
            assert kq == (len({pow(g, k, 23) for k in range(1, 23)}) == 22)


class TestKiemTra2048:
    def test_hop_le(self, tao, hop_thoai):
        assert tao(a=12345678901234567890, b=98765432109876543210)._validate_2048() == (12345678901234567890, 98765432109876543210)
        assert not hop_thoai

    @pytest.mark.parametrize("a,b", [(1, 5), (5, 1), (0, 5), (-3, 5), (dh.RFC_3526_2048_P - 1, 5), (5, dh.RFC_3526_2048_P)])
    def test_khoa_ngoai_khoang(self, a, b, tao, hop_thoai):
        assert tao(a=a, b=b)._validate_2048() is None
        assert hop_thoai

    def test_khong_so(self, tao, hop_thoai):
        assert tao(a="xx")._validate_2048() is None and hop_thoai

    def test_a_lon_p_tru_2_hop_le(self, tao, hop_thoai):
        P = dh.RFC_3526_2048_P
        kq = tao(a=P - 2, b=P - 3)._validate_2048()
        # g = 2 sinh nhóm con bậc q = (P-1)/2, nên mọi luỹ thừa của 2 đều thuộc nhóm con và hợp lệ
        assert kq == (P - 2, P - 3) and not hop_thoai


# ---------------------------------------------------------------- 2. NÚT BẤM: KIỂM TRA + CHẠY NỀN
class TestNutBam:
    def test_chan_tham_so_sai_khong_chay_nen(self, tao, hop_thoai):
        o = tao(a=22)
        goi = []
        o._run_async = lambda *a, **k: goi.append(a)
        for ten in ("run_muc_1", "run_muc_4", "run_muc_5", "run_all_auto"):
            getattr(o, ten)()
        assert goi == []

    def test_tham_so_dung_goi_run_async_mot_job(self, tao):
        for ten in ("run_muc_1", "run_muc_4", "run_muc_5", "run_muc_7"):
            o = tao()
            goi = []
            o._run_async = lambda jobs, on_done=None, _g=goi: _g.append((len(jobs), on_done))
            getattr(o, ten)()
            assert goi == [(1, None)], ten

    def test_muc_2_dung_khoa_2048(self, tao, hop_thoai):
        o = tao(a=7, b=9, c="")                       # c trống không ảnh hưởng Mục 2
        goi = []
        o._run_async = lambda jobs, on_done=None: goi.append(jobs)
        o.run_muc_2()
        assert len(goi) == 1 and not hop_thoai

    def test_muc_1_khong_can_c(self, tao, hop_thoai):
        o = tao(c="")
        goi = []
        o._run_async = lambda jobs, on_done=None: goi.append(jobs)
        o.run_muc_1()
        assert len(goi) == 1 and not hop_thoai

    def test_muc_8_gan_hien_bieu_do(self, tao):
        o = tao()
        goi = []
        o._run_async = lambda jobs, on_done=None: goi.append(on_done)
        o.run_muc_8()
        assert goi == [o._hien_bieu_do]

    def test_run_all_auto_mot_lan_kiem_tra_bay_job(self, tao, hop_thoai):
        o = tao()
        goi = []
        o._run_async = lambda jobs, on_done=None: goi.append((len(jobs), on_done))
        o.run_all_auto()
        assert goi == [(7, o._hien_bieu_do)] and not hop_thoai

    def test_run_all_auto_truyen_dung_tham_so_cho_tung_job(self, tao, monkeypatch):
        ghi = {}
        for ten in ("_job_muc_1", "_job_muc_2", "_job_muc_4", "_job_muc_5"):
            monkeypatch.setattr(G.DiffieHellmanGUI, ten,
                                staticmethod(lambda *a, _t=ten: ghi.setdefault(_t, a) and (lambda: None)))
        o = tao(p=101, g=2, a=7, b=9, c=11, tin="tin rieng")
        o._run_async = lambda jobs, on_done=None: None
        o.run_all_auto()
        assert ghi["_job_muc_1"][:4] == (101, 2, 7, 9)
        assert ghi["_job_muc_2"] == (7, 9, "tin rieng")           # Mục 2 dùng đúng khoá a, b người dùng nhập
        assert ghi["_job_muc_4"] == (101, 2, 7, 9, 11, "tin rieng")
        assert ghi["_job_muc_5"] == (101, 2, 7, 9, 11)

    def test_run_all_auto_tham_so_sai_chi_mot_hop_thoai(self, tao, hop_thoai):
        o = tao(a=22)
        o._run_async = lambda *a, **k: pytest.fail("không được chạy khi tham số sai")
        o.run_all_auto()
        assert len(hop_thoai) == 1

    def test_run_all_auto_xoa_man_hinh(self, tao):
        o = tao()
        o.txt_out.t = "cũ"
        o._run_async = lambda *a, **k: None
        o.run_all_auto()
        assert o.txt_out.t == ""

    def test_muc_6_bang_kiem_tra(self, tao, hop_thoai):
        cac_ca = [
            (dict(dp=10), True), (dict(dp=4), True), (dict(dp=2 ** 61 - 1, dg=3, dA=7), True),
            (dict(dp=10 ** 12 + 39), True), (dict(dg=1), True), (dict(dg=10007), True), (dict(dA=0), True),
            (dict(dA=10007), True), (dict(dp="abc"), True), (dict(dA=""), True),
            ({}, False), (dict(dp=23, dg=2, dA=5), False), (dict(dp=101, dg=2, dA=100), False),
        ]
        for tham_so, bi_chan in cac_ca:
            hop_thoai.clear()
            o = tao(**tham_so)
            goi = []
            o._run_async = lambda jobs, on_done=None, _g=goi: _g.append(jobs)
            o.run_muc_6()
            assert (not goi) == bi_chan, tham_so
            assert bool(hop_thoai) == bi_chan, tham_so

    def test_p_muc_6_dung_bang_10_mu_12_nguyen_to(self, tao, hop_thoai):
        p = 999999999989                                  # số nguyên tố lớn nhất dưới 10^12
        o = tao(dp=p, dg=3, dA=12345)
        goi = []
        o._run_async = lambda jobs, on_done=None: goi.append(jobs)
        o.run_muc_6()
        assert len(goi) == 1 and not hop_thoai

    def test_kiem_tra_tham_so_hien_bao_cao(self, tao, hop_thoai):
        o = tao()
        o.check_params_button()
        assert hop_thoai[-1][0] == "showinfo"
        assert "HỢP LỆ" in o.txt_out.t and "validate_pub" in o.txt_out.t
        assert "Cảnh báo (không chặn)" in o.txt_out.t     # p = 23 chỉ 5 bit

    def test_kiem_tra_tham_so_sai_hien_loi(self, tao, hop_thoai):
        o = tao(a=22)
        o.check_params_button()
        assert hop_thoai[-1][0] == "showwarning"

    def test_nut_kiem_tra_bi_khoa_khi_ban(self, tao, hop_thoai):
        o = tao()
        o._busy = True
        o.check_params_button()
        assert hop_thoai == [] and o.txt_out.t == ""


# ---------------------------------------------------------------- 3. LUỒNG NỀN
class TestLuongNen:
    def test_chay_lan_luot_va_khoa_nut(self, tao, hop_thoai):
        o = tao()
        trinh_tu = []
        jobs = [lambda: print("một"), lambda: print("hai"), lambda: print("ba")]
        o._run_async(jobs, on_done=lambda: trinh_tu.append("xong"))
        assert o._busy and all(b.state == "disabled" for b in o._action_buttons)
        assert "Đang chạy" in o.lbl_status.text
        doi_chay_xong(o)
        assert o.txt_out.t.index("một") < o.txt_out.t.index("hai") < o.txt_out.t.index("ba")
        assert not o._busy and all(b.state == "normal" for b in o._action_buttons)
        assert o.lbl_status.text == ""
        assert trinh_tu == ["xong"]
        assert o._on_done is None

    def test_job_chay_o_luong_khac_luong_chinh(self, tao):
        o = tao()
        ten_luong = []
        o._run_async([lambda: ten_luong.append(threading.current_thread() is threading.main_thread())])
        doi_chay_xong(o)
        assert ten_luong == [False]

    def test_chuyen_sang_tab_ket_qua(self, tao):
        o = tao()
        o._run_async([lambda: None])
        doi_chay_xong(o)
        assert o.notebook.da_chon == [0]

    def test_loi_trong_job_duoc_bat(self, tao, hop_thoai):
        o = tao()
        da_chay = []

        def hong():
            print("in dở dang")
            raise RuntimeError("lỗi giả lập")
        o._run_async([hong, lambda: da_chay.append("job sau")], on_done=lambda: da_chay.append("on_done"))
        doi_chay_xong(o)
        assert "in dở dang" in o.txt_out.t and "lỗi giả lập" in o.txt_out.t
        assert "LỖI THỰC THI" in o.txt_out.t
        assert hop_thoai and hop_thoai[0][0] == "showerror"
        assert "job sau" not in da_chay                   # lỗi dừng các job phía sau
        assert da_chay == ["on_done"]                     # nhưng vẫn mở khoá nút và gọi on_done
        assert not o._busy

    def test_khong_chay_hai_mục_cung_luc(self, tao, hop_thoai):
        o = tao()
        o._busy = True
        da_chay = []
        o._run_async([lambda: da_chay.append(1)])
        assert da_chay == [] and hop_thoai[0][0] == "showinfo"

    def test_job_khong_cham_vao_giao_dien(self):
        # job chạy ở luồng nền nên phải là staticmethod (không nhận self, không đụng widget)
        for ten in dir(G.DiffieHellmanGUI):
            if ten.startswith("_job_muc_"):
                assert isinstance(G.DiffieHellmanGUI.__dict__[ten], staticmethod), ten

    def test_drain_queue_rong(self, tao):
        assert tao()._drain_queue() is False

    def test_poll_dat_lai_lich_khi_chua_xong(self, tao):
        o = tao()
        lich = []
        o.after = lambda ms, f: lich.append((ms, f))
        o._poll()
        assert lich == [(100, o._poll)]
        o._q.put(("done",))
        lich.clear()
        o._poll()
        assert lich == []

    def test_on_done_goi_dung_mot_lan(self, tao):
        o = tao()
        dem = []
        o._on_done = lambda: dem.append(1)
        o._busy = True
        o._q.put(("done",))
        o._drain_queue()
        o._q.put(("done",))
        o._drain_queue()
        assert dem == [1]


# ---------------------------------------------------------------- 4. CÁC JOB DEMO
class TestJob:
    def test_job_1(self):
        out = chay_job(G.DiffieHellmanGUI._job_muc_1(23, 5, 6, 15, "g = 5 hợp lệ"))
        assert "A (Khóa công khai Alice) = 8" in out and "B (Khóa công khai Bob) = 19" in out
        assert "K_Alice = 2, K_Bob = 2" in out and "[FD65]" in out and "g = 5 hợp lệ" in out

    def test_job_1_tham_so_khac(self):
        out = chay_job(G.DiffieHellmanGUI._job_muc_1(101, 2, 17, 33, ""))
        K = pow(pow(2, 17, 101), 33, 101)
        assert f"K_Alice = {K}, K_Bob = {K}" in out

    def test_job_2(self):
        out = chay_job(G.DiffieHellmanGUI._job_muc_2(123456789, 987654321, "Chào Thầy Cô!"))
        assert "2048 bits" in out and "KHÔI PHỤC ĐÚNG 100%" in out and "Chào Thầy Cô!" in out

    def test_job_2_khoa_chung_khop(self):
        a, b = 12345, 67890
        P, G2 = dh.RFC_3526_2048_P, dh.RFC_3526_2048_G
        K = pow(pow(G2, b, P), a, P)
        out = chay_job(G.DiffieHellmanGUI._job_muc_2(a, b, "x"))
        assert hex(K)[:24] in out

    def test_job_3(self, thu_muc_tam):
        out = chay_job(G.DiffieHellmanGUI._job_muc_3())
        assert out.count("khôi phục đúng") == 2
        assert os.path.exists(os.path.join("samples", "anh_mau_khoi_phuc.png"))

    def test_job_4(self):
        out = chay_job(G.DiffieHellmanGUI._job_muc_4(23, 5, 6, 15, 3, "Chuyen 5,000,000 VND cho Bob"))
        assert "K_Alice = 6" in out and "K_Mal_Bob = 5" in out
        assert "'Chuyen 5,000,000 VND cho Bob'" in out
        assert "'Chuyen 99,000,000 VND cho tai khoan MALLORY'" in out
        assert "Bob hoàn toàn không biết" in out

    def test_job_5(self):
        out = chay_job(G.DiffieHellmanGUI._job_muc_5(23, 5, 6, 15, 3))
        assert "LỆCH, phát hiện MITM" in out and "chữ ký cũ): False" in out

    def test_job_6(self):
        out = chay_job(G.DiffieHellmanGUI._job_muc_6(10007, 5, 6518))
        assert "a = 6919" in out and f"= {pow(5, 6919, 10007)}" in out

    def test_job_6_khong_nghiem(self):
        assert "Không tồn tại" in chay_job(G.DiffieHellmanGUI._job_muc_6(23, 2, 5))

    def test_job_7(self):
        out = chay_job(G.DiffieHellmanGUI._job_muc_7())
        assert "DEMO 7A" in out and "DEMO 7B" in out and out.count("(đúng)") == 2

    def test_job_8(self, thu_muc_tam):
        out = chay_job(G.DiffieHellmanGUI._job_muc_8())
        assert "MỤC 8" in out and os.path.exists(os.path.join("docs", "benchmark.csv"))


# ---------------------------------------------------------------- 5. HIỂN THỊ ẢNH VÀ QUY ƯỚC
class TestHienThiAnh:
    def test_thieu_tep_bao_cho_nguoi_dung(self, tao, hop_thoai):
        tao().show_image(os.path.join("khong", "co.png"))
        assert hop_thoai[0][0] == "showinfo" and "Chưa có tệp" in hop_thoai[0][1]

    def test_hien_bieu_do_chi_khi_co_tep(self, tao, thu_muc_tam, hop_thoai):
        o = tao()
        o._hien_bieu_do()
        assert hop_thoai == []                              # chưa có docs/benchmark.png thì im lặng


class TestQuyUoc:
    def _ma_nguon(self):
        with open(G.__file__, encoding="utf-8") as f:
            return f.read()

    def test_khong_dung_pow_va_hashlib(self):
        ma = self._ma_nguon()
        assert not re.search(r"(?<![\w.])pow\(", ma)
        assert "hashlib" not in ma

    def test_dung_backend_matplotlib_khong_giao_dien_truoc_khi_nap_benchmark(self):
        ma = self._ma_nguon()
        assert 'matplotlib.use("Agg")' in ma
        assert ma.index('matplotlib.use("Agg")') < ma.index("from app.benchmark import")

    def test_dung_lai_ham_cua_core(self):
        for ten in ("mod_exp", "validate_pub", "validate_dh_params", "is_prime_miller_rabin",
                    "la_can_nguyen_thuy", "canh_bao_tham_so", "run_mitm_simulation", "run_defense_simulation"):
            assert getattr(G, ten) is getattr(dh, ten)

    def test_gioi_han_hang_so(self):
        assert G.GIOI_HAN_P_BSGS == 10 ** 12
        assert G.KHOA_TOI_THIEU == 2
