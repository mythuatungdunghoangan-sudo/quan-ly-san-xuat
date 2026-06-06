# Hướng dẫn sử dụng — Phân Loại Đơn Hàng

## Giới thiệu

Ứng dụng web giúp **bóc tách đơn hàng tự động** từ file PDF, ảnh chụp, hoặc Excel của khách hàng, rồi tổng hợp vào một file kế hoạch sản xuất Excel thống nhất.

**Hỗ trợ:** Nhãn C115 · Nhãn Decan · Hộp · Thùng carton · Túi màng

---

## Truy cập ứng dụng

| Cách | Địa chỉ | Khi nào dùng |
|---|---|---|
| **Cloud (khuyến nghị)** | `quan-ly-san-xuat-4wnwfzg9zujxcjnfmptdq4.streamlit.app` | Dùng mọi nơi, không cần cài đặt |
| **Máy tính cá nhân** | Double-click `Phan loai tu dong.bat` → `http://localhost:8501` | Dùng offline |

---

## Cài đặt lần đầu (máy tính mới)

> Chỉ cần làm **một lần duy nhất** trên mỗi máy.

1. Copy toàn bộ thư mục `Phan loai tu dong` vào máy
2. Đảm bảo máy có kết nối internet
3. Double-click **`cai_dat.bat`**
   - Tự động tải và cài Python nếu chưa có
   - Tự động cài toàn bộ thư viện cần thiết
   - Thời gian: 2–5 phút
4. Sau khi xong → double-click **`Phan loai tu dong.bat`** để mở app

---

## Cách sử dụng hàng ngày

### Bước 1 — Nhập Claude API Key (tùy chọn nhưng nên có)

Ở sidebar trái, nhập **Anthropic API Key** (dạng `sk-ant-...`).

- **Không có key:** Chỉ đọc được PDF có text và Excel. PDF scan/ảnh chụp sẽ báo lỗi.
- **Có key:** Đọc được mọi định dạng kể cả ảnh chụp tay, PDF scan mờ.

> Key không được lưu lại — mỗi lần mở app phải nhập lại.

### Bước 2 — Tạo file template (lần đầu)

Bấm **"Tạo / tải template mặc định"** ở sidebar để tải file Excel mẫu về xem cấu trúc.

### Bước 3 — Upload file đơn hàng

Bấm **Upload** → chọn file đơn hàng từ khách hàng:

| Định dạng | Yêu cầu |
|---|---|
| Excel (.xlsx, .xls) | Luôn đọc được, không cần API key |
| PDF có text | Đọc được không cần key |
| PDF scan / ảnh (JPG, PNG...) | **Cần Claude API key** |

Có thể upload **nhiều file cùng lúc** (nhiều công ty khác nhau).

### Bước 4 — Kiểm tra và chỉnh sửa

App hiển thị bảng dữ liệu đã bóc tách — bạn có thể:
- Sửa trực tiếp ô nào sai
- Đổi cột **"Loại"** nếu phân loại chưa đúng

### Bước 5 — Xuất file kế hoạch

Bấm **"Tổng hợp và tải về Excel"** → tải file kế hoạch sản xuất về máy.

File Excel có 6 sheet: **Nhãn C115 · Nhãn Decan · Hộp · Thùng carton · Túi màng · Tổng hợp**

---

## Cập nhật app sau khi chỉnh sửa code

```
git add .
git commit -m "mô tả thay đổi"
git push
```

Sau khi push, Streamlit Cloud tự cập nhật trong ~1–2 phút.

---

## Xử lý sự cố thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| App cloud báo lỗi sau update | Vào share.streamlit.io → xem log lỗi |
| `Phan loai tu dong.bat` không mở được | Chạy lại `cai_dat.bat` một lần nữa |
| Bóc tách sai tên sản phẩm | Sửa trực tiếp trong bảng trước khi xuất |
| PDF scan không đọc được | Cần nhập Claude API key vào sidebar |

---

## Cấu trúc thư mục

```
Phan loai tu dong/
├── app.py                  ← Giao diện chính
├── Phan loai tu dong.bat   ← Mở app trên máy tính
├── cai_dat.bat             ← Cài đặt lần đầu (máy mới)
├── requirements.txt        ← Danh sách thư viện Python
├── modules/
│   ├── extractor.py        ← Bóc tách PDF / ảnh / Excel
│   ├── excel_handler.py    ← Ghi dữ liệu vào template
│   └── template_creator.py ← Tạo file Excel mẫu
├── template/               ← File template (tự tạo khi chạy)
└── .streamlit/config.toml  ← Cấu hình giao diện Streamlit
```

---

## Thông tin kỹ thuật

- **Python** 3.11+ · **Streamlit** 1.57
- **AI:** Anthropic Claude (claude-sonnet-4-6) — Vision + Text
- **GitHub:** github.com/mythuatungdunghoangan-sudo/quan-ly-san-xuat
- **Cloud URL:** quan-ly-san-xuat-4wnwfzg9zujxcjnfmptdq4.streamlit.app
