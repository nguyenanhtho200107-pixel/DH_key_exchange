"""
Kiểm thử app/gui.py: kiểm tra tham số (Mục 1, 2, 4, 5, 6), luồng chạy nền, các job demo,
tab "Mô phỏng Trao đổi 2 bên" (hàm thuần sim_* và các hàm _sim_*), hiển thị ảnh, chọn tệp.

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
    ttk.Combobox = W
    mb, fd = types.ModuleType("tkinter.messagebox"), types.ModuleType("tkinter.filedialog")
    tk.ttk, tk.messagebox, tk.filedialog = ttk, mb, fd
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": mb, "tkinter.filedialog": fd})


_cai_tkinter_gia_neu_thieu()
from app import gui as G  # noqa: E402
from core import dh  # noqa: E402


# ---------------------------------------------------------------- ĐỒ GIẢ
class Var:
    """StringVar giả (có cả get và set)."""

    def __init__(self, v):
        self.v = str(v)

    def get(self):
        return self.v

    def set(self, v):
        self.v = str(v)


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
def thu_muc_tam(tmp_path, monkeypatch):
    """Chạy test trong thư mục tạm: code ghi vào samples/ và docs/ theo đường dẫn tương đối.
    (Nếu tests/conftest.py đã có fixture cùng tên thì có thể xoá đoạn này.)"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


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
        o.lbl_img_canvas, o.lbl_img_status = Nut(), Nut()
        o._img_ref = None
        o.after = lambda *a, **k: None
        return o
    return _tao


@pytest.fixture
def tao_sim():
    """Giao diện giả cho tab Mô phỏng: các ô nhập/hiển thị là Var giả, nhật ký là ManHinh giả."""
    def _tao(p=23, g=5, a=6, b=15):
        o = object.__new__(G.DiffieHellmanGUI)
        o.sim_p, o.sim_g, o.sim_a, o.sim_b = Var(p), Var(g), Var(a), Var(b)
        o.sim_preset = Var("(p = 23, g = 5)")
        for ten in ("sim_A_pub", "sim_B_pub", "sim_A_recv", "sim_B_recv", "sim_Ka", "sim_Kb"):
            setattr(o, ten, Var(""))
        o.sim_log = ManHinh()
        o._sim = {"A": None, "B": None}
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

    def test_muc_3_goi_run_async_mot_job(self, tao):
        o = tao()
        goi = []
        o._run_async = lambda jobs, on_done=None: goi.append((len(jobs), on_done))
        o.run_muc_3()
        assert goi == [(1, None)]

    def test_muc_2_dung_khoa_2048(self, tao, hop_thoai):
        o = tao(a=7, b=9, c="")                       # c trống không ảnh hưởng Mục 2
        goi = []
        o._run_async = lambda jobs, on_done=None: goi.append(jobs)
        o.run_muc_2()
        assert len(goi) == 1 and not hop_thoai

    def test_muc_2_khoa_sai_khong_chay(self, tao, hop_thoai):
        o = tao(a=1)
        o._run_async = lambda *a, **k: pytest.fail("không được chạy khi khoá sai")
        o.run_muc_2()
        assert hop_thoai

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

    def test_khong_chay_hai_muc_cung_luc(self, tao, hop_thoai):
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

    def test_set_busy_khoa_va_mo_nut(self, tao):
        o = tao()
        o._set_busy(True)
        assert o._busy and all(b.state == "disabled" for b in o._action_buttons)
        assert "Đang chạy" in o.lbl_status.text
        o._set_busy(False)
        assert not o._busy and all(b.state == "normal" for b in o._action_buttons)
        assert o.lbl_status.text == ""


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
        # kiểm tra tính chất thay vì cứng giá trị: a tìm được phải thoả g^a = A (mod p)
        out = chay_job(G.DiffieHellmanGUI._job_muc_6(10007, 5, 6518))
        m = re.search(r"khóa riêng a = (\d+)", out)
        assert m, out
        a = int(m.group(1))
        assert pow(5, a, 10007) == 6518
        assert f"= {pow(5, a, 10007)}" in out

    def test_job_6_khong_nghiem(self):
        assert "Không tồn tại" in chay_job(G.DiffieHellmanGUI._job_muc_6(23, 2, 5))

    def test_job_7(self):
        out = chay_job(G.DiffieHellmanGUI._job_muc_7())
        assert "DEMO 7A" in out and "DEMO 7B" in out and out.count("(đúng)") == 2

    def test_job_8(self, thu_muc_tam):
        out = chay_job(G.DiffieHellmanGUI._job_muc_8())
        assert "MỤC 8" in out and os.path.exists(os.path.join("docs", "benchmark.csv"))


# ---------------------------------------------------------------- 5. TAB MÔ PHỎNG: HÀM THUẦN
class TestSimHamThuan:
    def test_kiem_tra_khoa_hop_le(self):
        assert G.sim_kiem_tra_khoa(23, 5, 6, "a") == (8, None)
        assert G.sim_kiem_tra_khoa(23, 5, 2, "a") == (2, None)           # khoá nhỏ nhất
        assert G.sim_kiem_tra_khoa(23, 5, 21, "a") == (pow(5, 21, 23), None)   # khoá lớn nhất p-2

    @pytest.mark.parametrize("k", [-1, 0, 1, 22, 23, 100])
    def test_kiem_tra_khoa_ngoai_khoang(self, k):
        y, loi = G.sim_kiem_tra_khoa(23, 5, k, "a")
        assert y is None and loi and "phải nằm trong" in loi

    def test_kiem_tra_khoa_cho_khoa_cong_khai_yeu(self):
        y, loi = G.sim_kiem_tra_khoa(23, 5, 11, "a")                     # A = 5^11 = 22 = p-1
        assert y is None and "ngoài" in loi
        y, loi = G.sim_kiem_tra_khoa(5, 2, 2, "b")                       # 2^2 = 4 = p-1
        assert y is None and loi

    def test_kiem_tra_khoa_ten_xuat_hien_trong_loi(self):
        _, loi = G.sim_kiem_tra_khoa(23, 5, 0, "a (Bên A)")
        assert "a (Bên A)" in loi

    def test_khoa_hop_le(self):
        assert G.sim_khoa_hop_le(23, 5, 6) == 6
        assert G.sim_khoa_hop_le(23, 5, 6, tranh=6) == 2                 # nhỏ nhất hợp lệ, khác 6
        assert G.sim_khoa_hop_le(23, 5, 11) == 2                         # 11 cho A = p-1 nên bị bỏ
        assert G.sim_khoa_hop_le(23, 5, 99) == 2                         # ngoài khoảng
        assert G.sim_khoa_hop_le(23, 5) == 2                             # không mong muốn gì

    def test_khoa_hop_le_p_rat_nho(self):
        # p = 5, g = 2: chỉ k = 3 hợp lệ (k = 2 cho A = 4 = p-1)
        assert G.sim_khoa_hop_le(5, 2) == 3
        assert G.sim_khoa_hop_le(5, 2, 3, tranh=3) == 3                  # không còn lựa chọn khác thì vẫn trả về 3

    def test_khoa_hop_le_khong_co_khoa_nao(self):
        assert G.sim_khoa_hop_le(3, 2) is None                           # [2, p-2] rỗng

    def test_cap_khoa_mac_dinh(self):
        assert G.sim_cap_khoa_mac_dinh(23, 5) == (6, 15)

    @pytest.mark.parametrize("p,g", [(5, 2), (7, 3), (13, 2), (23, 5), (29, 2)])
    def test_cap_khoa_mac_dinh_cac_preset(self, p, g):
        a, b = G.sim_cap_khoa_mac_dinh(p, g)
        assert a is not None and b is not None
        assert G.sim_kiem_tra_khoa(p, g, a, "a")[1] is None
        assert G.sim_kiem_tra_khoa(p, g, b, "b")[1] is None
        K = pow(pow(g, a, p), b, p)
        assert K not in (1, p - 1)                                       # khoá chung không tầm thường

    def test_cap_khoa_mac_dinh_khong_co_khoa(self):
        assert G.sim_cap_khoa_mac_dinh(3, 2) == (None, None)

    def test_cap_khoa_mac_dinh_uu_tien_a_b_khac_nhau(self):
        a, b = G.sim_cap_khoa_mac_dinh(23, 5)
        assert a != b

    @pytest.mark.parametrize("p,g", [(23, 5), (5, 2), (7, 3), (101, 2)])
    def test_khoa_ngau_nhien_luon_hop_le(self, p, g):
        for _ in range(30):
            k = G.sim_khoa_ngau_nhien(p, g)
            assert k is not None
            assert G.sim_kiem_tra_khoa(p, g, k, "a")[1] is None


# ---------------------------------------------------------------- 6. TAB MÔ PHỎNG: GIAO DIỆN
class TestSimGetPg:
    def test_hop_le(self, tao_sim, hop_thoai):
        assert tao_sim()._sim_get_pg() == (23, 5)
        assert hop_thoai == []

    @pytest.mark.parametrize("p,g", [("abc", 5), (23, "xyz"), ("", 5), (23, ""), ("2.5", 5)])
    def test_khong_phai_so_nguyen(self, p, g, tao_sim, hop_thoai):
        assert tao_sim(p=p, g=g)._sim_get_pg() is None
        assert len(hop_thoai) == 1 and hop_thoai[0][0] == "showerror"

    @pytest.mark.parametrize("p", [24, 3, 1, 0, -7, 15])
    def test_p_khong_hop_le(self, p, tao_sim, hop_thoai):
        assert tao_sim(p=p, g=2)._sim_get_pg() is None
        assert len(hop_thoai) == 1 and hop_thoai[0][0] == "showwarning"
        assert "p" in hop_thoai[0][1]

    @pytest.mark.parametrize("g", [1, 0, -1, 23, 24])
    def test_g_ngoai_khoang(self, g, tao_sim, hop_thoai):
        assert tao_sim(g=g)._sim_get_pg() is None
        assert len(hop_thoai) == 1 and hop_thoai[0][0] == "showwarning"

    def test_g_khong_phai_can_nguyen_thuy(self, tao_sim, hop_thoai):
        assert tao_sim(g=2)._sim_get_pg() is None                        # 2 không phải căn nguyên thuỷ mod 23
        assert len(hop_thoai) == 1 and "KHÔNG phải" in hop_thoai[0][1]


class TestSimKiemTraPG:
    def test_kiem_tra_p_hop_le(self, tao_sim, hop_thoai):
        o = tao_sim()
        o._sim_check_p()
        assert hop_thoai[-1][0] == "showinfo" and "số nguyên tố hợp lệ" in o.sim_log.t

    def test_kiem_tra_p_hop_so(self, tao_sim, hop_thoai):
        o = tao_sim(p=24)
        o._sim_check_p()
        assert hop_thoai[-1][0] == "showwarning" and "KHÔNG phải số nguyên tố" in o.sim_log.t

    def test_kiem_tra_p_nho_hon_5(self, tao_sim, hop_thoai):
        tao_sim(p=3)._sim_check_p()
        assert hop_thoai[-1][0] == "showwarning"

    def test_kiem_tra_p_khong_phai_so(self, tao_sim, hop_thoai):
        tao_sim(p="abc")._sim_check_p()
        assert hop_thoai[-1][0] == "showerror"

    def test_kiem_tra_g_hop_le(self, tao_sim, hop_thoai):
        o = tao_sim()
        o._sim_check_g()
        assert len(hop_thoai) == 1 and hop_thoai[0][0] == "showinfo"
        assert "phần tử sinh" in hop_thoai[0][1] and "[Kiểm tra g]" in o.sim_log.t

    def test_kiem_tra_g_sai_chi_mot_hop_thoai(self, tao_sim, hop_thoai):
        o = tao_sim(g=2)
        o._sim_check_g()
        assert len(hop_thoai) == 1 and hop_thoai[0][0] == "showwarning"


class TestSimKhoaNgauNhien:
    def test_dien_khoa_hop_le(self, tao_sim, hop_thoai):
        o = tao_sim(a=0, b=0)
        o._sim_rand("A")
        o._sim_rand("B")
        for ten, var in (("a", o.sim_a), ("b", o.sim_b)):
            assert G.sim_kiem_tra_khoa(23, 5, int(var.get()), ten)[1] is None
        assert hop_thoai == []

    def test_pg_sai_khong_doi_khoa(self, tao_sim, hop_thoai):
        o = tao_sim(p=24)
        o._sim_rand("A")
        assert o.sim_a.get() == "6" and len(hop_thoai) == 1


class TestSimTraoDoi:
    def test_trao_doi_ca_hai_ben(self, tao_sim, hop_thoai):
        o = tao_sim()
        o._sim_exchange_both()
        K = pow(pow(5, 15, 23), 6, 23)
        assert (o.sim_A_pub.get(), o.sim_B_pub.get()) == ("8", "19")
        assert (o.sim_A_recv.get(), o.sim_B_recv.get()) == ("8", "19")
        assert o.sim_Ka.get() == o.sim_Kb.get() == str(K) == "2"
        assert "Hoàn tất" in o.sim_log.t and "SAS" in o.sim_log.t
        assert hop_thoai == []

    def test_khoa_sai_chi_mot_hop_thoai_va_khong_gui(self, tao_sim, hop_thoai):
        o = tao_sim(a=22, b=0)
        o._sim_exchange_both()
        assert len(hop_thoai) == 1 and hop_thoai[0][0] == "showwarning"
        dong_loi = [d for d in hop_thoai[0][1].splitlines() if d.startswith("- ")]
        assert len(dong_loi) == 2                                        # a = 22 và b = 0
        assert o._sim == {"A": None, "B": None}
        assert o.sim_A_pub.get() == "" and o.sim_Ka.get() == ""

    def test_mot_ben_sai_thi_ben_dung_cung_khong_duoc_gui(self, tao_sim, hop_thoai):
        o = tao_sim(a=6, b=22)
        o._sim_exchange_both()
        assert len(hop_thoai) == 1
        assert o._sim["A"] is None and o._sim["B"] is None
        assert o.sim_A_pub.get() == ""

    def test_khoa_cong_khai_bang_p_tru_1(self, tao_sim, hop_thoai):
        o = tao_sim(a=11)                                                # A = p-1
        o._sim_exchange_both()
        assert len(hop_thoai) == 1 and "ngoài" in hop_thoai[0][1]
        assert o._sim["A"] is None

    def test_khoa_khong_phai_so(self, tao_sim, hop_thoai):
        o = tao_sim(a="abc")
        o._sim_exchange_both()
        assert len(hop_thoai) == 1 and hop_thoai[0][0] == "showerror"
        o2 = tao_sim(b="")
        o2._sim_exchange_both()
        assert hop_thoai[-1][0] == "showerror" and o2._sim["A"] is None

    def test_pg_sai_thi_khong_gui(self, tao_sim, hop_thoai):
        o = tao_sim(p=24)
        o._sim_exchange_both()
        assert len(hop_thoai) == 1 and o._sim["A"] is None

    def test_gui_rieng_tung_ben_chua_co_khoa_chung(self, tao_sim, hop_thoai):
        o = tao_sim()
        o._sim_send_a()
        assert o.sim_A_pub.get() == "8" and o.sim_B_pub.get() == ""
        assert o.sim_Ka.get() == "" and o.sim_Kb.get() == ""
        assert o._sim["A"] == {"p": 23, "g": 5, "k": 6, "pub": 8} and o._sim["B"] is None
        assert hop_thoai == []

    def test_gui_lan_luot_a_roi_b(self, tao_sim, hop_thoai):
        o = tao_sim()
        o._sim_send_a()
        o._sim_send_b()
        assert o.sim_Ka.get() == o.sim_Kb.get() == "2"

    def test_gui_lan_luot_b_roi_a(self, tao_sim, hop_thoai):
        o = tao_sim()
        o._sim_send_b()
        assert o.sim_Ka.get() == ""
        o._sim_send_a()
        assert o.sim_Ka.get() == o.sim_Kb.get() == "2"

    def test_gui_khoa_sai_tung_ben(self, tao_sim, hop_thoai):
        o = tao_sim(a=22)
        o._sim_send_a()
        assert hop_thoai[-1][0] == "showwarning" and o._sim["A"] is None
        o2 = tao_sim(b=1)
        o2._sim_send_b()
        assert hop_thoai[-1][0] == "showwarning" and o2._sim["B"] is None
        o3 = tao_sim(a="x")
        o3._sim_send_a()
        assert hop_thoai[-1][0] == "showerror"

    def test_nho_khoa_rieng_da_gui_khong_lan_voi_o_nhap(self, tao_sim, hop_thoai):
        # gửi A với a = 6, sau đó sửa ô nhập a = 7 rồi mới gửi B: khoá chung vẫn tính theo a = 6 đã gửi
        o = tao_sim()
        o._sim_send_a()
        o.sim_a.set(7)
        o._sim_send_b()
        K = pow(pow(5, 15, 23), 6, 23)
        assert o.sim_Ka.get() == o.sim_Kb.get() == str(K)

    def test_doi_pg_giua_hai_lan_gui_xoa_ket_qua_cu(self, tao_sim, hop_thoai):
        o = tao_sim()
        o._sim_send_a()
        assert o._sim["A"]["p"] == 23
        o.sim_p.set(29)
        o.sim_g.set(2)
        o.sim_b.set(3)
        o._sim_send_b()
        assert o._sim["A"] is None and o._sim["B"]["p"] == 29
        assert o.sim_A_pub.get() == "" and o.sim_A_recv.get() == ""
        assert o.sim_Ka.get() == "" and o.sim_Kb.get() == ""
        assert "xóa kết quả cũ" in o.sim_log.t
        assert hop_thoai == []

    def test_trao_doi_lai_voi_pg_moi(self, tao_sim, hop_thoai):
        o = tao_sim()
        o._sim_exchange_both()
        o.sim_p.set(29)
        o.sim_g.set(2)
        o.sim_a.set(6)
        o.sim_b.set(15)
        o._sim_exchange_both()
        K = pow(pow(2, 15, 29), 6, 29)
        assert o.sim_Ka.get() == o.sim_Kb.get() == str(K)
        assert o._sim["A"]["p"] == o._sim["B"]["p"] == 29
        assert hop_thoai == []

    def test_canh_bao_khoa_chung_yeu(self, tao_sim, hop_thoai):
        # p = 5, g = 2: chỉ có khoá 3; khoá chung = 3^3 mod 5 = 2 nên không yếu, kiểm tra ca không cảnh báo
        o = tao_sim(p=5, g=2, a=3, b=3)
        o._sim_exchange_both()
        assert o.sim_Ka.get() == o.sim_Kb.get() == str(pow(pow(2, 3, 5), 3, 5))
        assert "Cảnh báo" not in o.sim_log.t

    def test_sim_state_dung_chung_mot_dict(self, tao_sim):
        o = tao_sim()
        assert o._sim_state() is o._sim

    def test_sim_state_tu_tao_neu_thieu(self):
        o = object.__new__(G.DiffieHellmanGUI)
        assert o._sim_state() == {"A": None, "B": None}


class TestSimDatLaiVaPreset:
    def test_reset_ve_mac_dinh(self, tao_sim, hop_thoai):
        o = tao_sim()
        o._sim_exchange_both()
        o.sim_p.set(29)
        o.sim_g.set(2)
        o.sim_a.set(9)
        o.sim_b.set(10)
        o._sim_reset()
        assert o._sim == {"A": None, "B": None}
        assert (o.sim_p.get(), o.sim_g.get(), o.sim_a.get(), o.sim_b.get()) == ("23", "5", "6", "15")
        assert o.sim_preset.get() == "(p = 23, g = 5)"
        for ten in ("sim_A_pub", "sim_B_pub", "sim_A_recv", "sim_B_recv", "sim_Ka", "sim_Kb"):
            assert getattr(o, ten).get() == "", ten
        assert "làm mới" in o.sim_log.t and "Hoàn tất" not in o.sim_log.t

    def test_reset_giu_pg(self, tao_sim, hop_thoai):
        o = tao_sim(p=29, g=2, a=9, b=10)
        o._sim_reset(keep_pg=True)
        assert (o.sim_p.get(), o.sim_g.get(), o.sim_a.get(), o.sim_b.get()) == ("29", "2", "9", "10")
        assert o._sim == {"A": None, "B": None}

    def test_chon_preset_dien_pg_va_khoa_hop_le(self, tao_sim, hop_thoai):
        o = tao_sim()
        o.sim_preset.set("(p = 29, g = 2)")
        o._sim_on_preset()
        assert (o.sim_p.get(), o.sim_g.get()) == ("29", "2")
        assert G.sim_kiem_tra_khoa(29, 2, int(o.sim_a.get()), "a")[1] is None
        assert G.sim_kiem_tra_khoa(29, 2, int(o.sim_b.get()), "b")[1] is None
        assert "p = 29" in o.sim_log.t

    @pytest.mark.parametrize("p,g", [(5, 2), (7, 3), (13, 2), (23, 5), (29, 2)])
    def test_moi_preset_trao_doi_duoc(self, p, g, tao_sim, hop_thoai):
        o = tao_sim()
        o.sim_preset.set(f"(p = {p}, g = {g})")
        o._sim_on_preset()
        o._sim_exchange_both()
        assert hop_thoai == []
        assert o.sim_Ka.get() == o.sim_Kb.get() != ""

    def test_chon_preset_xoa_ket_qua_cu(self, tao_sim, hop_thoai):
        o = tao_sim()
        o._sim_exchange_both()
        o.sim_preset.set("(p = 7, g = 3)")
        o._sim_on_preset()
        assert o._sim == {"A": None, "B": None} and o.sim_Ka.get() == ""

    def test_preset_rac_khong_lam_gi(self, tao_sim, hop_thoai):
        o = tao_sim()
        o.sim_preset.set("khong co so")
        o._sim_on_preset()
        assert (o.sim_p.get(), o.sim_g.get()) == ("23", "5")

    def test_dat_khoa_mac_dinh_p_nho(self, tao_sim):
        o = tao_sim(p=7, g=3, a=99, b=99)
        o._sim_dat_khoa_mac_dinh(7, 3)
        assert G.sim_kiem_tra_khoa(7, 3, int(o.sim_a.get()), "a")[1] is None
        assert G.sim_kiem_tra_khoa(7, 3, int(o.sim_b.get()), "b")[1] is None

    def test_doc_khoa(self, tao_sim, hop_thoai):
        o = tao_sim(a=" 12 ")
        assert o._sim_doc_khoa(o.sim_a, "a") == 12
        o.sim_a.set("abc")
        assert o._sim_doc_khoa(o.sim_a, "a") is None
        assert hop_thoai[-1][0] == "showerror"


# ---------------------------------------------------------------- 7. MÀN HÌNH, ẢNH, CHỌN TỆP
class TestManHinh:
    def test_clear_output(self, tao):
        o = tao()
        o.txt_out.t = "nội dung cũ"
        o.clear_output()
        assert o.txt_out.t == ""

    def test_hien_loi_truc_tiep(self, tao, hop_thoai):
        o = tao()
        o._hien_loi(["- loi mot", "- loi hai"])
        assert "KIỂM TRA THAM SỐ THẤT BẠI" in o.txt_out.t
        assert "loi mot" in o.txt_out.t and "loi hai" in o.txt_out.t
        assert o.notebook.da_chon == [0]
        assert hop_thoai[0][0] == "showwarning" and "loi mot" in hop_thoai[0][1] and "loi hai" in hop_thoai[0][1]

    def test_loi_chao_mung(self, tao):
        o = tao()
        o._write_welcome()
        assert "SẴN SÀNG THUYẾT TRÌNH" in o.txt_out.t and "CHẠY TỰ ĐỘNG TOÀN BỘ" in o.txt_out.t

    def test_ban_ro_mac_dinh_khi_trong(self, tao):
        assert tao(tin="   ")._ban_ro() == "Xin chao Thay Co! Demo Diffie-Hellman NEU."

    def test_ban_ro_cat_khoang_trang(self, tao):
        assert tao(tin="  xin chao  ")._ban_ro() == "xin chao"

    def test_muc_4_dung_tin_mac_dinh_khi_trong(self, tao):
        o = tao(tin="")
        goi = []
        o._run_async = lambda jobs, on_done=None: goi.append(jobs)
        o.run_muc_4()
        assert len(goi) == 1


class _AnhGia:
    """PhotoImage giả: có width() và subsample()."""

    def __init__(self, file=None, rong=1000):
        self.file, self.rong = file, rong

    def width(self):
        return self.rong

    def subsample(self, x, y):
        return _AnhGia(self.file, self.rong // x)


class TestHienThiAnh:
    def test_thieu_tep_bao_cho_nguoi_dung(self, tao, hop_thoai):
        tao().show_image(os.path.join("khong", "co.png"))
        assert hop_thoai[0][0] == "showinfo" and "Chưa có tệp" in hop_thoai[0][1]

    def test_hien_bieu_do_chi_khi_co_tep(self, tao, thu_muc_tam, hop_thoai):
        o = tao()
        o._hien_bieu_do()
        assert hop_thoai == []                              # chưa có docs/benchmark.png thì im lặng

    def test_hien_bieu_do_goi_show_image_khi_co_tep(self, tao, thu_muc_tam):
        os.makedirs("docs")
        with open(os.path.join("docs", "benchmark.png"), "wb") as f:
            f.write(b"x")
        o = tao()
        ghi = []
        o.show_image = ghi.append
        o._hien_bieu_do()
        assert ghi == [os.path.join("docs", "benchmark.png")]

    def test_show_image_thanh_cong_anh_rong_thu_nho(self, tao, thu_muc_tam, hop_thoai, monkeypatch):
        monkeypatch.setattr(G.tk, "PhotoImage", lambda file=None: _AnhGia(file, 1000))
        with open("a.png", "wb") as f:
            f.write(b"x")
        o = tao()
        o.show_image("a.png")
        assert hop_thoai == []
        assert o.notebook.da_chon == [1]
        assert o._img_ref.width() == 500                    # > 760 px thì thu nhỏ một nửa
        assert "Đang hiển thị" in o.lbl_img_status.text and "a.png" in o.lbl_img_status.text

    def test_show_image_anh_nho_giu_nguyen(self, tao, thu_muc_tam, hop_thoai, monkeypatch):
        monkeypatch.setattr(G.tk, "PhotoImage", lambda file=None: _AnhGia(file, 400))
        with open("b.png", "wb") as f:
            f.write(b"x")
        o = tao()
        o.show_image("b.png")
        assert o._img_ref.width() == 400

    def test_show_image_loi_doc_anh(self, tao, thu_muc_tam, hop_thoai, monkeypatch):
        def hong(file=None):
            raise RuntimeError("anh hong")
        monkeypatch.setattr(G.tk, "PhotoImage", hong)
        with open("c.png", "wb") as f:
            f.write(b"x")
        tao().show_image("c.png")
        assert hop_thoai[0][0] == "showerror" and "anh hong" in hop_thoai[0][1]


class TestChonTepTuyY:
    def test_chon_tep_chay_demo_file(self, tao, monkeypatch):
        monkeypatch.setattr(G.filedialog, "askopenfilename", lambda **k: "duong/dan/tep.txt", raising=False)
        ghi_demo = []
        monkeypatch.setattr(G, "demo_file", ghi_demo.append)
        o = tao()
        goi = []
        o._run_async = lambda jobs, on_done=None: goi.append(jobs)
        o.choose_custom_file()
        assert len(goi) == 1 and len(goi[0]) == 1
        goi[0][0]()                                          # chạy job thì gọi demo_file đúng đường dẫn
        assert ghi_demo == ["duong/dan/tep.txt"]

    def test_huy_chon_tep_khong_chay(self, tao, monkeypatch):
        monkeypatch.setattr(G.filedialog, "askopenfilename", lambda **k: "", raising=False)
        o = tao()
        o._run_async = lambda *a, **k: pytest.fail("không được chạy khi huỷ chọn tệp")
        o.choose_custom_file()

    def test_dang_ban_thi_khong_mo_hop_thoai_chon_tep(self, tao, monkeypatch):
        monkeypatch.setattr(G.filedialog, "askopenfilename",
                            lambda **k: pytest.fail("không được mở hộp thoại khi đang chạy"), raising=False)
        o = tao()
        o._busy = True
        o.choose_custom_file()


# ---------------------------------------------------------------- 8. QUY ƯỚC
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
