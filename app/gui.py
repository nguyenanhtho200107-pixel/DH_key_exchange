# File: app/gui.py
"""
Giao diện đồ họa (Tkinter) cho bài Demo Diffie-Hellman, Logarit rời rạc & MITM.

Cách chạy tại thư mục gốc của repo:
    python -m app.gui

Quy ước:
  - Mọi thuật toán và kiểm tra tham số dùng lại hàm của core/ (mod_exp, validate_pub,
    is_prime_miller_rabin, la_can_nguyen_thuy, canh_bao_tham_so...), không viết lại trong giao diện.
  - Các mục chạy lâu (Mục 3, 8, chạy tự động) chạy ở luồng nền để cửa sổ không bị đơ.
"""

import contextlib
import io
import os
import queue
import secrets
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Vẽ biểu đồ ra tệp PNG bằng backend không giao diện: tránh mở cửa sổ Tk thứ hai và
# tránh lỗi khi vẽ ở luồng nền (backend TkAgg chỉ an toàn ở luồng chính).
try:
    import matplotlib
    matplotlib.use("Agg")
except ImportError:
    pass

from core.dh import (
    mod_exp,
    sas_code,
    validate_dh_params,
    validate_pub,
    is_prime_miller_rabin,
    la_can_nguyen_thuy,
    canh_bao_tham_so,
    run_mitm_simulation,
    run_defense_simulation,
    RFC_3526_2048_P,
    RFC_3526_2048_G,
)
from core.stream import encrypt_text_hex, decrypt_text_hex
from core.dlog import dlog_bsgs, demo_eve_crack, demo_pohlig_hellman_compare
from app.filecrypt import ensure_sample_files, demo_file, benchmark_file_encryption
from app.benchmark import run_bsgs_benchmark
from app.cli import in_bang_mod_exp

# BSGS cần bảng ~sqrt(p) phần tử: chặn p quá lớn (10^12 ~ 40 bit) để không tràn bộ nhớ.
GIOI_HAN_P_BSGS = 10 ** 12
KHOA_TOI_THIEU = 2          # a, b, c phải nằm trong [2, p-2] (a = 1 làm A = g, a = p-1 làm A = 1)


def check_primitive_root(g: int, p: int):
    """Kiểm tra g có phải căn nguyên thủy mod p (dùng la_can_nguyen_thuy của core/dh.py).
    Trả về (True/False/None, thông báo)."""
    kq = la_can_nguyen_thuy(p, g)
    if kq is None:
        return None, "p quá lớn để phân tích thừa số (bỏ qua kiểm tra phần tử sinh)."
    if kq:
        return True, f"g = {g} là phần tử sinh nguyên thủy hợp lệ của Z_{p}*."
    return False, f"g = {g} KHÔNG phải phần tử sinh nguyên thủy của Z_{p}* (chỉ sinh nhóm con)."



def sim_kiem_tra_khoa(p: int, g: int, k: int, ten: str):
    """Kiểm tra khoá riêng k của tab mô phỏng. Trả về (khoá_công_khai, lỗi); lỗi là None nếu hợp lệ.
    Chặn cả khoá làm khoá công khai yếu (bằng p-1 hoặc ngoài [2, p-2])."""
    if not (KHOA_TOI_THIEU <= k <= p - 2):
        return None, f"Khóa {ten} = {k} phải nằm trong [{KHOA_TOI_THIEU}, {p - 2}]."
    y = mod_exp(g, k, p)
    if not validate_pub(y, p):
        return None, (f"Khóa {ten} = {k} cho khóa công khai {y} nằm ngoài [2, {p - 2}] "
                      f"(khóa chung chỉ còn ±1, ai cũng đoán được). Hãy chọn khóa khác.")
    return y, None


def sim_khoa_hop_le(p: int, g: int, mong_muon: int = None, tranh: int = None):
    """Khoá riêng hợp lệ để điền sẵn: ưu tiên giá trị mong muốn, nếu không được thì lấy khoá hợp lệ nhỏ nhất."""
    def ok(k):
        return KHOA_TOI_THIEU <= k <= p - 2 and validate_pub(mod_exp(g, k, p), p)
    if mong_muon is not None and mong_muon != tranh and ok(mong_muon):
        return mong_muon
    for k in range(KHOA_TOI_THIEU, p - 1):
        if k != tranh and ok(k):
            return k
    for k in range(KHOA_TOI_THIEU, p - 1):        # p rất nhỏ: chỉ có một khoá hợp lệ
        if ok(k):
            return k
    return None


def sim_cap_khoa_mac_dinh(p: int, g: int, a_mong: int = 6, b_mong: int = 15):
    """Cặp (a, b) điền sẵn: cả hai khoá công khai hợp lệ và khóa chung khác 1 và p-1 (nếu p đủ lớn để có)."""
    def ok(k):
        return KHOA_TOI_THIEU <= k <= p - 2 and validate_pub(mod_exp(g, k, p), p)
    a = sim_khoa_hop_le(p, g, a_mong)
    if a is None:
        return None, None
    A = mod_exp(g, a, p)
    ung_vien = [b_mong] + list(range(KHOA_TOI_THIEU, p - 1))
    for tranh_trung in (True, False):
        for b in ung_vien:
            if not ok(b) or (tranh_trung and b == a):
                continue
            if mod_exp(A, b, p) not in (1, p - 1):
                return a, b
    return a, sim_khoa_hop_le(p, g, b_mong, tranh=a)


def sim_khoa_ngau_nhien(p: int, g: int):
    """Khoá riêng ngẫu nhiên (secrets) trong [2, p-2] và cho khoá công khai hợp lệ."""
    for _ in range(200):
        k = KHOA_TOI_THIEU + secrets.randbelow(p - 3)
        if validate_pub(mod_exp(g, k, p), p):
            return k
    return sim_khoa_hop_le(p, g)


class DiffieHellmanGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hệ thống Demo Trao đổi khóa Diffie-Hellman, DLOG & MITM")
        self.geometry("1200x820")
        self.minsize(1040, 700)
        self.configure(bg="#0f172a")

        self._img_ref = None
        self._busy = False
        self._q = queue.Queue()
        self._on_done = None
        self._action_buttons = []      # các nút bị khóa khi đang chạy nền
        self._sim = {"A": None, "B": None}   # phiên trao đổi 2 bên: p, g, khóa riêng, khóa công khai đã gửi

        self._build_ui()
        self._write_welcome()

    # ------------------------------------------------------------------ DỰNG GIAO DIỆN
    def _build_ui(self):
        header = tk.Frame(self, bg="#1e293b", pady=10, padx=15)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="🔐 BẢNG ĐIỀU KHIỂN TRỰC QUAN: DIFFIE-HELLMAN, LOGARIT RỜI RẠC & MITM",
            font=("Segoe UI", 13, "bold"),
            fg="#38bdf8",
            bg="#1e293b",
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text="Đồng bộ core/dh.py (validate_pub + mod_exp + custom_sha256_bytes)",
            font=("Segoe UI", 9, "italic"),
            fg="#94a3b8",
            bg="#1e293b",
        ).pack(side=tk.RIGHT)

        main_frame = tk.Frame(self, bg="#0f172a", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ================= CỘT TRÁI: THAM SỐ & NÚT BẤM =================
        left_panel = tk.Frame(main_frame, bg="#1e293b", width=390, padx=12, pady=8)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)

        tk.Label(
            left_panel,
            text="1. THAM SỐ ĐẦU VÀO & KIỂM TRA HỢP LỆ",
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#1e293b",
        ).pack(anchor="w", pady=(0, 3))

        form = tk.Frame(left_panel, bg="#1e293b")
        form.pack(fill=tk.X, pady=(0, 3))

        self.var_p = tk.StringVar(value="23")
        self.var_g = tk.StringVar(value="5")
        self.var_a = tk.StringVar(value="6")
        self.var_b = tk.StringVar(value="15")
        self.var_c = tk.StringVar(value="3")
        self.var_msg = tk.StringVar(value="Xin chao Thay Co! Demo Diffie-Hellman NEU.")
        self.var_dlog_p = tk.StringVar(value="10007")
        self.var_dlog_g = tk.StringVar(value="5")
        self.var_dlog_A = tk.StringVar(value="6518")

        fields = [
            ("Số nguyên tố p:", self.var_p),
            ("Cơ số sinh g (1 < g < p):", self.var_g),
            ("Khóa riêng Alice (2 ≤ a ≤ p-2):", self.var_a),
            ("Khóa riêng Bob (2 ≤ b ≤ p-2):", self.var_b),
            ("Khóa Mallory (c, chỉ Mục 4-5):", self.var_c),
            ("Bản rõ (Tin nhắn):", self.var_msg),
        ]
        for row_idx, (label_text, var) in enumerate(fields):
            tk.Label(form, text=label_text, fg="#cbd5e1", bg="#1e293b", font=("Segoe UI", 9)).grid(
                row=row_idx, column=0, sticky="w", pady=1
            )
            tk.Entry(
                form, textvariable=var, bg="#0f172a", fg="#f8fafc", insertbackground="white",
                relief=tk.FLAT, font=("Consolas", 10), width=22
            ).grid(row=row_idx, column=1, sticky="ew", padx=(6, 0), pady=1)
        form.columnconfigure(1, weight=1)

        self.btn_check = tk.Button(
            left_panel,
            text="🔍 Kiểm Tra Tính Hợp Lệ Tham Số (p, g, a, b, c)",
            command=self.check_params_button,
            bg="#0369a1",
            fg="white",
            activebackground="#0284c7",
            activeforeground="white",
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            pady=3,
            cursor="hand2",
        )
        self.btn_check.pack(fill=tk.X, pady=(3, 5))
        self._action_buttons.append(self.btn_check)

        dlog_frame = tk.LabelFrame(
            left_panel, text="Tham số Mục 6: Tìm a từ (p, g, A)",
            fg="#94a3b8", bg="#1e293b", font=("Segoe UI", 8, "bold"), padx=6, pady=3
        )
        dlog_frame.pack(fill=tk.X, pady=(0, 5))
        for idx, (lbl, v) in enumerate([("p:", self.var_dlog_p), ("g:", self.var_dlog_g), ("A:", self.var_dlog_A)]):
            tk.Label(dlog_frame, text=lbl, fg="#cbd5e1", bg="#1e293b").grid(row=0, column=idx * 2, sticky="w")
            tk.Entry(dlog_frame, textvariable=v, width=8, bg="#0f172a", fg="#38bdf8", relief=tk.FLAT).grid(
                row=0, column=idx * 2 + 1, padx=(2, 8)
            )

        tk.Label(
            left_panel,
            text="2. CHỌN CHỨC NĂNG CHẠY DEMO (8 MỤC)",
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#1e293b",
        ).pack(anchor="w", pady=(2, 3))

        buttons = [
            ("1. DH Số Nhỏ (In từng bước & mã SAS)", self.run_muc_1, "#0284c7"),
            ("2. DH 2048-bit & Mã Hóa Tin Nhắn", self.run_muc_2, "#0284c7"),
            ("3. Mã Hóa Tệp Thật (.txt, .png) & Chọn File", self.run_muc_3, "#0d9488"),
            ("4. Tấn Công MITM (Mallory đọc & sửa tin)", self.run_muc_4, "#e11d48"),
            ("5. Phòng Chống MITM (SAS & Chữ ký RSA)", self.run_muc_5, "#16a34a"),
            ("6. Bẻ Khóa Tương Tác (Tìm a bằng BSGS)", self.run_muc_6, "#7c3aed"),
            ("7. Demo Eve 32-bit & Pohlig-Hellman", self.run_muc_7, "#7c3aed"),
            ("8. Chạy Benchmark & Vẽ Biểu Đồ Log", self.run_muc_8, "#d97706"),
            ("🚀 CHẠY TỰ ĐỘNG TOÀN BỘ (--auto)", self.run_all_auto, "#15803d"),
        ]
        for text, cmd, color in buttons:
            btn = tk.Button(
                left_panel,
                text=text,
                command=cmd,
                bg=color,
                fg="white",
                activebackground="#334155",
                activeforeground="white",
                relief=tk.FLAT,
                font=("Segoe UI", 9, "bold"),
                anchor="w",
                padx=10,
                pady=3,
                cursor="hand2",
            )
            btn.pack(fill=tk.X, pady=2)
            self._action_buttons.append(btn)

        bottom_btns = tk.Frame(left_panel, bg="#1e293b")
        bottom_btns.pack(fill=tk.X, pady=(5, 0))
        btn_file = tk.Button(
            bottom_btns, text="📂 Chọn File khác để Mã hóa", command=self.choose_custom_file,
            bg="#334155", fg="white", relief=tk.FLAT, font=("Segoe UI", 8, "bold"), pady=3
        )
        btn_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        self._action_buttons.append(btn_file)
        tk.Button(
            bottom_btns, text="🧹 Xóa Màn Hình", command=self.clear_output,
            bg="#475569", fg="white", relief=tk.FLAT, font=("Segoe UI", 8, "bold"), pady=3
        ).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        self.lbl_status = tk.Label(left_panel, text="", fg="#facc15", bg="#1e293b", font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(anchor="w", pady=(4, 0))

        # ================= CỘT PHẢI: MÀN HÌNH KẾT QUẢ & XEM ẢNH =================
        right_panel = tk.Frame(main_frame, bg="#1e293b")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        tab_log = tk.Frame(self.notebook, bg="#090d16")
        self.notebook.add(tab_log, text=" 💻 Màn hình Kết quả Chạy Trực tiếp ")

        scrollbar = tk.Scrollbar(tab_log)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.txt_out = tk.Text(
            tab_log,
            bg="#090d16",
            fg="#e2e8f0",
            font=("Consolas", 10),
            padx=14,
            pady=12,
            yscrollcommand=scrollbar.set,
            wrap=tk.WORD,
            relief=tk.FLAT,
        )
        self.txt_out.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.txt_out.yview)

        tab_img = tk.Frame(self.notebook, bg="#0f172a")
        self.notebook.add(tab_img, text=" 📊 Xem Biểu đồ Benchmark & Ảnh Mẫu ")

        img_bar = tk.Frame(tab_img, bg="#1e293b", pady=6, padx=10)
        img_bar.pack(fill=tk.X)
        tk.Button(
            img_bar, text="📈 Biểu đồ benchmark",
            command=lambda: self.show_image(os.path.join("docs", "benchmark.png")),
            bg="#0284c7", fg="white", relief=tk.FLAT, padx=10, pady=4, font=("Segoe UI", 9, "bold")
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            img_bar, text="🖼️ Ảnh gốc (anh_mau.png)",
            command=lambda: self.show_image(os.path.join("samples", "anh_mau.png")),
            bg="#0d9488", fg="white", relief=tk.FLAT, padx=10, pady=4, font=("Segoe UI", 9, "bold")
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            img_bar, text="✅ Ảnh khôi phục",
            command=lambda: self.show_image(os.path.join("samples", "anh_mau_khoi_phuc.png")),
            bg="#16a34a", fg="white", relief=tk.FLAT, padx=10, pady=4, font=("Segoe UI", 9, "bold")
        ).pack(side=tk.LEFT, padx=4)

        self.lbl_img_status = tk.Label(
            tab_img, text="Nhấn nút phía trên để xem biểu đồ hoặc ảnh sau khi chạy Mục 3 / Mục 8.",
            fg="#94a3b8", bg="#0f172a", font=("Segoe UI", 10)
        )
        self.lbl_img_status.pack(pady=8)

        self.lbl_img_canvas = tk.Label(tab_img, bg="#0f172a")
        self.lbl_img_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Tab 3: Mô phỏng Trao đổi 2 bên 
        tab_sim = tk.Frame(self.notebook, bg="#0b1120")
        self.notebook.add(tab_sim, text=" Mô phỏng Trao đổi 2 bên ")

        top_wrap = tk.Frame(tab_sim, bg="#0b1120", padx=12, pady=10)
        top_wrap.pack(fill=tk.X)
        top_wrap.columnconfigure(0, weight=1)
        top_wrap.columnconfigure(1, weight=1)
        top_wrap.columnconfigure(2, weight=1)

        # --- CỘT TRÁI: BÊN A (ALICE) ---
        card_a = tk.LabelFrame(top_wrap, text=" Bên A (Alice) ", fg="#38bdf8", bg="#131c31",
                               font=("Segoe UI", 11, "bold"), padx=12, pady=10)
        card_a.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        tk.Label(card_a, text="Khóa riêng (a):", fg="#cbd5e1", bg="#131c31", font=("Segoe UI", 9)).pack(anchor="w")
        row_a = tk.Frame(card_a, bg="#131c31")
        row_a.pack(fill=tk.X, pady=(2, 8))
        self.sim_a = tk.StringVar(value="6")
        tk.Entry(row_a, textvariable=self.sim_a, bg="#ffffff", fg="#0f172a", font=("Consolas", 10, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row_a, text="Ngẫu nhiên", command=lambda: self._sim_rand("A"), bg="#475569", fg="white",
                  relief=tk.FLAT, font=("Segoe UI", 8, "bold"), padx=8).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Label(card_a, text="Khóa công khai (A = g^a mod p):", fg="#cbd5e1", bg="#131c31", font=("Segoe UI", 9)).pack(anchor="w")
        self.sim_A_pub = tk.StringVar()
        tk.Entry(card_a, textvariable=self.sim_A_pub, state="readonly", readonlybackground="#e2e8f0",
                 fg="#0f172a", font=("Consolas", 10, "bold")).pack(fill=tk.X, pady=(2, 8))

        tk.Button(card_a, text="Gửi khóa A", command=self._sim_send_a, bg="#16a34a", fg="white",
                  relief=tk.FLAT, font=("Segoe UI", 9, "bold"), pady=5, cursor="hand2").pack(fill=tk.X, pady=(0, 8))

        tk.Label(card_a, text="Khóa Bob gửi nhận được (B):", fg="#cbd5e1", bg="#131c31", font=("Segoe UI", 9)).pack(anchor="w")
        self.sim_B_recv = tk.StringVar()
        tk.Entry(card_a, textvariable=self.sim_B_recv, state="readonly", readonlybackground="#e2e8f0",
                 fg="#0f172a", font=("Consolas", 10, "bold")).pack(fill=tk.X, pady=(2, 8))

        tk.Label(card_a, text="Khóa chung (K = B^a mod p):", fg="#38bdf8", bg="#131c31", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.sim_Ka = tk.StringVar()
        tk.Entry(card_a, textvariable=self.sim_Ka, state="readonly", readonlybackground="#dbeafe",
                 fg="#1e3a8a", font=("Consolas", 11, "bold")).pack(fill=tk.X, pady=(2, 0))

        # --- CỘT GIỮA: CHỌN THAM SỐ (p, g) ---
        card_mid = tk.LabelFrame(top_wrap, text=" Chọn cặp (p) và (g) công khai ", fg="#f8fafc", bg="#131c31",
                                 font=("Segoe UI", 10, "bold"), padx=12, pady=10)
        card_mid.grid(row=0, column=1, sticky="nsew", padx=4)

        tk.Label(card_mid, text="Chọn nhanh cặp có sẵn:", fg="#cbd5e1", bg="#131c31", font=("Segoe UI", 9)).pack(anchor="w")
        self.sim_preset = tk.StringVar(value="(p = 23, g = 5)")
        cb = ttk.Combobox(card_mid, textvariable=self.sim_preset, state="readonly", values=[
            "(p = 23, g = 5)", "(p = 5, g = 2)", "(p = 7, g = 3)", "(p = 13, g = 2)", "(p = 29, g = 2)"
        ])
        cb.pack(fill=tk.X, pady=(2, 8))
        cb.bind("<<ComboboxSelected>>", self._sim_on_preset)

        tk.Label(card_mid, text="Số nguyên tố p:", fg="#cbd5e1", bg="#131c31", font=("Segoe UI", 9)).pack(anchor="w")
        self.sim_p = tk.StringVar(value="23")
        tk.Entry(card_mid, textvariable=self.sim_p, bg="#ffffff", fg="#0f172a", font=("Consolas", 10, "bold")).pack(fill=tk.X, pady=(2, 6))

        tk.Label(card_mid, text="Cơ số sinh g:", fg="#cbd5e1", bg="#131c31", font=("Segoe UI", 9)).pack(anchor="w")
        self.sim_g = tk.StringVar(value="5")
        tk.Entry(card_mid, textvariable=self.sim_g, bg="#ffffff", fg="#0f172a", font=("Consolas", 10, "bold")).pack(fill=tk.X, pady=(2, 8))

        chk_row = tk.Frame(card_mid, bg="#131c31")
        chk_row.pack(fill=tk.X, pady=(0, 8))
        tk.Button(chk_row, text="Kiểm tra p", command=self._sim_check_p, bg="#0284c7", fg="white",
                  relief=tk.FLAT, font=("Segoe UI", 9, "bold"), pady=4).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Button(chk_row, text="Kiểm tra g", command=self._sim_check_g, bg="#d97706", fg="white",
                  relief=tk.FLAT, font=("Segoe UI", 9, "bold"), pady=4).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        tk.Button(card_mid, text="Tính & Trao đổi cả 2 bên", command=self._sim_exchange_both, bg="#2563eb", fg="white",
                  relief=tk.FLAT, font=("Segoe UI", 9, "bold"), pady=5).pack(fill=tk.X, pady=(0, 4))
        tk.Button(card_mid, text="Xóa & Làm lại", command=self._sim_reset, bg="#dc2626", fg="white",
                  relief=tk.FLAT, font=("Segoe UI", 8, "bold"), pady=3).pack(fill=tk.X)

        # --- CỘT PHẢI: BÊN B (BOB) ---
        card_b = tk.LabelFrame(top_wrap, text=" Bên B (Bob) ", fg="#4ade80", bg="#131c31",
                               font=("Segoe UI", 11, "bold"), padx=12, pady=10)
        card_b.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        tk.Label(card_b, text="Khóa riêng (b):", fg="#cbd5e1", bg="#131c31", font=("Segoe UI", 9)).pack(anchor="w")
        row_b = tk.Frame(card_b, bg="#131c31")
        row_b.pack(fill=tk.X, pady=(2, 8))
        self.sim_b = tk.StringVar(value="15")
        tk.Entry(row_b, textvariable=self.sim_b, bg="#ffffff", fg="#0f172a", font=("Consolas", 10, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row_b, text="Ngẫu nhiên", command=lambda: self._sim_rand("B"), bg="#475569", fg="white",
                  relief=tk.FLAT, font=("Segoe UI", 8, "bold"), padx=8).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Label(card_b, text="Khóa công khai (B = g^b mod p):", fg="#cbd5e1", bg="#131c31", font=("Segoe UI", 9)).pack(anchor="w")
        self.sim_B_pub = tk.StringVar()
        tk.Entry(card_b, textvariable=self.sim_B_pub, state="readonly", readonlybackground="#e2e8f0",
                 fg="#0f172a", font=("Consolas", 10, "bold")).pack(fill=tk.X, pady=(2, 8))

        tk.Button(card_b, text="Gửi khóa B", command=self._sim_send_b, bg="#16a34a", fg="white",
                  relief=tk.FLAT, font=("Segoe UI", 9, "bold"), pady=5, cursor="hand2").pack(fill=tk.X, pady=(0, 8))

        tk.Label(card_b, text="Khóa Alice gửi nhận được (A):", fg="#cbd5e1", bg="#131c31", font=("Segoe UI", 9)).pack(anchor="w")
        self.sim_A_recv = tk.StringVar()
        tk.Entry(card_b, textvariable=self.sim_A_recv, state="readonly", readonlybackground="#e2e8f0",
                 fg="#0f172a", font=("Consolas", 10, "bold")).pack(fill=tk.X, pady=(2, 8))

        tk.Label(card_b, text="Khóa chung (K = A^b mod p):", fg="#4ade80", bg="#131c31", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.sim_Kb = tk.StringVar()
        tk.Entry(card_b, textvariable=self.sim_Kb, state="readonly", readonlybackground="#dcfce7",
                 fg="#14532d", font=("Consolas", 11, "bold")).pack(fill=tk.X, pady=(2, 0))

        # --- KHUNG DƯỚI: NHẬT KÝ QUÁ TRÌNH ---
        log_box = tk.LabelFrame(tab_sim, text=" Quá trình trao đổi khóa ", fg="#f8fafc", bg="#0b1120",
                                font=("Segoe UI", 10, "bold"), padx=10, pady=6)
        log_box.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))
        self.sim_log = tk.Text(log_box, bg="#090d16", fg="#e2e8f0", font=("Consolas", 10), relief=tk.FLAT, height=9)
        self.sim_log.pack(fill=tk.BOTH, expand=True)
        self._sim_log_add("• Sẵn sàng! Chọn (p, g), nhập khóa riêng a, b rồi bấm [Gửi khóa A] và [Gửi khóa B].")

    def _sim_log_add(self, msg: str):
        self.sim_log.insert(tk.END, msg + "\n")
        self.sim_log.see(tk.END)

    def _sim_state(self):
        return self.__dict__.setdefault("_sim", {"A": None, "B": None})

    def _sim_get_pg(self):
        try:
            p, g = int(self.sim_p.get().strip()), int(self.sim_g.get().strip())
        except ValueError:
            messagebox.showerror("Lỗi tham số", "p và g bắt buộc phải là số nguyên!")
            return None
        if p < 5 or not is_prime_miller_rabin(p):
            messagebox.showwarning("Sai tham số p", f"p = {p} không phải số nguyên tố >= 5!")
            return None
        if g <= 1 or g >= p:
            messagebox.showwarning("Sai tham số g", f"g = {g} phải nằm trong khoảng (1, {p})!")
            return None
        ok_g, note_g = check_primitive_root(g, p)
        if ok_g is False:
            messagebox.showwarning("Sai tham số g", note_g)
            return None
        return p, g

    def _sim_doc_khoa(self, var, ten):
        try:
            return int(var.get().strip())
        except ValueError:
            messagebox.showerror("Lỗi", f"Khóa riêng {ten} phải là số nguyên!")
            return None

    def _sim_dat_khoa_mac_dinh(self, p, g):
        a, b = sim_cap_khoa_mac_dinh(p, g)
        if a is not None:
            self.sim_a.set(str(a))
        if b is not None:
            self.sim_b.set(str(b))

    def _sim_on_preset(self, _event=None):
        txt = self.sim_preset.get()
        nums = [int(s) for s in txt.replace("(", "").replace(")", "").replace(",", " ").split() if s.isdigit()]
        if len(nums) == 2:
            self.sim_p.set(str(nums[0]))
            self.sim_g.set(str(nums[1]))
            self._sim_reset(keep_pg=True)
            self._sim_dat_khoa_mac_dinh(nums[0], nums[1])        # khóa cũ có thể không hợp lệ với p mới
            self._sim_log_add(f"• Đã chọn cặp số công khai: p = {nums[0]}, g = {nums[1]}")

    def _sim_check_p(self):
        try:
            p = int(self.sim_p.get().strip())
        except ValueError:
            messagebox.showerror("Lỗi", "p phải là số nguyên!")
            return
        if p >= 5 and is_prime_miller_rabin(p):
            self._sim_log_add(f"• [Kiểm tra p] p = {p} là SỐ NGUYÊN TỐ hợp lệ.")
            messagebox.showinfo("Hợp lệ", f"p = {p} là số nguyên tố hợp lệ!")
        else:
            self._sim_log_add(f"• [Lỗi] p = {p} KHÔNG phải số nguyên tố >= 5.")
            messagebox.showwarning("Không hợp lệ", f"p = {p} không phải số nguyên tố >= 5!")

    def _sim_check_g(self):
        pg = self._sim_get_pg()
        if pg:
            p, g = pg
            _, note_g = check_primitive_root(g, p)
            self._sim_log_add(f"• [Kiểm tra g] {note_g}")
            messagebox.showinfo("Hợp lệ", note_g)

    def _sim_rand(self, side: str):
        pg = self._sim_get_pg()
        if not pg:
            return
        p, g = pg
        val = sim_khoa_ngau_nhien(p, g)
        if val is None:
            return
        (self.sim_a if side == "A" else self.sim_b).set(str(val))

    def _sim_xoa_ben(self, ben: str):
        """Xoá kết quả của một bên (khi p, g đã đổi nên kết quả cũ không còn dùng được)."""
        self._sim_state()[ben] = None
        (self.sim_A_pub if ben == "A" else self.sim_B_pub).set("")
        (self.sim_A_recv if ben == "A" else self.sim_B_recv).set("")
        self.sim_Ka.set("")
        self.sim_Kb.set("")

    def _sim_ap_dung(self, ben: str, p: int, g: int, k: int, pub: int):
        """Ghi nhận bên `ben` đã gửi khoá công khai. Nhớ p, g, khoá riêng đã dùng để về sau không lẫn với ô nhập."""
        kia = "B" if ben == "A" else "A"
        st = self._sim_state()
        if st[kia] and (st[kia]["p"], st[kia]["g"]) != (p, g):
            self._sim_xoa_ben(kia)
            self._sim_log_add(f"• p, g đã đổi so với lần gửi trước của Bên {kia}: xóa kết quả cũ của Bên {kia}, hãy gửi lại.")
        st[ben] = {"p": p, "g": g, "k": k, "pub": pub}
        (self.sim_A_pub if ben == "A" else self.sim_B_pub).set(str(pub))
        (self.sim_A_recv if ben == "A" else self.sim_B_recv).set(str(pub))
        self.sim_Ka.set("")
        self.sim_Kb.set("")
        self._sim_log_add(f"• Bên {ben} tính {ben} = {g}^{k} mod {p} = {pub} và gửi {ben} = {pub} cho Bên {kia}.")
        self._sim_try_shared()

    def _sim_try_shared(self):
        st = self._sim_state()
        A, B = st["A"], st["B"]
        if not (A and B):
            return
        p = A["p"]
        Ka = mod_exp(B["pub"], A["k"], p)
        Kb = mod_exp(A["pub"], B["k"], p)
        self.sim_Ka.set(str(Ka))
        self.sim_Kb.set(str(Kb))
        self._sim_log_add(f"• [Hoàn tất] Alice tính K = {B['pub']}^{A['k']} mod {p} = {Ka} | "
                          f"Bob tính K = {A['pub']}^{B['k']} mod {p} = {Kb}")
        if Ka == Kb:
            self._sim_log_add(f"• => Khóa chung K của hai bên đều bằng {Ka} (SAS: [{sas_code(A['pub'], B['pub'], Ka)}])")
            if Ka in (1, p - 1):
                self._sim_log_add(f"• [Cảnh báo] K = {Ka} (±1 mod {p}): p quá nhỏ nên khóa chung rất yếu, chỉ dùng để minh họa.")
        else:
            self._sim_log_add("• [LỖI] Hai khóa chung KHÔNG khớp nhau! Hãy bấm [Xóa & Làm lại] rồi thử lại.")

    def _sim_send_a(self):
        pg = self._sim_get_pg()
        if not pg:
            return
        p, g = pg
        a = self._sim_doc_khoa(self.sim_a, "a")
        if a is None:
            return
        pub, loi = sim_kiem_tra_khoa(p, g, a, "a (Bên A)")
        if loi:
            messagebox.showwarning("Sai khóa a", loi)
            return
        self._sim_ap_dung("A", p, g, a, pub)

    def _sim_send_b(self):
        pg = self._sim_get_pg()
        if not pg:
            return
        p, g = pg
        b = self._sim_doc_khoa(self.sim_b, "b")
        if b is None:
            return
        pub, loi = sim_kiem_tra_khoa(p, g, b, "b (Bên B)")
        if loi:
            messagebox.showwarning("Sai khóa b", loi)
            return
        self._sim_ap_dung("B", p, g, b, pub)

    def _sim_exchange_both(self):
        """Kiểm tra cả hai bên trước, chỉ gửi khi cả hai đều hợp lệ (một hộp thoại duy nhất nếu có lỗi)."""
        pg = self._sim_get_pg()
        if not pg:
            return
        p, g = pg
        a = self._sim_doc_khoa(self.sim_a, "a")
        if a is None:
            return
        b = self._sim_doc_khoa(self.sim_b, "b")
        if b is None:
            return
        pub_a, loi_a = sim_kiem_tra_khoa(p, g, a, "a (Bên A)")
        pub_b, loi_b = sim_kiem_tra_khoa(p, g, b, "b (Bên B)")
        loi = [x for x in (loi_a, loi_b) if x]
        if loi:
            messagebox.showwarning("Sai khóa riêng", "\n".join("- " + x for x in loi))
            return
        self._sim_ap_dung("A", p, g, a, pub_a)
        self._sim_ap_dung("B", p, g, b, pub_b)

    def _sim_reset(self, keep_pg: bool = False):
        self._sim_state().update({"A": None, "B": None})
        if not keep_pg:
            self.sim_preset.set("(p = 23, g = 5)")
            self.sim_p.set("23")
            self.sim_g.set("5")
            self.sim_a.set("6")
            self.sim_b.set("15")
        for v in (self.sim_A_pub, self.sim_B_pub, self.sim_A_recv, self.sim_B_recv, self.sim_Ka, self.sim_Kb):
            v.set("")
        self.sim_log.delete("1.0", tk.END)
        self._sim_log_add("• Đã làm mới phiên trao đổi khóa.")

    def _write_welcome(self):
        self.txt_out.insert(
            tk.END,
            "========================================================================\n"
            "  SẴN SÀNG THUYẾT TRÌNH! HƯỚNG DẪN SỬ DỤNG NHANH:\n"
            "  - Bấm [🔍 Kiểm Tra Tính Hợp Lệ Tham Số] để kiểm tra p, g, a, b, c.\n"
            "  - Bấm từng nút (1 -> 8) ở cột bên trái để chạy từng phần demo.\n"
            "  - Hoặc bấm nút màu xanh lá [🚀 CHẠY TỰ ĐỘNG TOÀN BỘ (--auto)].\n"
            "  - Mục chạy lâu (3, 8, tự động) chạy nền: các nút bị khóa đến khi xong.\n"
            "========================================================================\n"
        )

    def clear_output(self):
        self.txt_out.delete("1.0", tk.END)

    # ------------------------------------------------------------------ KIỂM TRA THAM SỐ
    def _hien_loi(self, errors):
        detail = "\n".join(errors)
        self.notebook.select(0)
        self.txt_out.insert(tk.END, f"\n[❌ KIỂM TRA THAM SỐ THẤT BẠI]\n{detail}\n")
        self.txt_out.see(tk.END)
        messagebox.showwarning("Tham số không hợp lệ", f"Phát hiện lỗi tham số đầu vào:\n\n{detail}")

    def _doc_so_nguyen(self, cac_o, tieu_de="Lỗi định dạng tham số"):
        """Đọc các ô nhập (danh sách (tên, StringVar)); trả về danh sách số nguyên hoặc None nếu có ô sai."""
        ket_qua = []
        for ten, var in cac_o:
            try:
                ket_qua.append(int(var.get().strip()))
            except ValueError:
                messagebox.showerror(tieu_de, f"Ô '{ten}' bắt buộc phải là SỐ NGUYÊN (không để trống, không nhập chữ)!")
                return None
        return ket_qua

    def _validate_all_inputs(self, need_c: bool = True):
        """
        Kiểm tra p, g, a, b (và c nếu need_c) cho các mục dùng số nhỏ (1, 4, 5).
        Dùng lại hàm của core/dh.py. Trả về (p, g, a, b, c, note_g) nếu hợp lệ, ngược lại None
        (đã hiện lỗi cho người dùng).
        """
        cac_o = [("p", self.var_p), ("g", self.var_g), ("a", self.var_a), ("b", self.var_b)]
        if need_c:
            cac_o.append(("c", self.var_c))
        so = self._doc_so_nguyen(cac_o)
        if so is None:
            return None
        p, g, a, b = so[:4]
        c = so[4] if need_c else None

        errors = []
        note_g = ""
        p_hop_le = False

        if p < 5:
            errors.append(f"- Số p = {p} quá nhỏ (yêu cầu số nguyên tố p >= 5).")
        elif not is_prime_miller_rabin(p):
            errors.append(f"- p = {p} KHÔNG PHẢI SỐ NGUYÊN TỐ! Diffie-Hellman yêu cầu p nguyên tố.")
        else:
            p_hop_le = True

        if g <= 1 or g >= p:
            errors.append(f"- Cơ số g = {g} không hợp lệ (bắt buộc 1 < g < p = {p}).")
        elif p_hop_le:
            is_prim, note_g = check_primitive_root(g, p)
            if is_prim is False:
                errors.append(f"- {note_g}")

        if p_hop_le:
            gioi_han = p - 2
            khoa = [("Khóa Alice (a)", a), ("Khóa Bob (b)", b)] + ([("Khóa Mallory (c)", c)] if need_c else [])
            for ten, val in khoa:
                if not (KHOA_TOI_THIEU <= val <= gioi_han):
                    errors.append(
                        f"- {ten} = {val} không hợp lệ (yêu cầu {KHOA_TOI_THIEU} <= khóa <= p - 2 = {gioi_han}; "
                        f"khóa 0, 1 hoặc p-1 cho khóa công khai/khóa chung yếu)."
                    )

        if not errors:
            with contextlib.redirect_stdout(io.StringIO()):          # validate_dh_params tự in lỗi
                ok = validate_dh_params(p, g)
            if not ok:
                errors.append("- core/dh.py (validate_dh_params) từ chối bộ (p, g).")
            else:
                # khóa công khai A, B phải hợp lệ (a = (p-1)/2 làm A = p-1, khóa chung chỉ còn ±1)
                for ten, y in (("A", mod_exp(g, a, p)), ("B", mod_exp(g, b, p))):
                    if not validate_pub(y, p):
                        errors.append(f"- Khóa công khai {ten} = {y} không hợp lệ (ngoài [2, p-2]); hãy chọn lại a, b hoặc g.")

        if errors:
            self._hien_loi(errors)
            return None
        return p, g, a, b, c, note_g

    def _validate_2048(self):
        """Kiểm tra a, b cho Mục 2 (nhóm RFC 3526). Trả về (a, b) hoặc None."""
        so = self._doc_so_nguyen([("a", self.var_a), ("b", self.var_b)])
        if so is None:
            return None
        a, b = so
        P, G = RFC_3526_2048_P, RFC_3526_2048_G
        q = (P - 1) // 2
        errors = []
        for ten, val in (("Khóa Alice (a)", a), ("Khóa Bob (b)", b)):
            if not (KHOA_TOI_THIEU <= val <= P - 2):
                errors.append(f"- {ten} = {val} phải nằm trong [{KHOA_TOI_THIEU}, p - 2] của nhóm RFC 3526.")
        if not errors:
            for ten, val in (("A", mod_exp(G, a, P)), ("B", mod_exp(G, b, P))):
                if not validate_pub(val, P, q):
                    errors.append(f"- Khóa công khai {ten} không hợp lệ (ngoài [2, p-2] hoặc không thuộc nhóm con bậc q).")
        if errors:
            self._hien_loi(errors)
            return None
        return a, b

    def check_params_button(self):
        """Sự kiện khi bấm nút Kiểm tra tham số trực tiếp trên giao diện."""
        if self._busy:
            return
        res = self._validate_all_inputs(need_c=True)
        if not res:
            return
        p, g, a, b, c, note_g = res
        with contextlib.redirect_stdout(io.StringIO()):
            canh_bao = canh_bao_tham_so(p, g)
        self.notebook.select(0)
        gh = f"[{KHOA_TOI_THIEU}, {p - 2}]"
        report = (
            "\n" + "=" * 68 + "\n"
            " 🔍 KẾT QUẢ KIỂM TRA TÍNH HỢP LỆ THAM SỐ DIFFIE-HELLMAN\n"
            + "=" * 68 + "\n"
            f"  [OK] Số nguyên tố p        : {p} (Đạt chuẩn Miller-Rabin, {p.bit_length()} bits)\n"
            f"  [OK] Cơ số sinh g          : {g} ({note_g})\n"
            f"  [OK] Khóa riêng Alice (a)  : {a} (Nằm trong khoảng {gh})\n"
            f"  [OK] Khóa riêng Bob (b)    : {b} (Nằm trong khoảng {gh})\n"
            f"  [OK] Khóa Mallory (c)      : {c} (Nằm trong khoảng {gh})\n"
            f"  [OK] Khóa công khai A, B   : hợp lệ (validate_pub)\n"
        )
        for s in canh_bao:
            report += f"  [!]  Cảnh báo (không chặn): {s}\n"
        report += "  => KẾT LUẬN: Toàn bộ tham số HỢP LỆ, sẵn sàng chạy!\n"
        self.txt_out.insert(tk.END, report)
        self.txt_out.see(tk.END)
        messagebox.showinfo("Tham số hợp lệ", f"Toàn bộ tham số (p={p}, g={g}, a={a}, b={b}, c={c}) đều hợp lệ!")

    # ------------------------------------------------------------------ CHẠY NỀN
    def _set_busy(self, busy: bool):
        self._busy = busy
        trang_thai = tk.DISABLED if busy else tk.NORMAL
        for btn in self._action_buttons:
            btn.config(state=trang_thai)
        self.lbl_status.config(text="⏳ Đang chạy... (vui lòng chờ)" if busy else "")

    def _run_async(self, jobs, on_done=None):
        """Chạy lần lượt các job (hàm không tham số) ở luồng nền, in kết quả từng job khi nó xong.
        Luồng nền chỉ tính toán và print; mọi thao tác với giao diện làm ở luồng chính."""
        if self._busy:
            messagebox.showinfo("Đang chạy", "Chương trình đang chạy một mục khác, hãy chờ xong rồi bấm tiếp.")
            return
        self.notebook.select(0)
        self._set_busy(True)
        self._on_done = on_done
        threading.Thread(target=self._worker, args=(list(jobs),), daemon=True).start()
        self.after(100, self._poll)

    def _worker(self, jobs):
        for job in jobs:
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    job()
                self._q.put(("out", buf.getvalue()))
            except Exception as exc:                      # lỗi được bắt, không làm sập giao diện
                self._q.put(("err", buf.getvalue(), str(exc)))
                break
        self._q.put(("done",))

    def _drain_queue(self):
        """Lấy kết quả từ luồng nền đưa lên màn hình. Trả về True khi đã chạy xong hết."""
        while True:
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                return False
            if item[0] == "out":
                self.txt_out.insert(tk.END, item[1] + "\n")
                self.txt_out.see(tk.END)
            elif item[0] == "err":
                self.txt_out.insert(tk.END, item[1] + f"\n[⚠️ LỖI THỰC THI ĐÃ ĐƯỢC BẮT AN TOÀN]: {item[2]}\n")
                self.txt_out.see(tk.END)
                messagebox.showerror("Thông báo lỗi", f"Có lỗi xảy ra khi xử lý:\n{item[2]}")
            elif item[0] == "done":
                self._set_busy(False)
                cb, self._on_done = self._on_done, None
                if cb:
                    cb()
                return True

    def _poll(self):
        if not self._drain_queue():
            self.after(100, self._poll)

    # ------------------------------------------------------------------ CÁC JOB (chạy ở luồng nền)
    @staticmethod
    def _job_muc_1(p, g, a, b, note_g):
        def job():
            print("\n" + "=" * 68)
            print(f" MỤC 1: TRAO ĐỔI KHÓA DH SỐ NHỎ (p={p}, g={g}, a={a}, b={b})")
            print("=" * 68)
            print(f"  [Kiểm tra tham số] p={p} nguyên tố | {note_g}")
            A = in_bang_mod_exp(g, a, p, ten_bien="A (Khóa công khai Alice)")
            B = in_bang_mod_exp(g, b, p, ten_bien="B (Khóa công khai Bob)")
            K_alice = in_bang_mod_exp(B, a, p, ten_bien="K_Alice = B^a mod p")
            K_bob = in_bang_mod_exp(A, b, p, ten_bien="K_Bob   = A^b mod p")
            print(f"\n  => KẾT QUẢ: Khóa chung hai bên {'khớp nhau' if K_alice == K_bob else 'KHÔNG khớp'} "
                  f"(K_Alice = {K_alice}, K_Bob = {K_bob})")
            print(f"  => Mã xác thực SAS (custom_sha256_bytes): [{sas_code(A, B, K_alice)}]")
        return job

    @staticmethod
    def _job_muc_2(a, b, ban_ro):
        def job():
            print("\n" + "=" * 68)
            print(" MỤC 2: DH SỐ LỚN (2048-BIT RFC 3526) & MÃ HÓA TIN NHẮN")
            print("=" * 68)
            P, G = RFC_3526_2048_P, RFC_3526_2048_G
            A = mod_exp(G, a, P)
            B = mod_exp(G, b, P)
            K_alice = mod_exp(B, a, P)
            K_bob = mod_exp(A, b, P)

            ban_ma_hex = encrypt_text_hex(ban_ro, K_alice)
            ban_giai_ma = decrypt_text_hex(ban_ma_hex, K_bob)

            print(f"  * Tham số p           : Chuẩn RFC 3526 Group 14 ({P.bit_length()} bits)")
            print(f"  * Khóa chung (rút gọn): {hex(K_alice)[:24]}...")
            print(f"  * Mã xác thực SAS     : [{sas_code(A, B, K_alice)}]")
            print(f"  * Bản rõ ban đầu      : {ban_ro}")
            print(f"  * Bản mã (Hex)        : {ban_ma_hex}")
            print(f"  * Giải mã ngược lại   : {ban_giai_ma}")
            print(f"  => Đối chiếu bản rõ   : {'KHÔI PHỤC ĐÚNG 100%' if ban_ro == ban_giai_ma else 'SAI LỆCH'}")
        return job

    @staticmethod
    def _job_muc_3():
        def job():
            print("\n" + "=" * 68)
            print(" MỤC 3: DEMO TRÊN DỮ LIỆU THẬT (TỆP VĂN BẢN .TXT & ẢNH .PNG)")
            print("=" * 68)
            txt_path, png_path = ensure_sample_files()
            demo_file(txt_path)
            demo_file(png_path)
            benchmark_file_encryption()
        return job

    @staticmethod
    def _job_muc_4(p, g, a, b, c, tin_alice):
        def job():
            K_alice, K_bob, K_mal_alice, K_mal_bob = run_mitm_simulation(p, g, a, b, c)
            print("\n  [Minh họa Mallory chặn đọc và sửa nội dung tin nhắn trên đường truyền]")
            cipher_from_alice = encrypt_text_hex(tin_alice, K_alice)
            mallory_read = decrypt_text_hex(cipher_from_alice, K_mal_alice)

            tin_gia_mao = "Chuyen 99,000,000 VND cho tai khoan MALLORY"
            cipher_to_bob = encrypt_text_hex(tin_gia_mao, K_mal_bob)
            bob_read = decrypt_text_hex(cipher_to_bob, K_bob)

            print(f"  * Alice gửi đi          : '{tin_alice}' (Mã hóa bằng K_Alice = {K_alice})")
            print(f"  * Mallory chặn & đọc lén: '{mallory_read}'")
            print(f"  * Mallory sửa nội dung  : '{tin_gia_mao}' (Mã hóa lại bằng K_Mal_Bob = {K_mal_bob})")
            print(f"  * Bob giải mã nhận được : '{bob_read}' (Bob hoàn toàn không biết bị nghe lén!)")
        return job

    @staticmethod
    def _job_muc_5(p, g, a, b, c):
        return lambda: run_defense_simulation(p, g, a, b, c)

    @staticmethod
    def _job_muc_6(p, g, A):
        def job():
            print("\n" + "=" * 68)
            print(f" MỤC 6: GIẢI LOGARIT RỜI RẠC BSGS TƯƠNG TÁC (p={p}, g={g}, A={A})")
            print("=" * 68)
            a_found = dlog_bsgs(g, A, p)
            if a_found is not None:
                print(f"  => Tìm thấy khóa riêng a = {a_found}")
                print(f"  => Kiểm tra lại bằng mod_exp: {g}^{a_found} mod {p} = {mod_exp(g, a_found, p)}")
            else:
                print("  => Không tồn tại số mũ a thỏa mãn bộ tham số trên.")
        return job

    @staticmethod
    def _job_muc_7():
        def job():
            demo_eve_crack()
            demo_pohlig_hellman_compare()
        return job

    @staticmethod
    def _job_muc_8():
        return lambda: run_bsgs_benchmark(repeats=2)

    # ------------------------------------------------------------------ CÁC NÚT MỤC
    def _ban_ro(self):
        return self.var_msg.get().strip() or "Xin chao Thay Co! Demo Diffie-Hellman NEU."

    def run_muc_1(self):
        params = self._validate_all_inputs(need_c=False)
        if not params:
            return
        p, g, a, b, _, note_g = params
        self._run_async([self._job_muc_1(p, g, a, b, note_g)])

    def run_muc_2(self):
        ab = self._validate_2048()
        if not ab:
            return
        self._run_async([self._job_muc_2(ab[0], ab[1], self._ban_ro())])

    def run_muc_3(self):
        self._run_async([self._job_muc_3()])

    def choose_custom_file(self):
        if self._busy:
            return
        filepath = filedialog.askopenfilename(
            title="Chọn tệp văn bản hoặc ảnh bất kỳ để mã hóa & giải mã bằng khóa DH",
            filetypes=[("Tất cả tệp", "*.*"), ("Văn bản", "*.txt"), ("Hình ảnh PNG", "*.png")]
        )
        if filepath:
            self._run_async([lambda: demo_file(filepath)])

    def run_muc_4(self):
        params = self._validate_all_inputs(need_c=True)
        if not params:
            return
        p, g, a, b, c, _ = params
        tin = self.var_msg.get().strip() or "Chuyen 5,000,000 VND cho Bob"
        self._run_async([self._job_muc_4(p, g, a, b, c, tin)])

    def run_muc_5(self):
        params = self._validate_all_inputs(need_c=True)
        if not params:
            return
        p, g, a, b, c, _ = params
        self._run_async([self._job_muc_5(p, g, a, b, c)])

    def run_muc_6(self):
        so = self._doc_so_nguyen(
            [("p (Mục 6)", self.var_dlog_p), ("g (Mục 6)", self.var_dlog_g), ("A (Mục 6)", self.var_dlog_A)],
            tieu_de="Lỗi đầu vào Mục 6",
        )
        if so is None:
            return
        p, g, A = so
        errors = []
        if p < 5 or not is_prime_miller_rabin(p):
            errors.append(f"- p = {p} phải là số nguyên tố >= 5.")
        elif p > GIOI_HAN_P_BSGS:
            errors.append(f"- p = {p} quá lớn cho BSGS (tối đa {GIOI_HAN_P_BSGS}, vì bảng cần ~sqrt(p) phần tử bộ nhớ).")
        elif g <= 1 or g >= p:
            errors.append(f"- Yêu cầu 1 < g < {p}.")
        elif A < 1 or A >= p:
            errors.append(f"- Yêu cầu 1 <= A < {p}.")
        if errors:
            self._hien_loi(errors)
            return
        self._run_async([self._job_muc_6(p, g, A)])

    def run_muc_7(self):
        self._run_async([self._job_muc_7()])

    def run_muc_8(self):
        self._run_async([self._job_muc_8()], on_done=self._hien_bieu_do)

    def _hien_bieu_do(self):
        png_path = os.path.join("docs", "benchmark.png")
        if os.path.exists(png_path):
            self.show_image(png_path)

    def run_all_auto(self):
        """Kiểm tra tham số MỘT lần; sai thì dừng ngay (một hộp thoại), đúng thì chạy nền tuần tự các mục."""
        params = self._validate_all_inputs(need_c=True)
        if not params:
            return
        ab = self._validate_2048()
        if not ab:
            return
        p, g, a, b, c, note_g = params
        self.clear_output()
        jobs = [
            self._job_muc_1(p, g, a, b, note_g),
            self._job_muc_2(ab[0], ab[1], self._ban_ro()),
            self._job_muc_3(),
            self._job_muc_4(p, g, a, b, c, self.var_msg.get().strip() or "Chuyen 5,000,000 VND cho Bob"),
            self._job_muc_5(p, g, a, b, c),
            self._job_muc_7(),
            self._job_muc_8(),
        ]
        self._run_async(jobs, on_done=self._hien_bieu_do)

    # ------------------------------------------------------------------ XEM ẢNH
    def show_image(self, filepath: str):
        if not os.path.exists(filepath):
            messagebox.showinfo("Thông báo", f"Chưa có tệp '{filepath}'. Hãy bấm chạy Mục 3 hoặc Mục 8 trước!")
            return
        try:
            self.notebook.select(1)
            img = tk.PhotoImage(file=filepath)
            if img.width() > 760:
                img = img.subsample(2, 2)
            self._img_ref = img
            self.lbl_img_canvas.config(image=self._img_ref)
            self.lbl_img_status.config(text=f"Đang hiển thị tệp: {filepath}", fg="#38bdf8")
        except Exception as e:
            messagebox.showerror("Lỗi hiển thị ảnh", f"Không thể mở ảnh: {e}")


if __name__ == "__main__":
    app = DiffieHellmanGUI()
    app.mainloop()
