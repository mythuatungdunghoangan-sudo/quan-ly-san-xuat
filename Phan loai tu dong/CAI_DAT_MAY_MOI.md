# Hướng dẫn cài đặt từ đầu — Máy tính mới

Hướng dẫn này giúp bạn thiết lập toàn bộ môi trường để **chạy app** và **tiếp tục phát triển** trên máy tính mới.

---

## Phần 1 — Chỉ muốn CHẠY app (không cần lập trình)

### Cách A — Dùng cloud (đơn giản nhất, không cần cài gì)
Mở trình duyệt, vào:
```
quan-ly-san-xuat-4wnwfzg9zujxcjnfmptdq4.streamlit.app
```
Xong. Không cần cài đặt gì cả.

---

### Cách B — Chạy offline trên máy

**Bước 1:** Tải thư mục app về máy (chọn 1 trong 2 cách):

- **Cách nhanh:** Copy thư mục `QuanLySanXuat` từ máy cũ qua USB / OneDrive
- **Cách từ GitHub:** Tải file ZIP tại:
  `github.com/mythuatungdunghoangan-sudo/quan-ly-san-xuat` → nút **Code** → **Download ZIP** → giải nén

**Bước 2:** Vào thư mục `Phan loai tu dong`, double-click **`cai_dat.bat`**
- Tự tải và cài Python nếu chưa có (cần internet, ~27MB)
- Tự cài toàn bộ thư viện
- Chờ 2–5 phút

**Bước 3:** Double-click **`Phan loai tu dong.bat`** để mở app

> Từ lần sau chỉ cần **`Phan loai tu dong.bat`**, không cần chạy lại `cai_dat.bat`.

---

## Phần 2 — Muốn LẬP TRÌNH / chỉnh sửa code với Claude Code

Cần cài 4 thứ theo thứ tự sau.

---

### Bước 1 — Cài Git

1. Vào: `git-scm.com/download/win`
2. Tải bản **64-bit** → chạy installer
3. Giữ nguyên tất cả tùy chọn mặc định, bấm Next đến hết
4. Kiểm tra: mở PowerShell, gõ `git --version`
   - Thấy `git version 2.x.x` → thành công

---

### Bước 2 — Cài Python

1. Vào: `python.org/downloads`
2. Tải bản mới nhất (3.11 trở lên)
3. Chạy installer — **QUAN TRỌNG:** tick vào **"Add Python to PATH"** trước khi bấm Install
4. Kiểm tra: mở PowerShell, gõ `python --version`
   - Thấy `Python 3.x.x` → thành công

> Nếu đã chạy `cai_dat.bat` ở Phần 1 thì Python đã có, bỏ qua bước này.

---

### Bước 3 — Cài Node.js (cần cho Claude Code)

1. Vào: `nodejs.org`
2. Tải bản **LTS** (bản ổn định)
3. Chạy installer, giữ nguyên tùy chọn mặc định
4. Kiểm tra: mở PowerShell, gõ `node --version`
   - Thấy `v22.x.x` hoặc cao hơn → thành công

---

### Bước 4 — Cài Claude Code

Mở PowerShell, chạy lệnh:
```
npm install -g @anthropic-ai/claude-code
```

Kiểm tra:
```
claude --version
```
Thấy `2.x.x (Claude Code)` → thành công.

---

### Bước 5 — Tải code về từ GitHub

Mở PowerShell, chọn thư mục muốn lưu (ví dụ `D:\OneDrive\Claude`), rồi chạy:

```
cd "D:\OneDrive\Claude"
git clone https://github.com/mythuatungdunghoangan-sudo/quan-ly-san-xuat.git QuanLySanXuat
```

Thư mục `QuanLySanXuat` sẽ được tạo với toàn bộ code mới nhất.

---

### Bước 6 — Cài thư viện Python

```
cd "D:\OneDrive\Claude\QuanLySanXuat\Phan loai tu dong"
pip install -r requirements.txt
```

Hoặc double-click `cai_dat.bat` như Phần 1.

---

### Bước 7 — Mở Claude Code và bắt đầu làm việc

Cách 1 — Double-click file `MoClaudeCode_QuanLySanXuat.bat` (ở thư mục gốc `QuanLySanXuat`)

Cách 2 — Mở PowerShell trong thư mục `QuanLySanXuat`, gõ:
```
claude
```

Lần đầu tiên Claude Code sẽ yêu cầu đăng nhập tài khoản Anthropic — làm theo hướng dẫn trên màn hình.

---

## Tóm tắt nhanh

```
Chỉ chạy app    →  Vào link cloud  HOẶC  cai_dat.bat → Phan loai tu dong.bat
Lập trình       →  Git → Python → Node.js → Claude Code → git clone → pip install
```

---

## Kiểm tra nhanh sau khi cài xong

Mở PowerShell và chạy từng lệnh, mỗi lệnh phải hiện số phiên bản:

```
git --version        → git version 2.x.x
python --version     → Python 3.x.x
node --version       → v22.x.x (hoặc cao hơn)
claude --version     → 2.x.x (Claude Code)
```

Nếu lệnh nào báo lỗi "not recognized" → cài lại bước tương ứng.
