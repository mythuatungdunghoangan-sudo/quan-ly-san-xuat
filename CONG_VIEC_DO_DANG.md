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

### Bước 1 — Push các thay đổi hôm nay lên GitHub
Mở cmd trong thư mục `QuanLySanXuat`, chạy:
```
git add .
git commit -m "don dep thu muc, them file huong dan vao Phan loai tu dong"
git push
```

### Bước 2 — Kiểm tra Ky tai lieu trên GitHub
Vào `github.com/mythuatungdunghoangan-sudo/quan-ly-san-xuat`
Tìm thư mục `Ky tai lieu` — nếu thấy thì làm tiếp Bước 3.

### Bước 3 — Deploy app Ky tai lieu lên Streamlit Cloud
Vào `share.streamlit.io` → **Create app** → **Deploy a public app from GitHub**

| Trường | Giá trị |
|---|---|
| Repository | `mythuatungdunghoangan-sudo/quan-ly-san-xuat` |
| Branch | `master` |
| Main file path | `Ky tai lieu/ky_tai_lieu.py` |

Nhấn **Deploy** → chờ ~2 phút → lấy link.

### Bước 4 — Cập nhật link Ky tai lieu
Sau khi có link, cập nhật file `Ky tai lieu/LINK_ONLINE.txt` với link mới.
