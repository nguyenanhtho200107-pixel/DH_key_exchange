# Trao đổi khoá Diffie–Hellman

Bài tập lớn An toàn bảo mật thông tin: cài đặt trao đổi khoá Diffie–Hellman bằng Python thuần,
kèm bài toán logarit rời rạc (BSGS, Pohlig–Hellman), tấn công người đứng giữa (MITM) và cách phòng chống.

## Cấu trúc

| Thư mục | Nội dung | Phụ trách |
|---|---|---|
| `app/` | Giao diện dòng lệnh, demo mã hoá tệp, benchmark BSGS | Lead |
| `core/` | Thuật toán DH, SHA-256 tự viết, SAS, RSA đồ chơi, MITM, BSGS, mã dòng | Dev |

## Chạy chương trình

Cần Python 3.9 trở lên. Chạy từ thư mục gốc của repo:

```bash
python -m app.cli          # menu chọn mục demo từ 0 đến 8
python -m app.cli --auto   # chạy liền toàn bộ kịch bản demo
```

Mục 8 (vẽ biểu đồ benchmark) cần `pip install matplotlib`; các mục khác không cần thư viện ngoài.

## Ví dụ tính tay

p = 23, g = 5, a = 6, b = 15 cho A = 8, B = 19 và khoá chung K = 2.

## Lưu ý

 RSA trong phần phòng thủ chỉ 64 bit để minh hoạ, không dùng trong thực tế.
Mã dòng trong `core/stream.py` chỉ để minh hoạ, không có xác thực toàn vẹn.
