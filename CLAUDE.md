# CLAUDE.md — Quản Lý Sản Xuất

## Tổng quan dự án

Ứng dụng web (Streamlit) tổng hợp đơn hàng sản xuất: nhận file đơn hàng từ khách hàng (PDF, ảnh, Excel), bóc tách dữ liệu tự động, ghi vào file kế hoạch sản xuất theo template định sẵn.

**Lĩnh vực:** In ấn / bao bì — nhãn (label), hộp (box), thùng (carton).  
**Tech stack:** Python 3.11 · Streamlit · pandas · openpyxl · pdfplumber · Anthropic SDK.  
**Đơn vị sản xuất:** CÔNG TY TNHH MỸ THUẬT ỨNG DỤNG BAO BÌ HOÀNG AN (không bao giờ xuất hiện ở cột Khách hàng).

---

## Các app trong dự án

| App | Thư mục | Entry point | Port | Link Cloud |
|---|---|---|---|---|
| **Phân loại đơn hàng** | `Phan loai tu dong/` | `app.py` | 8501 | `quan-ly-san-xuat-4wnwfzg9zujxcjnfmptdq4.streamlit.app` |
| **Ký tài liệu** | `Ky tai lieu/` | `ky_tai_lieu.py` | 8502 | `ky-tai-lieu-hoang-an.streamlit.app` |

## Triển khai & truy cập

| Môi trường | Địa chỉ / Cách dùng |
|---|---|
| **Cloud — Phân loại đơn hàng** | `quan-ly-san-xuat-4wnwfzg9zujxcjnfmptdq4.streamlit.app` |
| **Cloud — Ký tài liệu** | `ky-tai-lieu-hoang-an.streamlit.app` |
| **Local — Phân loại đơn hàng** | Double-click `Phan loai tu dong\Phan loai tu dong.bat` → `http://localhost:8501` |
| **Local — Ký tài liệu** | Double-click `Ky tai lieu\Ky tai lieu.bat` → `http://localhost:8502` |
| **GitHub (source code)** | `github.com/mythuatungdunghoangan-sudo/quan-ly-san-xuat` |

---

## Cách chạy ứng dụng

```
Phan loai tu dong\Phan loai tu dong.bat    # double-click, mở localhost:8501
Ky tai lieu\Ky tai lieu.bat               # double-click, mở localhost:8502
```
Hoặc thủ công: `cd "Phan loai tu dong"` → `python -m streamlit run app.py`

`run.bat` đặt `PYTHONDONTWRITEBYTECODE=1` — Python không tạo `__pycache__`, tránh sync rác lên OneDrive.

PowerShell hiển thị `NativeCommandError` với stderr Streamlit — **không phải lỗi**.

---

## Cài đặt trên máy mới

> Double-click `cai_dat.bat` → tự tải Python nếu chưa có + cài thư viện (2–5 phút)  
> Sau đó dùng `run.bat` mỗi lần.

---

## Quy trình cập nhật code

```
git add .
git commit -m "mô tả thay đổi"
git push
```
Sau khi push, Streamlit Cloud tự triển khai lại trong ~1–2 phút.

---

## Cấu trúc thư mục

```
QuanLySanXuat/                          # Thư mục gốc (git repo)
├── CLAUDE.md                           # File này
├── HUONG_DAN.md / CAI_DAT_MAY_MOI.md
├── Phan loai tu dong/                  # App phân loại đơn hàng
│   ├── app.py                          # Entry point
│   ├── Phan loai tu dong.bat           # Launcher port 8501
│   ├── cai_dat.bat / requirements.txt
│   ├── .streamlit/config.toml          # Theme xanh #4472C4, port 8501
│   ├── modules/
│   │   ├── template_creator.py         # Tạo Excel template (6 sheet)
│   │   ├── extractor.py                # Bóc tách dữ liệu PDF/ảnh/Excel
│   │   └── excel_handler.py            # Ghi dữ liệu vào template
│   └── template/
│       └── ke_hoach_san_xuat.xlsx
└── Ky tai lieu/                        # App ký tài liệu
    ├── ky_tai_lieu.py                  # Entry point (toàn bộ code)
    ├── Ky tai lieu.bat                 # Launcher port 8502
    ├── requirements.txt
    ├── tu_khoa.txt                     # Từ khóa tìm vị trí ký
    └── chu_ky/
        └── Chu ky Hoang.png            # Ảnh chữ ký
```

---

## Cấu trúc 6 sheet trong template

| Sheet | Màu | Từ khoá phân loại |
|---|---|---|
| **Nhãn C115** | #2E75B6 | nhãn, label, nhãn giấy, C115 — tất cả nhãn giấy |
| **Nhãn Decan** | #9DC3E6 | tem, decan, bế, sticker, nhãn dán |
| **Hộp** | #70AD47 | hộp, box, bồi, D250, giấy D, duplex — TẤT CẢ loại hộp |
| **Thùng carton** | #ED7D31 | thùng, carton, dùng chung, con, mẹ, bồi, offset, flexo — TẤT CẢ loại thùng |
| **Túi màng** | #FF0066 | túi, màng PE/PP, ziplock, film, OPP, bopp |
| **Tổng hợp** | #7030A0 | sản phẩm không khớp loại nào → người dùng sửa thủ công |

**Quan trọng:**
- Hộp và Thùng không chia sub-type — mọi biến thể đều gộp vào 1 sheet
- Tổng hợp chứa TẤT CẢ sản phẩm từ mọi sheet (để đối chiếu kiểm tra) + thêm cột "Loại"
- Template tự tạo lại nếu thiếu sheet (`ensure_template` kiểm tra `TEMPLATE_COLUMNS`)

---

## Kiến trúc modules

### `modules/extractor.py`

**`extract_from_file(uploaded_file, claude_api_key)`** → `{success, data, order_info, warning, error}`

| File | Không có API key | Có Claude API key |
|---|---|---|
| Excel | pandas | pandas |
| PDF text | pdfplumber | Claude Sonnet 4.6 + pdfplumber |
| PDF scan | Báo lỗi | Claude Vision |
| Ảnh | pytesseract OCR | Claude Vision |

**`parse_order_info(text)`** — bóc tách mã đơn, khách hàng, ngày đặt, ngày giao:
- Ưu tiên label tường minh: "Kính gửi:", "Khách hàng:" → letterhead chỉ là fallback
- `_OWN_COMPANY_RE = re.compile(r'ho[àa]ng\s*an', re.IGNORECASE)` — lọc Hoàng An khỏi khách hàng
- Lọc "Hoàng An" áp dụng cho cả kết quả từ Claude API

**`classify_sheet(product_name)`** — logic phân cấp:
```
1. Nhãn Decan: tem/decan/bế/nhãn dán → Nhãn Decan
   Còn lại nhãn: nhãn/label/C115     → Nhãn C115

2. Túi màng: túi/màng PE/PP/ziplock  → Túi màng

3. Xác định is_hop / is_thung:
   - is_hop   = starts_hop OR _any(_HOP_KW)
   - is_thung = starts_thung OR _any(_THUNG_KW)
   - "carton" trong tên → is_thung=True (nếu không có hộp)
   - _HOP_BOI_KW (bồi/D250) → is_hop=True (nếu không starts_thung)
   - Conflict: starts_thung wins → is_hop=False; else is_thung=False

4. is_hop  → Hộp
   is_thung → Thùng carton
   else     → Tổng hợp
```

**Ví dụ quan trọng:**
- `"Thùng dùng chung - 250g x 20 hộp (Zipbi)"` → starts_thung=True → **Thùng carton** (dù có "hộp" trong tên)
- `"Giấy Duplex 250g, bồi carton sóng E"` → "bồi" kích hoạt is_hop, "carton" kích hoạt is_thung, no starts_thung → **Hộp**
- `"Nhãn dán thùng Nofara"` → "nhãn dán" → **Nhãn Decan**

**`_from_excel`** — đọc tất cả sheet, gắn `_sheet_hint` từ tên sheet nếu khớp loại:
- Sheet tên "Nhãn C115" → mọi sản phẩm trong sheet đó gắn hint "Nhãn C115"
- `_postprocess` dùng hint thay classify nếu hint != "Tổng hợp"

**`_postprocess(records)`**:
- Lọc dòng trắng và footer (Tổng cộng/VAT/chữ ký)
- Tách kích thước (NxN hoặc NxNxN, có/không đơn vị) ra cột riêng
- Gán `_sheet` = hint (từ tên sheet Excel) hoặc `classify_sheet(sp)`
- Gọi từ cả Excel lẫn Claude API (PDF + Vision)

### `modules/template_creator.py`
- `TEMPLATE_COLUMNS`: dict 6 sheet → danh sách cột
- `SHEET_COLORS`: màu tab
- `create_template(output_path)`: tạo Excel với header format + freeze panes

### `modules/excel_handler.py`
- `export_to_bytes(template_path, extracted_list)`: ghi dữ liệu → bytes (template KHÔNG bị sửa)
- `append_rows(ws, records, order_info)`: thêm dòng với alternating row color
- `_resolve_value(record, header, order_info)`: khớp chính xác → order_info fallback → fuzzy
- `_clean(v)`: trả `""` cho nan/None/null/"-"/"n/a"

---

## Luồng hoạt động (`app.py`)

```
Upload files (nhiều file, nhiều công ty)
    → extract_from_file() → records có cột _sheet + order_info
    → st.data_editor: hiển thị, cột "Loại" = selectbox 6 giá trị
    → Gom grouped[sheet]: order_info nhúng vào từng dòng
         (Mã đơn hàng / Khách hàng / Ngày đặt / Ngày giao per dòng)
    → export_to_bytes() → download
```

**Sheet Tổng hợp mirror tất cả**: mọi sản phẩm đều xuất hiện trong Tổng hợp kèm cột "Loại", đồng thời xuất hiện trong sheet chuyên biệt tương ứng.

---

## Claude API

- Nhập trong sidebar, không lưu, nhập lại mỗi lần mở
- Model: `claude-sonnet-4-6` (vision + text), max_tokens=4096
- PDF text: gửi toàn bộ, tự chunk 40.000 ký tự nếu dài (nhiều lần gọi, gộp kết quả)
- Prompt yêu cầu JSON `{order_info, products[]}` — mỗi product có thêm trường `"sheet"` để Claude phân loại luôn
- `_apply_claude_sheet_hints()` chuyển `"sheet"` → `"_sheet_hint"` trước khi `_postprocess`

---

## Vấn đề đã biết & cách giải quyết

| Vấn đề | Nguyên nhân | Giải pháp |
|---|---|---|
| Tên sản phẩm rỗng | `_find_header_row` chọn nhầm merged cell | Đếm keyword per-cell |
| "Tên Mặt hàng [Thông số]" không map | `map_columns` chỉ exact match | Thêm starts-with fallback |
| "Thùng... x 20 hộp" → Hộp | "hộp " bắt substring trong mô tả | Conflict resolution: starts_thung wins, clear is_hop |
| "Giấy Duplex 250g, bồi carton" → Thùng | "carton" → is_thung | `_HOP_BOI_KW` kích hoạt is_hop, hop wins khi không starts_thung |
| Dòng "Tổng cộng/VAT" vào data | Không lọc footer | `_SUMMARY_ROW_RE` + filter SL không chứa số |
| Lỗi TextColumn vs INTEGER | Streamlit 1.57+ | Convert toàn bộ cột sang str trước `data_editor` |
| Nhiều công ty bị trộn order_info | `order_info_by_sheet` chỉ lưu file đầu | Nhúng order_info vào từng record khi gom nhóm |
| "nan" trong file Excel | `_resolve_value` không lọc NaN | `_clean()` trả "" cho nan/None |
| "Hoàng An" vào cột Khách hàng | "Kính gửi: Hoàng An" → bắt nhầm | `_OWN_COMPANY_RE` lọc mọi candidate chứa "Hoàng An" |
| Khách hàng là tên Hoàng An từ letterhead | Letterhead ưu tiên cao hơn label | Đảo ưu tiên: label tường minh trước, letterhead fallback |
| Kích thước 2D bị bỏ qua | `_DIM_RE` chỉ match NxNxN | Sửa regex: NxN(xN tuỳ chọn) |
| Claude API không phân loại sheet | Claude không biết cần trả "sheet" | Thêm trường `"sheet"` vào prompt + `_apply_claude_sheet_hints()` map kết quả |
| Excel sheet riêng loại bị gộp chung | `_from_excel` không đọc tên sheet | `_sheet_hint` từ `classify_sheet(sheet_name)` |
| Thiếu sản phẩm cuối PDF dài | Cắt text ở 8000 ký tự | Chunk 40.000 ký tự, gọi Claude nhiều lần nếu cần |
| Template cũ thiếu sheet mới | `ensure_template` không kiểm tra nội dung | Kiểm tra đủ sheet trong `TEMPLATE_COLUMNS`, tạo lại nếu thiếu |
| NativeCommandError trong PowerShell | Streamlit ghi ra stderr | Không phải lỗi — app vẫn chạy bình thường |

---

## Mở rộng trong tương lai

- [ ] Đọc nhiều trang PDF scan bằng Claude Vision
- [ ] Trích xuất Ngày giao từ tên file (pattern `ĐH NAME NUM - DD.MM.xlsx`)
- [ ] Map cột tự động thông minh hơn (Claude so sánh cột nguồn vs template)
- [ ] Thêm sheet "Tiến độ" theo dõi trạng thái đơn hàng
- [ ] Lưu lịch sử đơn hàng vào SQLite
- [ ] Gửi email tóm tắt đơn hàng tự động
- [ ] Thêm công đoạn sản xuất: in, cán màng, bế, dán hộp

---

## Bối cảnh người dùng

- Công ty: **CÔNG TY TNHH MỸ THUẬT ỨNG DỤNG BAO BÌ HOÀNG AN** — đơn vị nhận in
- Nhận đơn hàng từ khách hàng dưới nhiều định dạng (PDF, ảnh, Excel)
- File Excel đơn hàng: thường là 1 sheet, header tại row 7–10, footer có VAT/chữ ký
- Cần tổng hợp vào một file Excel kế hoạch sản xuất thống nhất, phân loại đúng sheet
- Ưu tiên: dễ dùng, không cần kỹ thuật
