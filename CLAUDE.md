# CLAUDE.md — Quản Lý Sản Xuất

## Tổng quan dự án

Ứng dụng web (Streamlit) tổng hợp đơn hàng sản xuất: nhận file đơn hàng từ khách hàng (PDF, ảnh, Excel), bóc tách dữ liệu tự động, ghi vào file kế hoạch sản xuất theo template định sẵn.

**Lĩnh vực:** In ấn / bao bì — nhãn (label), hộp (box), thùng (carton).  
**Tech stack:** Python 3.14 · Streamlit 1.57 · pandas · openpyxl · pdfplumber · Anthropic SDK.

---

## Triển khai & truy cập

| Môi trường | Địa chỉ / Cách dùng |
|---|---|
| **Cloud (Streamlit Community)** | `quan-ly-san-xuat-4wnwfzg9zujxcjnfmptdq4.streamlit.app` |
| **Local (máy hiện tại)** | Double-click `run.bat` → `http://localhost:8501` |
| **GitHub (source code)** | `github.com/mythuatungdunghoangan-sudo/quan-ly-san-xuat` |

---

## Cách chạy ứng dụng

### Cách 1 — Double-click (dễ nhất)
```
run.bat
```
> Tên file `run.bat` có thể đổi thành bất kỳ tên nào cho dễ hiểu (vd: `Mo_App.bat`).

### Cách 2 — Command line
```
cd "D:\OneDrive\Claude\QuanLySanXuat"
python -m streamlit run app.py
```
Trình duyệt tự mở tại `http://localhost:8501`.

### Lưu ý terminal Windows
PowerShell hiển thị cảnh báo `NativeCommandError` với stderr của Streamlit — **đây không phải lỗi**. App vẫn chạy bình thường.

---

## Cài đặt trên máy mới

> **Bước 1 (một lần duy nhất):** Double-click `cai_dat.bat`
> - Tự tải Python 3.11 nếu chưa có (cần internet, ~27MB)
> - Tự cài toàn bộ thư viện từ `requirements.txt`
> - Mất 2–5 phút
>
> **Bước 2 (mỗi lần dùng):** Double-click `run.bat`

Cài thủ công (nếu đã có Python):
```
pip install -r requirements.txt
```

---

## Quy trình cập nhật code

Sau mỗi lần chỉnh sửa code, đẩy lên GitHub để cloud tự cập nhật:

```
git add .
git commit -m "mô tả thay đổi"
git push
```

Hoặc nói với Claude Code: **"đẩy code lên GitHub"** — Claude tự chạy lệnh git.

**Sau khi push:** Streamlit Cloud tự nhận và triển khai lại trong ~1–2 phút.

---

## Cấu trúc thư mục

```
QuanLySanXuat/
├── app.py                      # Entry point — giao diện Streamlit
├── run.bat                     # Khởi động app (double-click)
├── cai_dat.bat                 # Cài đặt lần đầu cho máy mới
├── requirements.txt            # Danh sách thư viện Python
├── CLAUDE.md                   # File này — context cho Claude Code
├── HUONG_DAN.md                # Hướng dẫn sử dụng cho người dùng cuối
├── README.md
├── .gitignore                  # Loại trừ: __pycache__, .xlsx, ảnh, .claude/
├── .streamlit/
│   └── config.toml             # Theme xanh #4472C4, port 8501
├── modules/
│   ├── __init__.py
│   ├── template_creator.py     # Tạo file Excel template (5 sheet)
│   ├── extractor.py            # Bóc tách dữ liệu từ PDF/ảnh/Excel
│   └── excel_handler.py        # Ghi dữ liệu vào template, xuất file
└── template/
    └── ke_hoach_san_xuat.xlsx  # Template Excel (tự tạo khi chạy lần đầu)
```

---

## Kiến trúc modules

### `modules/template_creator.py`
- `TEMPLATE_COLUMNS`: dict định nghĩa cột cho mỗi sheet
- `SHEET_COLORS`: màu tab cho mỗi sheet
- `create_template(output_path)`: tạo file Excel với 5 sheet định dạng sẵn

**5 sheet trong template:**
| Sheet | Màu | Mô tả |
|---|---|---|
| Nhãn | #4472C4 | Kế hoạch sản xuất nhãn (label) |
| Hộp | #70AD47 | Kế hoạch sản xuất hộp (box) |
| Thùng | #ED7D31 | Kế hoạch sản xuất thùng/carton |
| Túi màng | #FF0066 | Túi zip, màng PE/PP, màng co |
| Tổng hợp | #7030A0 | Tổng hợp chung tất cả loại |

### `modules/extractor.py`
- `extract_from_file(uploaded_file, claude_api_key)` → `{success, data, order_info, warning, error}`
- Tự chọn engine dựa trên loại file và có/không có API key:

| File | Không có API key | Có Claude API key |
|---|---|---|
| Excel (.xlsx/.xls) | pandas (luôn dùng) | pandas (luôn dùng) |
| PDF text | pdfplumber | Claude text + pdfplumber |
| PDF scan | Báo lỗi | Claude Vision |
| Ảnh (JPG/PNG...) | pytesseract OCR | Claude Vision |

- `parse_order_info(text)`: regex bóc tách mã đơn, khách hàng, ngày đặt, ngày giao
  - **Khách hàng**: ưu tiên "Kính gửi:" → "Khách hàng:" → fallback "Đơn vị:". Tự động cắt bỏ phần địa chỉ sau tên
  - **Mã đơn hàng**: nhận dạng "ĐƠN HÀNG\nSố 08/2026" (multi-line), "ĐH/DH/PO" prefix
  - **Ngày đặt**: nhận dạng cả "Ngày đặt:" và "Ngày X/X/XXXX" (tiêu đề đơn hàng)
  - **Ngày giao**: nhận dạng "Ngày giao:", "Thời gian giao hàng:" + ngày cụ thể
- `map_columns(df)`: map tên cột tiếng Việt → tên chuẩn; có fallback starts-with cho cột như "Tên Mặt hàng [Thông số]"
- `_find_header_row(df_raw)`: tìm dòng header bằng cách đếm số keyword khớp per-cell (tránh chọn nhầm merged cell)
- `_find_table_header_row(table)`: tương tự cho PDF tables
- `classify_sheet(name)`: phân loại 2 bước — kiểm tra 25 ký tự đầu (ưu tiên), rồi toàn văn
- `_postprocess(records)`: lọc dòng trắng, dòng tổng/VAT/footer; tách kích thước ra cột riêng; gán `_sheet`

### `modules/excel_handler.py`
- `export_to_bytes(template_path, extracted_list)`: ghi tất cả dữ liệu vào template, trả về bytes
- `append_rows(ws, records, order_info)`: append dòng vào sheet với định dạng alternating row
- `_resolve_value(record, header, order_info)`: tìm giá trị phù hợp — khớp chính xác → order_info fallback → fuzzy match
- `_clean(v)`: chuyển sang string, trả về `""` cho nan/None/null/"-"/"n/a" (tránh "nan" xuất hiện trong file Excel)

---

## Luồng hoạt động chính (`app.py`)

```
Upload files (nhiều file, nhiều công ty)
    → extract_from_file() cho từng file
    → Hiển thị order_info (mã đơn, khách hàng, ngày)
    → st.data_editor: user xem và sửa dữ liệu, cột "Loại" có selectbox
    → Gom dữ liệu: order_info nhúng TRỰC TIẾP vào từng dòng
         (tránh trộn lẫn thông tin khi nhiều công ty cùng sheet)
    → export_to_bytes() ghi vào template
    → Download file kết quả
```

**Xử lý nhiều công ty:** mỗi dòng sản phẩm mang Mã đơn hàng / Khách hàng / Ngày đặt / Ngày giao của chính file đó — không dùng chung `order_info` theo sheet mà nhúng vào record tại bước gom nhóm (`grouped`).

---

## Claude API key

- Nhập trong sidebar của app (không lưu lại, nhập mỗi lần mở)
- Model hiện tại: `claude-opus-4-5` (vision + text)
- Prompt: bóc tách JSON `{order_info, products[]}` từ nội dung đơn hàng
- Nếu không có key: pdfplumber (PDF text) + pytesseract (ảnh)

---

## Vấn đề đã biết & cách giải quyết

| Vấn đề | Nguyên nhân | Giải pháp |
|---|---|---|
| Tên sản phẩm rỗng | `_find_header_row` chọn nhầm merged cell | Đếm keyword per-cell thay vì per-row |
| "Tên Mặt hàng [Thông số]" không map | `map_columns` chỉ exact match | Thêm starts-with fallback |
| "Thùng dùng chung" bị phân loại Hộp | Từ khoá "hộp" xuất hiện giữa tên | Phân loại 2 bước: ưu tiên 25 ký tự đầu |
| Dòng "Tổng cộng/VAT" bị đưa vào data | Không lọc footer rows | `_SUMMARY_ROW_RE` + filter SL không chứa số |
| Lỗi TextColumn vs INTEGER | Streamlit 1.57+ yêu cầu string | Convert toàn bộ cột df sang str trước `data_editor` |
| Nhiều công ty bị trộn order_info | `order_info_by_sheet` chỉ lưu file đầu | Nhúng order_info trực tiếp vào từng record khi gom nhóm |
| "nan" xuất hiện trong file Excel | `_resolve_value` không lọc NaN | `_clean()` trong excel_handler trả về "" cho nan/None |
| Khách hàng trích xuất sai (tên nhà sx) | Pattern "công ty" khớp trước "kính gửi" | Tách pattern, ưu tiên "kính gửi" trước |
| Ngày đặt rỗng với format "Ngày X/X/XXXX" | Pattern chỉ nhận dạng "Ngày đặt:" | Thêm pattern `ngày\s+\d{1,2}/\d` |
| NativeCommandError trong PowerShell | Streamlit ghi ra stderr | Không phải lỗi — app vẫn chạy bình thường |

---

## Mở rộng trong tương lai

- [ ] Thêm sheet "Tiến độ" để theo dõi trạng thái từng đơn hàng
- [ ] Lưu lịch sử đơn hàng vào database (SQLite)
- [ ] Gửi email tóm tắt đơn hàng tự động
- [ ] Đọc nhiều trang PDF scan bằng Claude Vision
- [ ] Map cột tự động thông minh hơn (Claude so sánh cột nguồn vs template)
- [ ] Thêm công đoạn: in, cán màng, bế, dán hộp
- [ ] Trích xuất Ngày giao từ tên file (pattern "ĐH NAME NUM - DD.MM.xlsx")
- [ ] Cho phép đổi tên run.bat thành tên tuỳ chọn (vd: Mo_App.bat)

---

## Bối cảnh người dùng

- Lĩnh vực: sản xuất bao bì / in ấn (nhãn, hộp, thùng)
- Nhận đơn hàng từ khách hàng dưới nhiều định dạng khác nhau
- Cần tổng hợp vào một file Excel kế hoạch sản xuất thống nhất
- Ưu tiên: dễ dùng, không cần kỹ thuật
