# Ghi chú công việc — 05/06/2026

---

## ĐÃ LÀM XONG

### 1. Xác định lại cấu trúc dự án
- Dự án có **2 app** (không phải 3):
  - `Phan loai tu dong/` — bóc tách & phân loại đơn hàng, port 8501
  - `Ky tai lieu/` — chèn chữ ký vào PDF/Excel/ảnh, port 8502
- App 1 và App 3 là một — đều là `Phan loai tu dong/app.py`

### 2. Dọn dẹp thư mục gốc QuanLySanXuat
- Chuyển vào `Phan loai tu dong/`: HUONG_DAN.md, CAI_DAT_MAY_MOI.md, Huong dan su dung app.txt
- Nội dung các file đã cập nhật đúng (đường dẫn, số sheet, tên bat file, model AI)
- Xóa khỏi root: 3 file hướng dẫn cũ + thư mục `template/`
- Tạo mới trong `Phan loai tu dong/`: LINK_ONLINE.txt (ghi link cloud)

### 3. Cập nhật CLAUDE.md
- Sửa cấu trúc thư mục đúng thực tế (2 app trong subfolder)
- Cập nhật bảng triển khai & truy cập
- Cập nhật cách chạy ứng dụng

### 4. Cài Git
- Git chưa có trên máy → đã cài xong
- Kiểm tra git status: branch ahead 1 commit, có thay đổi chưa staged

### 5. Link app Phân loại đơn hàng (đã có)
```
https://quan-ly-san-xuat-4wnwfzg9zujxcjnfmptdq4.streamlit.app
```

---

## CÒN LÀM TIẾP

### Bước 1 — Push các thay đổi hôm nay lên GitHub ✅ XONG (06/06/2026)

### Bước 2 — Kiểm tra Ky tai lieu trên GitHub ✅ XONG

### Bước 3 — Deploy app Ky tai lieu lên Streamlit Cloud ✅ XONG (06/06/2026)
- Link: `ky-tai-lieu-hoang-an.streamlit.app`
- Main file dùng: `ky_tai_lieu_app.py` (wrapper ở root, KHÔNG dùng trực tiếp
  `Ky tai lieu/ky_tai_lieu.py` vì tên thư mục có dấu cách gây lỗi requirements)

### Bước 4 — Cập nhật link Ky tai lieu ✅ XONG
- `Ky tai lieu/LINK_ONLINE.txt` đã có link
- `CLAUDE.md` đã cập nhật

---

# Ghi chú công việc — 06/06/2026

---

## ĐÃ LÀM XONG

### 1. Deploy app Ký tài liệu lên Cloud
- Link: `https://ky-tai-lieu-hoang-an.streamlit.app`
- Các lỗi đã sửa:
  - Path `CHU_KY_DIR`, `TU_KHOA_FILE` sai trên Cloud → đổi dùng `Path(__file__).parent`
  - File chữ ký không lên GitHub (`.gitignore` chặn `*.png`) → thêm exception
  - Tên thư mục "Ky tai lieu" có dấu cách → Cloud đọc nhầm requirements
    → Tạo `ky_tai_lieu_app.py` wrapper ở root (giống `app.py`)
  - Thiếu `pandas` → thêm vào requirements
  - App crash React DOM do `streamlit-drawable-canvas` → đã fix bằng path

### 2. Thêm tính năng ký file Word (.docx)
- Tự tìm keyword (CÔNG TY HOÀNG AN, Nguyễn Minh Hoàng...) rồi chèn chữ ký ngay dưới
- Fallback: ký cuối tài liệu nếu không tìm thấy keyword
- Hỗ trợ Tab 1 (ký 1 file) và Tab 2 (ký hàng loạt)
- Thêm `python-docx` vào requirements

---

## CÒN LÀM TIẾP

### Sửa warning `use_container_width` (Streamlit 1.58)
- Streamlit báo deprecated, cần đổi thành `width='stretch'`
- Áp dụng cho cả 2 app (Phân loại và Ký tài liệu)
- Ưu tiên thấp — chỉ là warning, chưa crash app

### Xem trước Word sau khi ký
- Hiện tại không có preview cho file Word
- Hướng xử lý sau: convert Word → PDF bằng LibreOffice rồi render
