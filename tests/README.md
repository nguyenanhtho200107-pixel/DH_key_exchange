# Kiểm thử

Chạy từ thư mục gốc của repo:

```bash
pip install -r tests/requirements.txt     # pytest, sympy, mpmath, matplotlib (chỉ dùng trong tests/ để đối chiếu)
python -m pytest tests -q                 # toàn bộ test (khoảng 40 giây)
python -m pytest tests -q -m "not cham"   # bỏ các test chạy lâu (khoảng 15 giây)
python tests/run_report.py                # báo cáo kiểm thử DH, ghi docs/test_log.txt
```

| File | Kiểm thử | Phần mã |
|---|---|---|
| `test_dh.py`, `run_report.py` | thuật toán DH, SHA-256, Miller-Rabin, RFC 3526, MITM, SAS, RSA, nhập liệu | `core/dh.py` (Lead) |
| `test_stream.py` | mã dòng SHA-256: luồng khoá, nonce, tiếng Việt, khoá sai | `core/stream.py` (Dev) |
| `test_dlog.py` | vét cạn, BSGS, CRT, Pohlig-Hellman, hai demo | `core/dlog.py` (Dev) |
| `test_cli.py` | nhập liệu an toàn, kiểm tra tham số, Mục 1-6, menu, `--auto` | `app/cli.py` (CLI) |
| `test_filecrypt.py` | tệp mẫu, mã hoá và giải mã tệp, bảng đo | `app/filecrypt.py` (CLI) |
| `test_benchmark.py` | đo BSGS, CSV, biểu đồ, ngoại suy 2048-bit | `app/benchmark.py` (CLI) |
| `test_gui.py` | kiểm tra tham số, luồng nền, các job (không mở cửa sổ thật) | `app/gui.py` (CLI) |
| `conftest.py` | hạt giống cố định, thư mục tạm, đăng ký dấu `cham` | dùng chung |

Test đối chiếu độc lập bằng `hashlib`, `sympy`, `mpmath` và `pow()`; các thư viện này chỉ có trong `tests/`.
Các test của `gui.py` không cần màn hình; nếu máy không có `tkinter` thì dùng bản giả tối thiểu.
