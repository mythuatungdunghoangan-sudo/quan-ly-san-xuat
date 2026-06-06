# CLAUDE.md — Ký Tài Liệu

## Tổng quan

Ứng dụng Streamlit chèn chữ ký (ảnh PNG) vào tài liệu PDF, Excel (.xlsx), hoặc ảnh (JPG/PNG).  
Chạy độc lập, cổng **8502** (không xung đột với app phân loại đơn hàng ở 8501).

**Khởi động:** double-click `Ky tai lieu.bat`  
**Entry point:** `ky_tai_lieu.py`

---

## Cấu trúc thư mục

```
Ky tai lieu/
├── Ky tai lieu.bat        ← launcher (cổng 8502)
├── ky_tai_lieu.py         ← toàn bộ code ứng dụng
├── tu_khoa.txt            ← danh sách từ khóa tìm vị trí ký (người dùng tự chỉnh)
├── requirements.txt       ← thư viện: streamlit, Pillow, PyMuPDF, streamlit-drawable-canvas
└── chu_ky/
    └── Chu ky Hoang.png   ← ảnh chữ ký (PNG hoặc JPG, bất kỳ tên nào)
```

---

## Hai tab chính

### Tab 1 — Ký một file
- Upload 1 file (PDF/ảnh/Excel)
- Sidebar: quản lý chữ ký (upload ảnh hoặc vẽ tay)
- Chế độ **Tự động**: quét PDF tìm từ khóa → đặt chữ ký đúng vị trí + preview khung cam
- Chế độ **Thủ công**: chọn góc (Dưới phải / Dưới trái / Giữa dưới / ...)
- Ảnh JPG/PNG: slider X/Y tự do để kéo thả chữ ký
- Xuất 1 file → download

### Tab 2 — Ký hàng loạt
- Nguồn file: upload nhiều file **hoặc** nhập đường dẫn thư mục
- Hỗ trợ: PDF + Excel (.xlsx) + ảnh (JPG/PNG)
- Xử lý tự động → progress bar → bảng kết quả
- Download ZIP tất cả hoặc từng file riêng
- Preview: PDF (render trang), ảnh (hiện trực tiếp), Excel (hiện bảng dữ liệu)

---

## Luồng tự động tìm vị trí

### PDF
1. `scan_page_for_keywords(pdf_bytes, page_num)` — dùng `fitz.page.search_for()` tìm từ khóa
2. Kết quả sắp xếp theo **ưu tiên** (nhỏ = cao hơn), cùng ưu tiên → theo Y từ trên xuống
3. Ưu tiên ≤ `HA_PRIORITY_MAX` (= 4) mới được xem là "của Hoàng An"
4. Nếu không tìm thấy keyword Hoàng An → `sign_pdf_bottom_center()`: tìm Y cuối nội dung, đặt chữ ký căn giữa trang phía dưới

**place = "below"**: chữ ký đặt bên DƯỚI từ khóa (dùng cho nhãn: "Bên sản xuất", "XÁC NHẬN"…)  
**place = "above"**: chữ ký đặt bên TRÊN từ khóa (dùng cho tên in sẵn: "Nguyễn Minh Hoàng", "Giám đốc"…)

### Excel (.xlsx)
1. `find_excel_sig_position(excel_bytes)` — dùng openpyxl **read_only=False, data_only=True** (chỉ đọc, không save)
2. Tìm cell chứa keyword trong `_SIGN_KW_XL` (ưu tiên "CÔNG TY HOÀNG AN" trước)
3. Tìm vùng **merge** chứa cell đó → tính tổng chiều rộng (EMU)
4. colOff = `(tổng_chiều_rộng_merge - chiều_rộng_chữ_ký) / 2` → **căn giữa chữ ký** dưới ô đó
5. `sign_excel_file()` dùng **zipfile** sửa trực tiếp drawing1.xml → **không corrupt QR code / logo cũ**
6. Dùng `oneCellAnchor` + tính height theo tỉ lệ gốc → **không méo ảnh**

### Ảnh (JPG/PNG)
- Không có OCR → chỉ hỗ trợ vị trí thủ công
- Slider X% + Y% để kéo thả, preview cập nhật real-time

---

## File tu_khoa.txt — Cấu hình từ khóa

```
từ_khóa | below/above | tên hiển thị | ưu_tiên | khoảng_cách
```

| Cột | Ý nghĩa |
|-----|---------|
| `từ_khóa` | Text tìm trong PDF (khớp chính xác, phân biệt hoa/thường) |
| `below/above` | Đặt chữ ký bên dưới hoặc bên trên từ khóa |
| `tên hiển thị` | Tên hiển thị trong dropdown app |
| `ưu_tiên` | Số nguyên, **nhỏ hơn = ưu tiên cao hơn** khi có nhiều keyword |
| `khoảng_cách` | Điểm PDF, khoảng cách từ từ khóa đến chữ ký (mặc định: 4) |

**Bảng ưu tiên hiện tại:**

| Ưu tiên | Từ khóa | Ghi chú |
|---------|---------|---------|
| 1 | CÔNG TY HOÀNG AN | Cao nhất |
| 2 | XÁC NHẬN, Bên sản xuất, Nhà sản xuất | Vùng xác nhận HA |
| 3 | Xác nhận đơn đặt hàng, Bên đặt hàng, **Trưởng bộ phận** (offset=60) | Fallback khách hàng |
| 4 | Nguyễn Minh Hoàng | Tên người, thấp hơn tên công ty |
| 5 | Ký tên, (Ký, họ tên), Chữ ký, Đại diện | Chung |
| 6 | Tổng Giám đốc, Giám đốc, Trưởng phòng | Thấp nhất |

**Thêm từ khóa mới:** mở `tu_khoa.txt` bằng Notepad, thêm dòng cuối, lưu, khởi động lại app.

---

## Hàm quan trọng trong ky_tai_lieu.py

| Hàm | Tác dụng |
|-----|---------|
| `_load_keywords()` | Đọc tu_khoa.txt, trả về list dict `{kw, label, place, priority, v_offset}` |
| `scan_page_for_keywords(pdf_bytes, page_num)` | Tìm keyword trong 1 trang PDF, trả về list có priority + coords |
| `auto_find_keyword_in_doc(pdf_bytes)` | Quét toàn bộ PDF, trả về `(kw, place, v_offset)` tốt nhất (priority ≤ 4) |
| `find_content_bottom(page)` | Tìm Y cuối nội dung + X trung tâm (dùng khi không có keyword HA) |
| `sign_pdf_bottom_center(...)` | Ký ở vùng trống cuối trang, căn giữa (fallback) |
| `sign_pdf_auto(...)` | Tìm keyword trên mỗi trang và ký tại đó |
| `sign_pdf_manual(...)` | Ký theo vị trí góc cố định (thủ công) |
| `find_excel_sig_position(excel_bytes)` | Tìm keyword + vùng merge → tính colOff căn giữa |
| `sign_excel_file(excel_bytes, ...)` | Chèn ảnh vào xlsx bằng **zipfile** (không dùng openpyxl save) |
| `sign_image_file(...)` | Ghép chữ ký lên ảnh JPG/PNG bằng Pillow |
| `sign_pdf_auto` + `sign_pdf_bottom_center` | Đều trả về `(bytes, signed_pages)` |
| `process_one_file(...)` | Xử lý 1 file bất kỳ trong batch (PDF/ảnh/Excel), trả về dict kết quả |
| `create_zip(results)` | Đóng gói kết quả batch thành ZIP |
| `overlay_sig(...)` | Ghép PIL Image chữ ký lên ảnh nền, tùy chọn highlight khung cam |

---

## Thư viện và lý do chọn

| Thư viện | Dùng cho | Ghi chú |
|----------|---------|---------|
| `PyMuPDF` (fitz) | PDF: render trang, tìm text, chèn ảnh | Nhanh, không cần poppler |
| `openpyxl` | Excel: đọc nội dung, tìm merge cells | Chỉ dùng để ĐỌC, không save |
| `zipfile` (built-in) | Excel: sửa drawing XML trực tiếp | Tránh corrupt QR code / external links |
| `streamlit-drawable-canvas` | Vẽ chữ ký tay trong trình duyệt | Cần cài thêm |
| `Pillow` | Xử lý ảnh, overlay chữ ký | Đã có trong requirements chung |

---

## Vấn đề đã giải quyết & lý do

| Vấn đề | Giải pháp |
|--------|-----------|
| Excel báo lỗi "Found a problem" khi mở | Dùng zipfile sửa drawing XML trực tiếp thay vì openpyxl save (openpyxl rewrite làm hỏng QR code / external links) |
| Ảnh chữ ký méo trong Excel | Dùng `oneCellAnchor` + tính height = width × (h/w gốc) → giữ tỉ lệ |
| "Nguyễn Minh Hoàng" có ưu tiên hơn "Công ty Hoàng An" | Cột ưu tiên trong tu_khoa.txt: Công ty = 1, Tên người = 4 |
| Chữ ký lệch so với "CÔNG TY HOÀNG AN" | Đọc merged_cells → tính colOff = (merge_width - sig_width) / 2 |
| File I.FI không có keyword Hoàng An | Fallback: tìm Y cuối nội dung → ký giữa trang phía dưới |
| "Trưởng bộ phận" (I.FI) cần khoảng cách xa | Cột v_offset = 60 trong tu_khoa.txt |
| Ảnh RGBA méo khi chèn | `sig_img.convert("RGBA").save(buf, "PNG")` trước khi đưa vào zipfile |
| Không xem trước được Excel | Hiện bảng dữ liệu openpyxl read_only + thông báo row/keyword tìm thấy |

---

## Keyword quan trọng cho Excel (tách riêng với PDF)

```python
_SIGN_KW_XL = [
    "công ty hoàng an", "cong ty hoang an",
    "nguyễn minh hoàng", "nguyen minh hoang",
    "bên sản xuất", "nhà sản xuất", "xác nhận nhà sản xuất",
]
```

Các file Excel đơn hàng Hoàng An nhận được thường có:
- "CÔNG TY HOÀNG AN" tại cột F (col 5, 0-based), merge 3 cột (F–H)
- "NGUYỄN MINH HOÀNG" 5 dòng bên dưới
- Chữ ký đặt ngay dưới "CÔNG TY HOÀNG AN", căn giữa merge

---

## Hằng số quan trọng

```python
RENDER_DPI   = 130       # DPI render PDF preview, 1pt PDF = 130/72 px
PT_TO_PX     = 130/72    # hệ số chuyển PDF points → pixel
HA_PRIORITY_MAX = 4      # keyword priority <= 4 mới là "của Hoàng An"
                          # priority 5-6 là chung (Ký tên, Giám đốc...) → không dùng làm vị trí ký
```

---

## Cách thêm tính năng mới

### Thêm loại file mới
→ Sửa hàm `process_one_file()`: thêm `elif ext == ".docx": ...`

### Thêm keyword mới
→ Mở `tu_khoa.txt`, thêm dòng theo format, lưu, restart app. Không cần sửa code.

### Thay đổi logic ưu tiên
→ Sửa cột số 4 (ưu_tiên) trong `tu_khoa.txt`. Hoặc sửa hằng số `HA_PRIORITY_MAX` trong code nếu muốn thay đổi ngưỡng "từ khóa của Hoàng An".

### Thêm keyword Excel riêng
→ Sửa list `_SIGN_KW_XL` trong `ky_tai_lieu.py` (không dùng tu_khoa.txt vì Excel cần logic khác).

### Thay đổi kích thước chữ ký mặc định
→ Slider "Kích thước" trong UI. Cho Excel: sửa tham số `width_px=160` trong `sign_excel_file()`.

### Chỉnh vị trí chữ ký Excel (rowOff, colOff)
→ Trong `sign_excel_file()`, sửa `rowOff=57150` (khoảng cách dọc từ đầu row tính bằng EMU).
   1 EMU = 1/914400 inch. 57150 EMU ≈ 1.5mm xuống dưới từ đầu dòng.
