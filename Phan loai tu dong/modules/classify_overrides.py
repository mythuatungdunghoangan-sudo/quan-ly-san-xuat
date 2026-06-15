"""
Bảng "học" phân loại: lưu lại các cặp (tên sản phẩm đã chuẩn hoá → loại do người dùng chọn tay)
để lần phân loại sau tự áp dụng, không cần sửa lại.

File lưu: data/classify_overrides.json (tạo tự động, nằm cạnh app.py)
Format: {"tên sản phẩm chuẩn hoá": "Tên sheet (Nhãn Decan, Hộp, ...)"}
"""

import json
import re
from pathlib import Path

OVERRIDES_PATH = Path("data/classify_overrides.json")


def _normalize_key(product_name: str) -> str:
    """
    Chuẩn hoá tên sản phẩm để dùng làm khoá tra override:
    - lowercase
    - bỏ khoảng trắng dư
    - bỏ cụm kích thước dạng số x số (vd: '28 x 16', '20lít x ...') kèm cm/mm
    - bỏ ngoặc rỗng còn sót lại sau khi xoá kích thước
    """
    s = str(product_name or "").lower().strip()
    s = re.sub(r'\s+', ' ', s)
    # Bỏ cụm kích thước "<số> x <số> [x <số>] [cm/mm]", có/không có dấu ngoặc bao quanh
    s = re.sub(
        r'[\(\{]?\s*\d+[\.,]?\d*\s*[xX×]\s*\d+[\.,]?\d*(?:\s*[xX×]\s*\d+[\.,]?\d*)?\s*(?:cm|mm)?\s*[\)\}]?',
        '', s,
    )
    # Bỏ đơn vị mồ côi (cm/mm) còn sót lại — phải làm trước khi xoá ngoặc rỗng
    s = re.sub(r'(?<![a-zà-ỹ])\s*(cm|mm)\b', '', s)
    # Bỏ các cặp ngoặc rỗng còn sót (lặp vài lần để xử lý ngoặc lồng nhau)
    for _ in range(3):
        s = re.sub(r'[\(\{]\s*[\)\}]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def load_overrides() -> dict[str, str]:
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_override(product_name: str, sheet_name: str) -> None:
    """Lưu/ghi đè 1 cặp (tên sản phẩm → loại) vào bảng học."""
    key = _normalize_key(product_name)
    if not key or not sheet_name:
        return
    overrides = load_overrides()
    if overrides.get(key) == sheet_name:
        return
    overrides[key] = sheet_name
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(overrides, f, ensure_ascii=False, indent=2, sort_keys=True)


def get_override(product_name: str) -> str:
    """Trả về loại đã học cho tên sản phẩm này, hoặc '' nếu chưa có."""
    overrides = load_overrides()
    return overrides.get(_normalize_key(product_name), "")


def remove_override(product_name: str) -> None:
    key = _normalize_key(product_name)
    overrides = load_overrides()
    if key in overrides:
        del overrides[key]
        OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
            json.dump(overrides, f, ensure_ascii=False, indent=2, sort_keys=True)
