"""
Ứng dụng tổng hợp đơn hàng sản xuất
Upload PDF / ảnh / Excel → bóc tách → phân loại tự động → xuất kế hoạch sản xuất
"""

import streamlit as st
import pandas as pd
from collections import defaultdict
from pathlib import Path
import tempfile, os

st.set_page_config(
    page_title="Kế hoạch sản xuất",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .stExpander > summary { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

from modules.template_creator import create_template, TEMPLATE_COLUMNS
from modules.extractor import extract_from_file, SHEET_NAMES_ALL
from modules.excel_handler import export_to_bytes

TEMPLATE_PATH = Path("template/ke_hoach_san_xuat.xlsx")

# Màu badge mỗi loại
_SHEET_BADGE = {
    "Nhãn C115":    "🔵",
    "Nhãn Decan":   "🩵",
    "Hộp":          "🟢",
    "Thùng carton": "🟠",
    "Túi màng":     "🔴",
    "Tổng hợp":     "🟣",
}


def ensure_template() -> Path:
    needs_create = not TEMPLATE_PATH.exists()
    if not needs_create:
        # Tạo lại nếu template cũ thiếu sheet mới
        try:
            import openpyxl
            wb = openpyxl.load_workbook(TEMPLATE_PATH)
            if not all(s in wb.sheetnames for s in TEMPLATE_COLUMNS):
                needs_create = True
        except Exception:
            needs_create = True
    if needs_create:
        create_template(TEMPLATE_PATH)
    return TEMPLATE_PATH


# ─── SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📦 Quản lý sản xuất")
    st.caption("v1.1 — phân loại tự động theo dòng")
    st.divider()

    st.subheader("🤖 Claude AI (tùy chọn)")
    use_claude = st.toggle(
        "Bật Claude AI",
        value=False,
        help="Tắt để dùng pdfplumber + OCR miễn phí, không cần key.",
    )
    if use_claude:
        claude_key = st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-...",
            help="Gắn key để đọc PDF scan và ảnh thông minh hơn.",
        )
        if claude_key:
            st.success("✅ Claude AI đang bật")
        else:
            st.warning("⚠️ Chưa nhập API key")
    else:
        claude_key = ""
        st.info("Claude AI đang tắt — dùng pdfplumber + OCR")

    st.divider()

    st.subheader("📋 File template")
    if st.button("🔄 Tạo / tải template mặc định", width="stretch"):
        tp = ensure_template()
        with open(tp, "rb") as f:
            st.download_button(
                "💾 Download template Excel",
                f.read(),
                file_name="ke_hoach_san_xuat_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

    custom_template = st.file_uploader(
        "Hoặc upload template của bạn",
        type=["xlsx"],
        help="Cần có sheet: Nhãn, Hộp, Thùng, Túi màng, Tổng hợp",
    )

    st.divider()
    with st.expander("📖 Hướng dẫn"):
        st.markdown("""
**Phân loại tự động:**
- 🔵 **Nhãn C115** — nhãn, label, nhãn giấy, C115
- 🩵 **Nhãn Decan** — Tem, Decan, Bế, sticker
- 🟢 **Hộp** — tất cả loại hộp (carton, bồi, Duplex...)
- 🟠 **Thùng carton** — tất cả loại thùng
- 🔴 **Túi màng** — túi, màng PE/PP, ziplock
- 🟣 **Tổng hợp** — tổng hợp tất cả

**Bạn có thể sửa cột "Loại" trước khi xuất.**
""")


# ─── MAIN ───────────────────────────────────────────────────────────────────
st.header("📂 Upload file đơn hàng")

uploaded_files = st.file_uploader(
    "Kéo thả hoặc chọn file",
    type=["pdf", "png", "jpg", "jpeg", "bmp", "tiff", "webp", "xlsx", "xls"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if not uploaded_files:
    st.markdown("""
    <div style="text-align:center; padding: 3rem; color: #888;
                border: 2px dashed #ddd; border-radius: 12px;">
        <h3>📤 Chưa có file nào</h3>
        <p>Hỗ trợ: <strong>PDF</strong> · <strong>PNG / JPG</strong> · <strong>Excel</strong></p>
        <p style="font-size:0.9em">App tự động phân loại từng dòng → Nhãn / Hộp / Thùng / Túi màng</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ─── XỬ LÝ TỪNG FILE ────────────────────────────────────────────────────────
st.divider()
st.subheader("📊 Dữ liệu bóc tách & phân loại")

# all_items: list of {file, df (với cột _sheet), order_info}
all_items = []

for uploaded_file in uploaded_files:
    with st.expander(f"📄 {uploaded_file.name}", expanded=True):
        with st.spinner(f"Đang xử lý **{uploaded_file.name}**…"):
            result = extract_from_file(
                uploaded_file,
                claude_api_key=claude_key if claude_key else None,
            )

        if not result["success"]:
            st.error(f"❌ {result['error']}")
            continue
        if result["warning"]:
            st.warning(result["warning"])

        info = result.get("order_info") or {}
        if any(info.values()):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Mã đơn hàng", info.get("order_id") or "—")
            c2.metric("Khách hàng",  info.get("customer") or "—")
            c3.metric("Ngày đặt",    info.get("order_date") or "—")
            c4.metric("Ngày giao",   info.get("delivery_date") or "—")

        data = result["data"]
        if not data:
            st.warning("Không tìm thấy dữ liệu dạng bảng trong file.")
            continue

        df = pd.DataFrame(data)

        # Chuyển toàn bộ cột sang string (trừ _sheet/Loại đã là string)
        # Bắt buộc để tránh lỗi TextColumn vs INTEGER trong Streamlit 1.57+
        for col in df.columns:
            if col not in ("_sheet", "Loại"):
                df[col] = df[col].astype(str).replace({"nan": "", "None": ""})

        # Đổi tên _sheet → "Loại" để hiển thị thân thiện
        if "_sheet" in df.columns:
            df = df.rename(columns={"_sheet": "Loại"})
        elif "Loại" not in df.columns:
            df.insert(0, "Loại", "Tổng hợp")

        # Đưa cột Loại lên đầu (sau STT nếu có)
        cols = list(df.columns)
        if "STT" in cols and "Loại" in cols:
            cols.remove("Loại")
            stt_idx = cols.index("STT")
            cols.insert(stt_idx + 1, "Loại")
            df = df[cols]

        # Đếm theo loại để hiển thị badge
        counts = df["Loại"].value_counts().to_dict() if "Loại" in df.columns else {}
        badges = "  ".join(
            f"{_SHEET_BADGE.get(k,'📦')} **{k}**: {v}"
            for k, v in sorted(counts.items())
        )
        st.caption(f"{len(df)} dòng đã phân loại → {badges}")
        st.caption("Cột **Loại** có thể sửa trực tiếp ↓")

        edited_df = st.data_editor(
            df,
            width="stretch",
            num_rows="dynamic",
            key=f"editor__{uploaded_file.name}",
            hide_index=True,
            column_config={
                "Loại": st.column_config.SelectboxColumn(
                    "Loại",
                    options=SHEET_NAMES_ALL,
                    required=True,
                    help="Chọn sheet sẽ ghi dữ liệu vào",
                    width="small",
                ),
                "STT": st.column_config.TextColumn("STT", width="small"),
                "Số lượng": st.column_config.TextColumn("Số lượng", width="small"),
                "Kích thước": st.column_config.TextColumn("Kích thước", width="medium"),
                "Tên sản phẩm": st.column_config.TextColumn("Tên sản phẩm", width="large"),
            },
        )

        all_items.append({
            "file": uploaded_file.name,
            "df": edited_df,
            "order_info": info,
        })


# ─── TỔNG HỢP & XUẤT ────────────────────────────────────────────────────────
if not all_items:
    st.stop()

st.divider()
st.subheader("🚀 Tổng hợp & Xuất file")

# Gom tất cả dòng, nhóm theo cột Loại
# order_info được nhúng TRỰC TIẾP vào từng dòng để nhiều file/công ty không bị trộn
grouped: dict[str, list[dict]] = defaultdict(list)

_OI_FIELDS = {
    "Mã đơn hàng": "order_id",
    "Khách hàng":  "customer",
    "Ngày đặt":    "order_date",
    "Ngày giao":   "delivery_date",
}

for item in all_items:
    records = item["df"].to_dict("records")
    oi = item["order_info"]
    for rec in records:
        rec = dict(rec)
        sheet = str(rec.pop("Loại", "Tổng hợp")).strip() or "Tổng hợp"
        # Nhúng thông tin đơn hàng vào từng dòng nếu chưa có
        for col, oi_key in _OI_FIELDS.items():
            if not rec.get(col) or str(rec.get(col)).strip() in ("", "nan"):
                rec[col] = oi.get(oi_key, "")
        grouped[sheet].append(rec)

# Bảng tóm tắt phân loại
if grouped:
    summary_data = []
    for sheet, rows in sorted(grouped.items()):
        summary_data.append({
            "Loại": f"{_SHEET_BADGE.get(sheet,'📦')} {sheet}",
            "Số dòng": len(rows),
            "Mẫu sản phẩm": ", ".join(
                str(r.get("Tên sản phẩm",""))[:30]
                for r in rows[:2] if r.get("Tên sản phẩm")
            ) or "—",
        })
    st.dataframe(pd.DataFrame(summary_data), width="stretch", hide_index=True)

    st.caption("💡 Sheet **Tổng hợp** trong file Excel sẽ chứa **tất cả sản phẩm** từ mọi loại để dễ đối chiếu kiểm tra.")

    if st.button("📥 Xuất file kế hoạch sản xuất", type="primary", width="stretch"):
        with st.spinner("Đang ghi vào template…"):
            if custom_template is not None:
                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                    tmp.write(custom_template.read())
                    tpl_path = tmp.name
            else:
                tpl_path = str(ensure_template())

            # order_info đã nhúng vào từng dòng, không cần truyền riêng
            extracted_list = [
                {
                    "file": sheet,
                    "data": rows,
                    "sheet": sheet,
                    "order_info": {},
                }
                for sheet, rows in grouped.items()
            ]

            try:
                output_bytes = export_to_bytes(tpl_path, extracted_list)
                st.success(
                    f"✅ Xuất thành công! "
                    f"{sum(len(r) for r in grouped.values())} dòng → "
                    f"{len(grouped)} sheet"
                )
                st.download_button(
                    "💾 Tải về file kế hoạch sản xuất",
                    output_bytes,
                    file_name="ke_hoach_san_xuat_output.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )
            except Exception as e:
                st.error(f"Lỗi khi xuất file: {e}")
            finally:
                if custom_template is not None and os.path.exists(tpl_path):
                    os.unlink(tpl_path)
