"""
Bóc tách dữ liệu từ PDF, hình ảnh, và Excel.
Hỗ trợ hai chế độ:
  - Không có API key: pdfplumber (PDF), pytesseract (ảnh), pandas (Excel)
  - Có Claude API key: Claude Vision/Text cho PDF và ảnh (thông minh hơn)
"""

import io
import re
import json
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VN_ORDER_ID = [
    r'(?:mã\s*đơn\s*hàng|số\s*đơn|đơn\s*hàng\s*số|order\s*(?:id|no|number))[:\s]*([A-Z0-9\-/]+)',
    r'\b(?:ĐH|DH|PO)[:\s#]*([A-Z0-9\-/]+)',
]
_VN_CUSTOMER = [
    # "Khách hàng:" → label tường minh, ưu tiên cao
    r'khách\s*hàng[:\s]+([^\n]{3,80})',
    # "Kính gửi: Công ty X" → gửi thẳng đến công ty
    r'kính\s*gửi[:\s]+((?:công\s*ty|cty|tnhh|cp\b)[^\n]{2,70})',
    # "Kính gửi: Anh X / Công ty Y" → lấy phần sau dấu /
    r'kính\s*gửi[:\s]+(?:anh|chị|chi|ông|ong|bà|ba|mr\.?|ms\.?|mrs\.?)[^/\n]+/\s*([^\n]{3,60})',
    # "Kính gửi: X" — chỉ lấy nếu X không phải tên người
    r'kính\s*gửi[:\s]+(?!(?:anh|chị|chi|ông|ong|bà|ba|mr\.?|ms\.?|mrs\.?)\s)([^\n]{3,80})',
    # Fallback cuối: "Đơn vị", generic
    r'(?:đơn\s*vị|customer|client)[:\s]+([^\n]{3,60})',
]

# Danh xưng → đây là tên người, không phải công ty
_PERSON_TITLE_RE = re.compile(
    r'^(?:anh|chị|chi|ông|ong|bà|ba|mr\.?|ms\.?|mrs\.?)\s+',
    re.IGNORECASE,
)

# Marker kết thúc phần letterhead (bắt đầu nội dung đơn hàng)
_HEADER_END_RE = re.compile(
    r'kính\s*gửi|đơn\s*(?:đặt\s*)?hàng|hóa\s*đơn|purchase\s*order|invoice',
    re.IGNORECASE,
)

_VN_ORDER_DATE = [
    r'(?:ngày\s*đặt(?:\s*hàng)?|order\s*date)[:\s]*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})',
    # "Ngày 11/05/2026" trong phần tiêu đề đơn hàng
    r'(?<!\w)ngày[:\s]+(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})',
]
_VN_DELIVERY = [
    r'(?:ngày\s*giao(?:\s*hàng)?|hạn\s*giao|delivery\s*date)[:\s]*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})',
    r'(?:thời\s*gian\s*giao\s*hàng|ngày\s*nhận)[:\s]*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})',
]


def _first_match(patterns, text):
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


_CUSTOMER_STOP_RE = re.compile(
    r'\s+(?:địa\s*chỉ|điện\s*thoại|đt\s*:|fax\s*:|mst\s*:|email\s*:|website\s*:|www\.)',
    re.IGNORECASE,
)

# Tên đơn vị nhận in — loại trừ khỏi cột Khách hàng
_OWN_COMPANY_RE = re.compile(r'ho[àa]ng\s*an', re.IGNORECASE)


def _is_own_company(name: str) -> bool:
    return bool(_OWN_COMPANY_RE.search(name))


def _extract_letterhead_company(text: str) -> str:
    """
    Trích tên công ty từ phần letterhead đầu văn bản (trước 'Kính gửi'/'Đơn đặt hàng').
    VD: 'CÔNG TY TNHH BIG CROP\\n51 Đường...' → 'CÔNG TY TNHH BIG CROP'
    """
    m_end = _HEADER_END_RE.search(text)
    header_zone = text[:m_end.start()] if m_end else text[:400]

    m = re.search(
        r'(công\s*ty\s+(?:tnhh\s+|cổ\s*phần\s+|cp\s+|hợp\s*danh\s+)?[^\n,;]{2,60}?)'
        r'(?:\n|,|;|địa\s*chỉ|điện\s*thoại|đt\s*:|mst\s*:|$)',
        header_zone, re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return ""


def parse_order_info(text: str) -> dict:
    customer = ""

    # Ưu tiên 1: label tường minh ("Kính gửi:", "Khách hàng:", ...)
    for pat in _VN_CUSTOMER:
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            continue
        val = m.group(1).strip()
        if _PERSON_TITLE_RE.match(val):
            continue
        m_stop = _CUSTOMER_STOP_RE.search(val)
        candidate = val[:m_stop.start()].strip() if m_stop else val[:80].strip()
        # Bỏ qua nếu là tên đơn vị nhận in (Hoàng An)
        if candidate and not _is_own_company(candidate):
            customer = candidate
            break

    # Ưu tiên 2: letterhead đầu văn bản (fallback)
    if not customer:
        letterhead = _extract_letterhead_company(text)
        if letterhead and not _is_own_company(letterhead):
            customer = letterhead

    return {
        "order_id": _first_match(_VN_ORDER_ID, text),
        "customer": customer,
        "order_date": _first_match(_VN_ORDER_DATE, text),
        "delivery_date": _first_match(_VN_DELIVERY, text),
    }


_COL_MAP = {
    # Tên sản phẩm
    "tên hàng": "Tên sản phẩm", "tên hàng hóa": "Tên sản phẩm",
    "tên sản phẩm": "Tên sản phẩm", "mặt hàng": "Tên sản phẩm",
    "tên mặt hàng": "Tên sản phẩm", "sản phẩm": "Tên sản phẩm",
    "hàng hóa": "Tên sản phẩm", "item": "Tên sản phẩm",
    "product": "Tên sản phẩm", "description": "Tên sản phẩm",
    "diễn giải": "Tên sản phẩm", "tên sp": "Tên sản phẩm",
    # Mã sản phẩm
    "mã hàng": "Mã sản phẩm", "mã sản phẩm": "Mã sản phẩm",
    "mã mặt hàng": "Mã sản phẩm", "mã sp": "Mã sản phẩm",
    "mã": "Mã sản phẩm", "code": "Mã sản phẩm",
    "sku": "Mã sản phẩm", "item code": "Mã sản phẩm",
    # Số lượng
    "số lượng": "Số lượng", "sl": "Số lượng",
    "qty": "Số lượng", "quantity": "Số lượng",
    "số lượng nhãn": "Số lượng nhãn",
    "số lượng hộp": "Số lượng hộp",
    "số lượng thùng": "Số lượng thùng",
    # Đơn vị
    "đvt": "Đơn vị", "unit": "Đơn vị", "uom": "Đơn vị",
    # Ghi chú
    "ghi chú": "Ghi chú", "note": "Ghi chú",
    "notes": "Ghi chú", "remark": "Ghi chú",
    # Khác
    "kích thước": "Kích thước", "size": "Kích thước",
    "màu sắc": "Màu sắc", "color": "Màu sắc", "colour": "Màu sắc",
    "chất liệu": "Chất liệu", "material": "Chất liệu",
}


def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = re.sub(r'\s+', ' ', str(col).lower().strip())
        if key in _COL_MAP:
            rename[col] = _COL_MAP[key]
        else:
            # Starts-with fallback: "tên mặt hàng [thông số]" → "tên mặt hàng"
            for map_key, map_val in _COL_MAP.items():
                if key.startswith(map_key) and len(map_key) >= 3:
                    rename[col] = map_val
                    break
    return df.rename(columns=rename) if rename else df


def _find_header_row(df_raw: pd.DataFrame):
    """Return index of the row with the most individual cells matching header keywords."""
    keywords = {
        "tên hàng", "tên hàng hóa", "tên sản phẩm", "tên sp",
        "số lượng", "sl", "qty", "quantity",
        "mã hàng", "mã sp", "mã sản phẩm",
        "đvt", "unit", "item", "product", "description", "stt",
    }
    best_idx, best_score = None, 0
    for i, row in df_raw.iterrows():
        # Đếm số cell khớp thay vì tổng keyword — tránh merged-cell bự được điểm cao giả
        score = sum(
            1 for v in row
            if pd.notna(v) and any(kw in re.sub(r'\s+', ' ', str(v).lower()) for kw in keywords)
        )
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx if best_score >= 1 else None


# ---------------------------------------------------------------------------
# Post-processing: tách kích thước + phân loại sheet tự động
# ---------------------------------------------------------------------------

# Pattern: số x số (x số tuỳ chọn) (cm/mm tuỳ chọn) — nhận cả 2D và 3D
_DIM_RE = re.compile(
    r'(\d+[\.,]?\d*\s*[xX×]\s*\d+[\.,]?\d*'
    r'(?:\s*[xX×]\s*\d+[\.,]?\d*)?'
    r'(?:\s*(?:cm|mm))?)'
    r'(?:\s+KTPB)?',
    re.IGNORECASE,
)
_SUFFIX_RE = re.compile(r'\s*[-–]\s*$|\s+KTPB\s*$', re.IGNORECASE)

SHEET_NAMES_ALL = [
    "Nhãn C115", "Nhãn Decan",
    "Hộp",
    "Thùng carton",
    "Túi màng",
    "Tổng hợp",
]

# ── Từ khoá nhận dạng nhãn ───────────────────────────────────────────────────
_NHAN_BASE_KW  = ["nhãn", "nhản", "nhan ", "label"]
_NHAN_DECAN_KW = ["tem ", "decan", "nhãn decan", "nhan decan",
                   "sticker", "bế ", "be dán", "be dan",
                   "nhãn dán", "nhan dan"]                       # Nhãn Decan
_NHAN_C115_KW  = ["c115", "nhãn giấy", "nhan giay", "giấy c1"] # Nhãn C115

# ── Từ khoá túi màng ─────────────────────────────────────────────────────────
_TUI_KW = ["túi ", "tui ", "túi zip", "ziplock", "zip lock",
           "màng co", "mang co", "màng pe", "mang pe",
           "màng pp", "mang pp", "màng bopp", "mang bopp",
           "bao bì pe", "bao bi pe", "bao bì pp", "bao bi pp",
           "túi đứng", "túi nằm", "túi dẹt", "stand up pouch",
           "film ", " opp ", "bopp"]

# ── Từ khoá loại chính (hộp / thùng) ─────────────────────────────────────────
_HOP_KW   = ["hộp ", "hop ", "hộp giấy", "hộp cứng", "hộp màu", "hộp in",
              " box ", "folding box"]
_THUNG_KW = ["thùng", "thung ", "master carton", "outer carton"]

# ── Từ khoá sub-type hộp / thùng ─────────────────────────────────────────────
# Chỉ Duplex 350/400 là Hộp Duplex — Duplex 250g chỉ là chất liệu bồi, không phải loại hộp
_HOP_DUP_KW = ["duplex 350", "duplex 400", "dup 350", "dup 400"]
_HOP_BOI_KW = ["bồi", "boi ", "d250", "d 250", "giấy d",
               "carton e", "carton b", "e flute", "b flute"]


def classify_sheet(product_name: str) -> str:
    """
    Phân loại phân cấp: xác định loại chính → sub-type.
    Ưu tiên 25 ký tự đầu để tránh bắt từ khoá giữa tên.
    """
    name_low   = product_name.lower()
    name_start = name_low[:25]
    name_full  = f" {name_low} "

    def _any(kws): return any(k in name_full for k in kws)

    # ── Nhãn ──────────────────────────────────────────────
    # Decan/tem/bế → Nhãn Decan; tất cả còn lại (kể cả C115 và generic) → Nhãn C115
    is_nhan = any(name_start.startswith(k.strip()) for k in _NHAN_BASE_KW) \
              or _any(_NHAN_BASE_KW) or _any(_NHAN_DECAN_KW) or _any(_NHAN_C115_KW)
    if is_nhan:
        if _any(_NHAN_DECAN_KW):
            return "Nhãn Decan"
        return "Nhãn C115"

    # ── Túi màng ──────────────────────────────────────────
    if _any(_TUI_KW):
        return "Túi màng"

    # ── Xác định loại chính từ đầu tên ────────────────────
    starts_hop   = any(name_start.startswith(k.strip()) for k in _HOP_KW)
    starts_thung = any(name_start.startswith(k.strip()) for k in _THUNG_KW)

    is_hop   = starts_hop or _any(_HOP_KW)
    is_thung = starts_thung or _any(_THUNG_KW)

    # "carton" đơn thuần → thùng — nhưng chỉ khi không có ngữ cảnh hộp
    if "carton" in name_full and not is_hop:
        is_thung = True

    # Từ khoá vật liệu hộp (bồi, D250...) → đây là hộp khi không xác định được thùng
    if _any(_HOP_BOI_KW) and not starts_thung:
        is_hop = True

    # Khi cả hai có mặt, ưu tiên loại đứng đầu tên
    if is_hop and is_thung:
        if starts_thung:
            is_hop = False   # "Thùng... x 20 hộp" → thùng thắng
        else:
            is_thung = False  # "Hộp...", "Giấy bồi carton sóng E" → hộp thắng

    # ── Hộp — tất cả vào một sheet ───────────────────────
    if is_hop:
        return "Hộp"

    # ── Thùng — tất cả vào một sheet ─────────────────────
    if is_thung:
        return "Thùng carton"

    return "Tổng hợp"


def _split_name_size(name: str) -> tuple[str, str]:
    m = _DIM_RE.search(name)
    if not m:
        return name.strip(), ""
    dim = m.group(1).strip()
    clean = _DIM_RE.sub("", name).strip()
    clean = _SUFFIX_RE.sub("", clean).strip()
    return clean, dim


_SUMMARY_ROW_RE = re.compile(
    r'^(tổng|tong |cộng|cong |vat|thuế|thue |ghi chú|note|total|subtotal'
    r'|số tiền|thời gian|địa điểm|địa chỉ|điều kiện|thanh toán'
    r'|so tien|thoi gian|dia diem|dia chi'
    r'|xác nhận|xac nhan|chữ ký|chu ky|người lập|nguoi lap'
    r'|người mua|đại diện|dai dien|người bán|ban giao'
    r'|công ty|cong ty$)',
    re.IGNORECASE,
)


def _postprocess(records: list[dict]) -> list[dict]:
    """
    Với mỗi record:
    - Tách kích thước ra cột 'Kích thước'
    - Gán cột '_sheet': dùng '_sheet_hint' (từ tên sheet Excel) nếu có, ngược lại phân loại theo tên sản phẩm
    - Lọc bỏ dòng trắng và dòng tổng cộng/VAT
    """
    out = []
    for rec in records:
        sp = str(rec.get("Tên sản phẩm", "") or "").strip()
        if sp.lower() in ("nan", "none", "-"):
            sp = ""
        sl = str(rec.get("Số lượng", "") or "").strip().replace("nan", "")

        # Bỏ dòng hoàn toàn trắng
        if not sp and not sl:
            continue

        # Bỏ dòng tổng cộng / VAT / chữ ký / footer
        if _SUMMARY_ROW_RE.match(sp) or sp.endswith(":"):
            continue

        # Bỏ dòng có SL trông như tên người/công ty (chữ cái >= 10, không có số)
        if sl and not re.search(r'\d', sl) and len(sl) >= 8:
            continue

        rec = dict(rec)

        # Tách kích thước
        if sp and not rec.get("Kích thước"):
            clean, dim = _split_name_size(sp)
            rec["Tên sản phẩm"] = clean
            sp = clean
            if dim:
                rec["Kích thước"] = dim

        # Phân loại sheet: ưu tiên hint từ tên sheet Excel, fallback theo tên sản phẩm
        hint = str(rec.pop("_sheet_hint", "") or "").strip()
        rec["_sheet"] = hint if hint and hint != "Tổng hợp" else classify_sheet(sp)

        out.append(rec)
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_from_file(uploaded_file, claude_api_key: str | None = None) -> dict:
    """
    Returns:
        {success, data: list[dict], order_info: dict, warning: str, error: str}
    """
    name = uploaded_file.name.lower()
    try:
        if name.endswith((".xlsx", ".xls")):
            return _from_excel(uploaded_file)
        elif name.endswith(".pdf"):
            if claude_api_key:
                return _from_pdf_claude(uploaded_file, claude_api_key)
            return _from_pdf(uploaded_file)
        elif name.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")):
            if claude_api_key:
                return _from_image_claude(uploaded_file, claude_api_key)
            return _from_image_ocr(uploaded_file)
        else:
            return _err("Định dạng file không hỗ trợ")
    except Exception as exc:
        return _err(str(exc))


def _ok(data, order_info=None, warning=""):
    return {"success": True, "data": data, "order_info": order_info or {}, "warning": warning, "error": ""}


def _err(msg):
    return {"success": False, "data": [], "order_info": {}, "warning": "", "error": msg}


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def _from_excel(uploaded_file) -> dict:
    xls = pd.ExcelFile(uploaded_file)
    all_frames = []
    order_info = {}

    for sheet_name in xls.sheet_names:
        raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        if raw.empty:
            continue

        header_row = _find_header_row(raw)

        if header_row is not None:
            pre_text = " ".join(
                str(v) for i, row in raw.iterrows() if i < header_row
                for v in row if pd.notna(v)
            )
            order_info.update({k: v for k, v in parse_order_info(pre_text).items() if v})
            df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row)
        else:
            df = pd.read_excel(xls, sheet_name=sheet_name)

        df = df.dropna(how="all").reset_index(drop=True)
        if df.empty:
            continue
        df = map_columns(df)

        # Nếu tên sheet khớp chủng loại → dùng làm phân loại trực tiếp
        sheet_type = classify_sheet(sheet_name)
        if sheet_type != "Tổng hợp":
            df["_sheet_hint"] = sheet_type

        all_frames.append(df)

    if not all_frames:
        return _err("Không đọc được dữ liệu từ file Excel")

    combined = pd.concat(all_frames, ignore_index=True)
    if "STT" not in combined.columns:
        combined.insert(0, "STT", range(1, len(combined) + 1))
    else:
        combined["STT"] = range(1, len(combined) + 1)
    records = _postprocess(combined.to_dict("records"))
    return _ok(records, order_info)


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

_TABLE_HEADER_KW = {
    "tên hàng", "tên sản phẩm", "tên sp", "mặt hàng", "hàng hóa",
    "số lượng", "sl", "qty", "quantity",
    "mã hàng", "mã sp", "mã sản phẩm",
    "đvt", "unit", "item", "product", "description", "stt",
}


def _norm_cell(val) -> str:
    """Normalize a cell value: strip, collapse whitespace."""
    if val is None:
        return ""
    return re.sub(r'\s+', ' ', str(val).strip())


def _find_table_header_row(table: list) -> int:
    """
    Return the row index that looks most like a column-header row.
    Score = number of individual cells that contain a keyword.
    This avoids picking a giant merged-cell row that embeds the whole document.
    """
    best_idx, best_score = 0, 0
    for i, row in enumerate(table):
        # Count cells (not total keywords) that match — a real header has many short cells
        cell_hits = sum(
            1 for c in row
            if c and any(kw in re.sub(r'\s+', ' ', str(c).lower()) for kw in _TABLE_HEADER_KW)
        )
        if cell_hits > best_score:
            best_score, best_idx = cell_hits, i
    return best_idx


def _table_to_df(table: list) -> "pd.DataFrame | None":
    """
    Convert a pdfplumber table to a mapped DataFrame.
    - Finds the real header row (not always row 0)
    - Normalizes column names (strips newlines/spaces)
    - Drops all-empty columns and rows
    - Deduplicates column names (None → Cột{i})
    """
    header_idx = _find_table_header_row(table)
    raw_headers = table[header_idx]

    # Build unique, normalized header list
    seen: dict[str, int] = {}
    headers = []
    for i, h in enumerate(raw_headers):
        name = _norm_cell(h) if h else ""
        if not name:
            name = f"Cột{i}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        headers.append(name)

    data_rows = [
        [_norm_cell(c) for c in row]
        for row in table[header_idx + 1:]
        if any(c and _norm_cell(c) for c in row)
    ]
    if not data_rows:
        return None

    df = pd.DataFrame(data_rows, columns=headers)
    # Drop columns that are entirely empty or are generic Cột{n} with no data
    non_empty_cols = [c for c in df.columns if df[c].replace("", pd.NA).notna().any()]
    df = df[non_empty_cols].dropna(how="all")
    if df.empty:
        return None
    return map_columns(df)


# ---------------------------------------------------------------------------
# PDF (pdfplumber)
# ---------------------------------------------------------------------------

def _from_pdf(uploaded_file) -> dict:
    try:
        import pdfplumber
    except ImportError:
        return _err("Cần cài pdfplumber: pip install pdfplumber")

    pdf_bytes = uploaded_file.read()
    all_frames = []
    full_text = ""

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

            for table in page.extract_tables() or []:
                if not table or len(table) < 2:
                    continue
                df = _table_to_df(table)
                # Bỏ qua bảng metadata nhỏ (< 2 cột có dữ liệu hoặc < 2 dòng data)
                if df is not None and len(df.columns) >= 2 and len(df) >= 1:
                    all_frames.append(df)

    order_info = parse_order_info(full_text)

    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
        combined = combined.fillna("").astype(str).replace("nan", "")
        if "STT" not in combined.columns:
            combined.insert(0, "STT", range(1, len(combined) + 1))
        else:
            combined["STT"] = range(1, len(combined) + 1)
        records = _postprocess(combined.to_dict("records"))
        return _ok(records, order_info)
    elif full_text.strip():
        lines = [l.strip() for l in full_text.splitlines() if l.strip()]
        data = [{"Nội dung": line} for line in lines[:100]]
        return _ok(data, order_info, warning="Không phát hiện bảng — hiển thị text thô, vui lòng chỉnh sửa thủ công")
    else:
        return _err("Không đọc được nội dung PDF (có thể là ảnh scan — hãy dùng Claude API key)")


# ---------------------------------------------------------------------------
# Image (pytesseract OCR)
# ---------------------------------------------------------------------------

def _from_image_ocr(uploaded_file) -> dict:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return _err(
            "Cần cài pytesseract + Tesseract OCR.\n"
            "Hoặc nhập Claude API key để đọc ảnh bằng AI (không cần cài thêm gì)."
        )

    image = Image.open(uploaded_file)
    try:
        text = pytesseract.image_to_string(image, lang="vie+eng")
    except Exception:
        try:
            text = pytesseract.image_to_string(image, lang="eng")
        except Exception as e:
            return _err(f"Lỗi OCR: {e}")

    order_info = parse_order_info(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return _err("Không đọc được text từ hình ảnh")

    data = [{"Nội dung OCR": line} for line in lines]
    return _ok(data, order_info, warning="OCR xong — vui lòng kiểm tra và chỉnh sửa dữ liệu trước khi xuất")


# ---------------------------------------------------------------------------
# Claude API — PDF
# ---------------------------------------------------------------------------

_CLAUDE_PROMPT = """Bạn là trợ lý đọc đơn hàng sản xuất in ấn/bao bì Việt Nam. Bóc tách toàn bộ sản phẩm thành JSON:
{
  "order_info": {
    "order_id": "mã đơn hàng hoặc số PO (để trống nếu không có)",
    "customer": "tên công ty đặt hàng (KHÔNG ghi tên người liên hệ, KHÔNG ghi Hoàng An)",
    "order_date": "dd/mm/yyyy",
    "delivery_date": "dd/mm/yyyy"
  },
  "products": [
    {
      "Tên sản phẩm": "tên đầy đủ, không kèm kích thước nếu có thể tách riêng",
      "Mã sản phẩm": "",
      "Số lượng": "chỉ số, không kèm đơn vị",
      "Đơn vị": "cái/hộp/thùng/cuộn/kg...",
      "Kích thước": "VD: 10x15 cm hoặc 10x15x5 cm",
      "Màu sắc": "",
      "Ghi chú": "",
      "sheet": "phân loại theo quy tắc dưới đây"
    }
  ]
}

Quy tắc phân loại trường "sheet" (chọn đúng 1 trong 6 giá trị):
- "Nhãn C115"    : nhãn giấy, label, C115, nhãn in offset (KHÔNG phải tem/decan/sticker)
- "Nhãn Decan"   : tem, decal, decan, sticker, nhãn dán, bế nhãn, nhãn tự dính
- "Hộp"          : hộp giấy, hộp màu, hộp bồi, hộp Duplex, hộp carton, hộp in
- "Thùng carton" : thùng carton, thùng đựng, master carton, outer carton, thùng sóng
- "Túi màng"     : túi PE/PP/OPP/BOPP, túi ziplock, màng co, túi đứng, film bao gói
- "Tổng hợp"     : không khớp loại nào trên

Lưu ý quan trọng:
- Liệt kê TẤT CẢ sản phẩm, không bỏ sót dòng nào
- Bỏ qua các dòng tổng cộng, VAT, chữ ký, địa chỉ
- Chỉ trả về JSON thuần, không giải thích thêm

Nội dung:
"""


def _parse_claude_json(text: str) -> dict | None:
    m = re.search(r'\{[\s\S]+\}', text)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


_MAX_CHUNK = 40_000  # ký tự / lần gọi Claude


def _call_claude_extract(client, text_chunk: str) -> dict | None:
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": _CLAUDE_PROMPT + text_chunk}],
    )
    return _parse_claude_json(msg.content[0].text)


def _apply_claude_sheet_hints(products: list[dict]) -> list[dict]:
    """Chuyển trường 'sheet' Claude trả về thành '_sheet_hint' cho _postprocess."""
    for rec in products:
        claude_sheet = str(rec.pop("sheet", "") or "").strip()
        if claude_sheet in SHEET_NAMES_ALL:
            rec["_sheet_hint"] = claude_sheet
    return products


def _from_pdf_claude(uploaded_file, api_key: str) -> dict:
    try:
        import anthropic
        import pdfplumber
    except ImportError as e:
        return _err(f"Thiếu thư viện: {e}")

    pdf_bytes = uploaded_file.read()
    full_text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
    except Exception:
        pass

    if not full_text.strip():
        return _err("PDF rỗng hoặc là ảnh scan — không thể đọc text. Hãy chuyển sang ảnh.")

    client = anthropic.Anthropic(api_key=api_key)

    # Chia chunk nếu text quá dài — tránh mất sản phẩm cuối file
    if len(full_text) <= _MAX_CHUNK:
        chunks = [full_text]
    else:
        chunks = [full_text[i:i + _MAX_CHUNK] for i in range(0, len(full_text), _MAX_CHUNK)]

    all_products: list[dict] = []
    order_info: dict = {}
    for chunk in chunks:
        parsed = _call_claude_extract(client, chunk)
        if not parsed:
            continue
        if not order_info:
            oi = parsed.get("order_info", {})
            if _is_own_company(oi.get("customer", "")):
                oi["customer"] = ""
            order_info = oi
        all_products.extend(parsed.get("products", []))

    if not all_products and not order_info:
        return _err("Claude không trả về JSON hợp lệ")

    all_products = _apply_claude_sheet_hints(all_products)
    records = _postprocess(all_products)
    return _ok(records, order_info)


# ---------------------------------------------------------------------------
# Claude API — Image (Vision)
# ---------------------------------------------------------------------------

def _from_image_claude(uploaded_file, api_key: str) -> dict:
    try:
        import anthropic
        import base64
    except ImportError as e:
        return _err(f"Thiếu thư viện: {e}")

    raw = uploaded_file.read()
    b64 = base64.standard_b64encode(raw).decode()

    name = uploaded_file.name.lower()
    if name.endswith(".png"):
        media_type = "image/png"
    elif name.endswith(".webp"):
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": _CLAUDE_PROMPT + "(ảnh đơn hàng)"},
            ],
        }],
    )
    parsed = _parse_claude_json(msg.content[0].text)
    if not parsed:
        return _err("Claude không trả về JSON hợp lệ")

    products = _apply_claude_sheet_hints(parsed.get("products", []))
    records = _postprocess(products)
    oi = parsed.get("order_info", {})
    if _is_own_company(oi.get("customer", "")):
        oi["customer"] = ""
    return _ok(records, oi)
