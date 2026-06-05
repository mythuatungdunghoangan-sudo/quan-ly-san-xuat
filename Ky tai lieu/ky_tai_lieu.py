"""
Ứng dụng ký tài liệu
Upload PDF hoặc ảnh → tự động dùng chữ ký đã lưu → xuất file đã ký
"""

import io
import numpy as np
import streamlit as st
from PIL import Image
from pathlib import Path

st.set_page_config(
    page_title="Ký tài liệu",
    page_icon="✍️",
    layout="wide",
)

st.title("✍️ Ký tài liệu")

# ─── THƯ MỤC CHỮ KÝ ──────────────────────────────────────────────────────────
CHU_KY_DIR = Path("chu_ky")
CHU_KY_DIR.mkdir(exist_ok=True)
CHU_KY_SAVE_PATH = CHU_KY_DIR / "chu_ky.png"  # nơi lưu khi dùng tính năng vẽ/upload trong app


def _find_chu_ky() -> Image.Image | None:
    """Tìm file ảnh đầu tiên trong thư mục chu_ky/ (PNG, JPG — bất kỳ tên nào)"""
    patterns = ["*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"]
    candidates = []
    for pat in patterns:
        candidates.extend(CHU_KY_DIR.glob(pat))
    for f in sorted(set(candidates)):
        try:
            img = Image.open(f).convert("RGBA")
            return img
        except Exception:
            continue
    return None


# ─── SESSION STATE ────────────────────────────────────────────────────────────
if "sig_active" not in st.session_state:
    st.session_state.sig_active = _find_chu_ky()

if "canvas_key" not in st.session_state:
    st.session_state.canvas_key = 0

if "show_change_sig" not in st.session_state:
    st.session_state.show_change_sig = False

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def remove_white_bg(img: Image.Image, threshold: int = 230) -> Image.Image:
    img = img.convert("RGBA")
    data = np.array(img)
    mask = (data[:, :, 0] > threshold) & (data[:, :, 1] > threshold) & (data[:, :, 2] > threshold)
    data[mask, 3] = 0
    return Image.fromarray(data, "RGBA")


def render_pdf_page(pdf_bytes: bytes, page_num: int, dpi: int = 120) -> Image.Image:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def _sig_pos(bw, bh, sw, sh, position, margin):
    m = margin
    return {
        "Trên trái":   (m, m),
        "Trên phải":  (bw - sw - m, m),
        "Dưới trái":  (m, bh - sh - m),
        "Dưới phải": (bw - sw - m, bh - sh - m),
        "Giữa trang": ((bw - sw) // 2, (bh - sh) // 2),
        "Giữa dưới": ((bw - sw) // 2, bh - sh - m),
    }.get(position, (bw - sw - m, bh - sh - m))


def overlay_sig_image(base: Image.Image, sig: Image.Image, position: str,
                      width_pct: float, margin: int) -> Image.Image:
    bw, bh = base.size
    sw = max(40, int(bw * width_pct / 100))
    sh = int(sig.height * sw / sig.width)
    sig_r = sig.resize((sw, sh), Image.LANCZOS).convert("RGBA")
    x, y = _sig_pos(bw, bh, sw, sh, position, margin)
    result = base.convert("RGBA")
    result.paste(sig_r, (int(x), int(y)), mask=sig_r)
    return result.convert("RGB")


def sign_pdf(pdf_bytes: bytes, sig_img: Image.Image, pages: list,
             position: str, width_pct: float, margin_pt: float) -> bytes:
    import fitz
    sig_buf = io.BytesIO()
    sig_img.save(sig_buf, "PNG")
    sig_png = sig_buf.getvalue()
    ar = sig_img.width / sig_img.height

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for i, page in enumerate(doc):
        if (i + 1) not in pages:
            continue
        pw, ph = page.rect.width, page.rect.height
        sw = pw * width_pct / 100
        sh = sw / ar
        x, y = _sig_pos(pw, ph, sw, sh, position, margin_pt)
        page.insert_image(fitz.Rect(x, y, x + sw, y + sh), stream=sig_png)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def save_chu_ky(img: Image.Image):
    img.save(CHU_KY_SAVE_PATH, "PNG")
    st.session_state.sig_active = img


# ─── PHẦN QUẢN LÝ CHỮ KÝ ─────────────────────────────────────────────────────

with st.sidebar:
    st.header("✍️ Chữ ký")

    if st.session_state.sig_active is not None and not st.session_state.show_change_sig:
        # Đã có chữ ký lưu sẵn
        st.success("Đang dùng chữ ký đã lưu")
        st.image(st.session_state.sig_active, use_container_width=True)
        if st.button("🔄 Đổi chữ ký", use_container_width=True):
            st.session_state.show_change_sig = True
            st.rerun()

    else:
        # Chưa có hoặc đang đổi chữ ký
        if st.session_state.show_change_sig:
            st.info("Chọn chữ ký mới:")

        tab_upload, tab_draw = st.tabs(["📤 Upload ảnh", "🖊 Vẽ tay"])

        new_sig = None

        with tab_upload:
            sig_file = st.file_uploader(
                "Chọn ảnh chữ ký (PNG/JPG)",
                type=["png", "jpg", "jpeg"],
                key="sig_upload_file",
            )
            if sig_file:
                loaded = Image.open(sig_file)
                remove_bg = st.checkbox("Xóa nền trắng", value=True)
                new_sig = remove_white_bg(loaded) if remove_bg else loaded.convert("RGBA")
                st.image(new_sig, use_container_width=True, caption="Xem trước")

        with tab_draw:
            try:
                from streamlit_drawable_canvas import st_canvas
            except ImportError:
                st.error("Thiếu `streamlit-drawable-canvas`. Chạy lại `cai_dat.bat`.")
                st_canvas = None

            if st_canvas:
                c1, c2 = st.columns([3, 1])
                with c2:
                    if st.button("Xóa", use_container_width=True):
                        st.session_state.canvas_key += 1
                        st.rerun()
                canvas_res = st_canvas(
                    stroke_width=3,
                    stroke_color="#111111",
                    background_color="#f5f5f5",
                    height=150,
                    drawing_mode="freedraw",
                    key=f"canvas_{st.session_state.canvas_key}",
                    display_toolbar=False,
                )
                if canvas_res.image_data is not None:
                    arr = canvas_res.image_data.astype(np.uint8)
                    if (arr[:, :, :3].min(axis=2) < 180).any():
                        rgb = Image.fromarray(arr[:, :, :3], "RGB")
                        new_sig = remove_white_bg(rgb, threshold=200)

        # Nút lưu chữ ký
        if new_sig is not None:
            st.divider()
            if st.button("💾 Lưu & dùng chữ ký này", type="primary", use_container_width=True):
                save_chu_ky(new_sig)
                st.session_state.show_change_sig = False
                st.success("Đã lưu! Sẽ tự dùng cho lần sau.")
                st.rerun()

        if st.session_state.show_change_sig:
            if st.button("↩️ Giữ chữ ký cũ", use_container_width=True):
                st.session_state.show_change_sig = False
                st.rerun()

    st.divider()
    st.header("⚙️ Cài đặt")
    position = st.selectbox(
        "Vị trí",
        ["Dưới phải", "Dưới trái", "Giữa dưới", "Trên phải", "Trên trái", "Giữa trang"],
    )
    width_pct = st.slider("Kích thước (% chiều rộng trang)", 5, 60, 22)
    margin_val = st.slider("Khoảng cách lề", 5, 150, 35)

# ─── NỘI DUNG CHÍNH ───────────────────────────────────────────────────────────

if st.session_state.sig_active is None:
    st.info("Chưa có chữ ký — upload hoặc vẽ chữ ký trong thanh bên trái rồi lưu lại.")
    st.stop()

# Upload tài liệu
uploaded_doc = st.file_uploader(
    "📄 Tải lên tài liệu cần ký (PDF hoặc ảnh)",
    type=["pdf", "png", "jpg", "jpeg"],
)

if not uploaded_doc:
    st.info("Tải lên file để bắt đầu. Chữ ký sẽ được chèn tự động.")
    st.stop()

doc_bytes = uploaded_doc.read()
is_pdf = uploaded_doc.name.lower().endswith(".pdf")

if is_pdf:
    try:
        import fitz
        _tmp = fitz.open(stream=doc_bytes, filetype="pdf")
        total_pages = _tmp.page_count
        _tmp.close()
    except Exception as e:
        st.error(f"Không đọc được PDF: {e}")
        st.stop()

# ─── LAYOUT XEM TRƯỚC + CHỌN TRANG ──────────────────────────────────────────

col_left, col_right = st.columns([1, 2], gap="large")

with col_left:
    if is_pdf:
        st.subheader("📋 Chọn trang ký")
        apply_all = st.checkbox(f"Ký tất cả {total_pages} trang", value=False)
        if apply_all:
            selected_pages = list(range(1, total_pages + 1))
            st.caption(f"Sẽ ký toàn bộ {total_pages} trang.")
        else:
            selected_pages = st.multiselect(
                "Chọn trang",
                list(range(1, total_pages + 1)),
                default=[total_pages],
                format_func=lambda p: f"Trang {p}",
            )

        st.divider()
        if is_pdf:
            preview_page_num = st.selectbox(
                "Trang xem trước",
                list(range(1, total_pages + 1)),
                index=(selected_pages[-1] - 1) if selected_pages else 0,
                format_func=lambda p: f"Trang {p}",
            )
    else:
        selected_pages = []
        preview_page_num = 1

    st.divider()
    # Xuất file
    can_export = not (is_pdf and not selected_pages)
    if not can_export:
        st.warning("Chưa chọn trang nào để ký.")

    if can_export and st.button("🖊 Xuất file đã ký", type="primary", use_container_width=True):
        stem = Path(uploaded_doc.name).stem
        with st.spinner("Đang xử lý..."):
            try:
                if is_pdf:
                    out_bytes = sign_pdf(
                        doc_bytes, st.session_state.sig_active, selected_pages,
                        position, width_pct, float(margin_val),
                    )
                    st.download_button(
                        "⬇️ Tải PDF đã ký",
                        data=out_bytes,
                        file_name=f"da_ky_{stem}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                    st.success(f"Đã ký {len(selected_pages)} trang.")
                else:
                    result = overlay_sig_image(
                        Image.open(io.BytesIO(doc_bytes)),
                        st.session_state.sig_active, position, width_pct, margin_val,
                    )
                    buf = io.BytesIO()
                    result.save(buf, "PNG")
                    st.download_button(
                        "⬇️ Tải ảnh đã ký",
                        data=buf.getvalue(),
                        file_name=f"da_ky_{stem}.png",
                        mime="image/png",
                        use_container_width=True,
                    )
                    st.success("Xong. Nhấn nút tải về.")
            except Exception as e:
                st.error(f"Lỗi: {e}")

with col_right:
    st.subheader("👁 Xem trước")
    try:
        if is_pdf:
            base_img = render_pdf_page(doc_bytes, preview_page_num - 1)
            will_sign = preview_page_num in selected_pages
        else:
            base_img = Image.open(io.BytesIO(doc_bytes)).convert("RGB")
            will_sign = True

        if will_sign:
            preview_img = overlay_sig_image(
                base_img, st.session_state.sig_active, position, width_pct, margin_val
            )
            st.image(preview_img, use_container_width=True)
        else:
            st.image(base_img, use_container_width=True)
            st.caption("⚠️ Trang này chưa được chọn ký.")
    except Exception as e:
        st.error(f"Lỗi xem trước: {e}")
