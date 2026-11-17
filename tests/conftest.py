"""
Cấu hình chung cho toàn bộ tests

Quy ước của nhóm: hashlib, sympy, mpmath và pow() chỉ được dùng trong tests/ để đối chiếu.
"""
import os
import random
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pytest_configure(config):
    config.addinivalue_line("markers", "cham: test chạy lâu (vài giây trở lên), bỏ qua bằng: -m 'not cham'")


@pytest.fixture(autouse=True)
def _hat_giong_co_dinh():
    """Mỗi test bắt đầu với cùng hạt giống ngẫu nhiên để kết quả lặp lại được."""
    random.seed(20261114)


@pytest.fixture
def thu_muc_tam(tmp_path, monkeypatch):
    """Chạy test trong thư mục tạm: các tệp samples/, docs/ sinh ra không làm bẩn repo."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
