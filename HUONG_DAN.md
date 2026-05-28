# Hướng dẫn sử dụng — Quản Lý Sản Xuất

## Giới thiệu

Ứng dụng web giúp **bóc tách đơn hàng tự động** từ file PDF, ảnh chụp, hoặc Excel của khách hàng, rồi tổng hợp vào một file kế hoạch sản xuất Excel thống nhất.

**Hỗ trợ:** Nhãn · Hộp · Thùng/Carton · Túi màng

---

## Truy cập ứng dụng

| Cách | Địa chỉ | Khi nào dùng |
|---|---|---|
| **Cloud (khuyến nghị)** | `quan-ly-san-xuat-4wnwfzg9zujxcjnfmptdq4.streamlit.app` | Dùng mọi nơi, không cần cài đặt |
| **Máy tính cá nhân** | Chạy `run.bat` → mở `http://localhost:8501` | Dùng offline, không cần internet |

---

## Cài đặt lần đầu (máy tính mới)

> Chỉ cần làm **một lần duy nhất** trên mỗi máy.

1. Copy toàn bộ thư mục `QuanLySanXuat` vào máy
2. Đảm bảo máy có kết nối internet
3. Double-click **`cai_dat.bat`**
   - Tự động tải và cài Python nếu chưa có
   - Tự động cài toàn bộ thư viện cần thiết
   - Thời gian: 2–5 phút
4. Sau khi xong → double-click **`run.bat`** để mở app

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
- Đổi cột **"Loại"** (Nhãn / Hộp / Thùng / Túi màng) nếu phân loại chưa đúng

### Bước 5 — Xuất file kế hoạch

Bấm **"Tổng hợp và tải về Excel"** → tải file kế hoạch sản xuất về máy.

File Excel có 5 sheet: **Nhãn · Hộp · Thùng · Túi màng · Tổng hợp** — dữ liệu tự động phân vào đúng sheet.

---

## Cập nhật app sau khi chỉnh sửa code

Khi bạn (hoặc Claude Code) chỉnh sửa code trong thư mục `QuanLySanXuat`, cần đẩy lên GitHub để cloud cập nhật.

### Cách nhanh nhất — dùng Claude Code

Mở Claude Code trong thư mục `QuanLySanXuat`, gõ:

> "đẩy code lên GitHub"

Claude sẽ tự chạy lệnh git cho bạn.

### Tự chạy tay — mở PowerShell trong thư mục QuanLySanXuat

```
git add .
git commit -m "mô tả thay đổi"
git push
```

**Sau khi push xong:** Streamlit Cloud tự động nhận code mới và khởi động lại trong ~1–2 phút. Không cần làm gì thêm.

### Kiểm tra trạng thái deploy

Vào **share.streamlit.io** → chọn app → xem log nếu app báo lỗi sau khi cập nhật.

---

## Xử lý sự cố thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| App cloud báo lỗi sau update | Vào share.streamlit.io → xem log lỗi → gửi cho Claude Code sửa |
| `run.bat` không mở được | Chạy lại `cai_dat.bat` một lần nữa |
| Bóc tách sai tên sản phẩm | Sửa trực tiếp trong bảng trước khi xuất |
| PDF scan không đọc được | Cần nhập Claude API key vào sidebar |
| "nan" xuất hiện trong file Excel | Lỗi đã được fix — cập nhật code mới nhất từ GitHub |

---

## Cấu trúc thư mục

```
QuanLySanXuat/
├── app.py                  ← Giao diện chính
├── run.bat                 ← Mở app trên máy tính
├── cai_dat.bat             ← Cài đặt lần đầu (máy mới)
├── requirements.txt        ← Danh sách thư viện Python
├── modules/
│   ├── extractor.py        ← Bóc tách PDF / ảnh / Excel
│   ├── excel_handler.py    ← Ghi dữ liệu vào template
│   └── template_creator.py ← Tạo file Excel mẫu
├── template/               ← File template (tự tạo khi chạy)
├── .streamlit/
│   └── config.toml         ← Cấu hình giao diện Streamlit
└── HUONG_DAN.md            ← File này
```

---

## Thông tin kỹ thuật

- **Python** 3.11+ · **Streamlit** 1.57
- **AI:** Anthropic Claude (claude-opus-4-5) — Vision + Text
- **GitHub:** github.com/mythuatungdunghoangan-sudo/quan-ly-san-xuat
- **Cloud URL:** quan-ly-san-xuat-4wnwfzg9zujxcjnfmptdq4.streamlit.app
