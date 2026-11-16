# Trao đổi khoá Diffie–Hellman

Bài tập lớn An toàn bảo mật thông tin: cài đặt trao đổi khoá Diffie–Hellman bằng Python thuần
(không dùng `hashlib`), kèm bài toán logarit rời rạc (BSGS, Pohlig–Hellman), tấn công người đứng giữa
(MITM) và cách phòng chống (mã SAS, chữ ký số).

## Phân công

| Vai | Phần phụ trách |
|---|---|
| **Lead** | `core/dh.py` (thuật toán DH, SHA-256 tự viết, kiểm tra tham số, RFC 3526, MITM, SAS, RSA đồ chơi), `core/__init__.py`, `README.md`, `.gitignore`, `.github/CODEOWNERS`; quản lý repo, review và merge PR |
| **Dev** | `core/stream.py` (mã dòng), `core/dlog.py` (BSGS, Pohlig–Hellman) |
| **CLI** | `app/` (`cli.py`, `gui.py`, `filecrypt.py`, `benchmark.py`, `__init__.py`) |
| **Test** | `tests/` |

## Cấu trúc và thứ tự phụ thuộc

```
core/dh.py        không import module nào của dự án (nền tảng)
core/stream.py    dùng dh
core/dlog.py      dùng dh, stream
app/*             dùng dh, stream, dlog
tests/*           dùng tất cả
```

Vì vậy thứ tự tải lên nên là: `core/dh.py` → `core/stream.py` → `core/dlog.py` → `app/` → `tests/`.
Chương trình chỉ chạy được khi đã có đủ `core/` và `app/`.

## Chạy chương trình

Cần Python 3.9 trở lên. Chạy từ thư mục gốc của repo:

```bash
python -m app.cli          # menu dòng lệnh, chọn mục demo từ 0 đến 8
python -m app.cli --auto   # chạy liền toàn bộ kịch bản demo
python -m app.gui          # giao diện đồ hoạ (Tkinter)
```

Mục 8 (vẽ biểu đồ benchmark) cần `pip install matplotlib`; các mục khác không cần thư viện ngoài.

## Kiểm thử

Khi đã có thư mục `tests/`:

```bash
pip install -r tests/requirements.txt   # pytest, sympy, mpmath, matplotlib (chỉ dùng trong tests/ để đối chiếu)
python -m pytest tests -q               # toàn bộ test (khoảng 40 giây)
python -m pytest tests -q -m "not cham" # bỏ các test chạy lâu
python tests/run_report.py              # báo cáo kiểm thử DH, ghi docs/test_log.txt
```

## Ví dụ tính tay

p = 23, g = 5, a = 6, b = 15 cho A = 8, B = 19 và khoá chung K = 2.
Mô phỏng MITM với c = 3: M = 10, Alice giữ khoá 6, Bob giữ khoá 5.

## Quy trình Git

1. Mỗi người sửa đúng phần của mình trên nhánh riêng (ví dụ `feat/stream`, `feat/cli`, `feat/tests`).
2. Mở Pull Request vào `main`; Lead review rồi merge (`.github/CODEOWNERS` tự gán người review).
3. Commit theo dạng `feat: ...`, `fix: ...`, `test: ...`, `docs: ...`.

## Lưu ý

- RSA trong phần phòng thủ chỉ 64 bit để minh hoạ, không dùng trong thực tế.
- Mã dòng trong `core/stream.py` chỉ để minh hoạ, không có xác thực toàn vẹn.
- Các tham số p nhỏ (p = 23, p 32 đến 40 bit) chỉ để học; thực tế dùng p >= 2048 bit (nhóm RFC 3526).
