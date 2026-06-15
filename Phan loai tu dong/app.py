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
from modules.extractor import extract_from_file, needs_claude_fallback, SHEET_NAMES_ALL
from modules.excel_handler import export_to_bytes
from modules.classify_overrides import save_override

TEMPLATE_PATH = Path("template/ke_hoach_san_xuat.xlsx")

if "claude_manual_results" not in st.session_state:
    st.session_state.claude_manual_results = {}

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
        # Tạo lại nếu template cũ thiếu sheet hoặc cột không khớp TEMPLATE_COLUMNS
        try:
            import openpyxl
            wb = openpyxl.load_workbook(TEMPLATE_PATH)
            for sheet_name, columns in TEMPLATE_COLUMNS.items():
                if sheet_name not in wb.sheetnames:
                    needs_create = True
                    break
                headers = [c.value for c in wb[sheet_name][1]]
                while headers and headers[-1] is None:
                    headers.pop()
                if headers != columns:
                    needs_create = True
                    break
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
    claude_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        help="Dự phòng cho từng file: chỉ dùng khi pdfplumber/OCR không đọc được file đó "
             "(PDF scan, ảnh, không phát hiện bảng...).",
    )
    if claude_key:
        st.success("✅ Claude AI dự phòng cho file lỗi")
    else:
        st.info("Chưa nhập API key — chỉ dùng pdfplumber + OCR miễn phí")

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
    file_key = getattr(uploaded_file, "file_id", None) or f"{uploaded_file.name}_{uploaded_file.size}"

    with st.expander(f"📄 {uploaded_file.name}", expanded=True):
        result = st.session_state.claude_manual_results.get(file_key)
        from_manual_claude = result is not None

        if result is None:
            with st.spinner(f"Đang xử lý **{uploaded_file.name}**…"):
                result = extract_from_file(uploaded_file, claude_api_key=None)
                if claude_key and needs_claude_fallback(uploaded_file.name, result):
                    uploaded_file.seek(0)
                    retry = extract_from_file(uploaded_file, claude_api_key=claude_key)
                    if retry["success"] and (retry["data"] or any((retry.get("order_info") or {}).values())):
                        result = retry
                        st.info("🤖 pdfplumber/OCR không đọc được file này — đã tự động dùng Claude AI")

        if from_manual_claude:
            st.info("🤖 Đã đọc lại file này bằng Claude AI")

        if not result["success"]:
            st.error(f"❌ {result['error']}")
        elif result["warning"]:
            st.warning(result["warning"])

        # File vẫn lỗi / chưa có bảng → cho nhập API key và đọc lại riêng file này bằng Claude AI
        if needs_claude_fallback(uploaded_file.name, result):
            with st.form(f"claude_form_{file_key}"):
                manual_key = st.text_input(
                    "Anthropic API Key cho file này",
                    type="password",
                    value=claude_key,
                    placeholder="sk-ant-...",
                    help="Chỉ dùng để đọc lại riêng file này bằng Claude AI.",
                )
                run_claude = st.form_submit_button("🤖 Đọc lại bằng Claude AI")
            if run_claude:
                if not manual_key:
                    st.warning("Vui lòng nhập API key")
                else:
                    uploaded_file.seek(0)
                    with st.spinner(f"Đang đọc **{uploaded_file.name}** bằng Claude AI…"):
                        retry = extract_from_file(uploaded_file, claude_api_key=manual_key)
                    st.session_state.claude_manual_results[file_key] = retry
                    for _f in ("customer", "order_date", "delivery_date"):
                        st.session_state.pop(f"{_f}__{file_key}", None)
                    st.rerun()

        if not result["success"]:
            continue

        info = result.get("order_info") or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Mã đơn hàng", info.get("order_id") or "—")
        info["customer"] = c2.text_input(
            "Khách hàng", value=info.get("customer", ""),
            key=f"customer__{file_key}",
            help="Sửa lại nếu bóc tách tự động sai hoặc thiếu tên khách hàng",
        )
        info["order_date"] = c3.text_input(
            "Ngày đặt", value=info.get("order_date", ""),
            key=f"order_date__{file_key}",
        )
        info["delivery_date"] = c4.text_input(
            "Ngày giao", value=info.get("delivery_date", ""),
            key=f"delivery_date__{file_key}",
        )

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

        # Lưu lại "Loại" do hệ thống tự phân loại (trước khi người dùng sửa tay)
        # để so sánh sau khi data_editor trả về, dùng "Tên sản phẩm" làm khoá ghép.
        auto_loai_by_product = {}
        if "Loại" in df.columns and "Tên sản phẩm" in df.columns:
            for _, _row in df.iterrows():
                _name = str(_row.get("Tên sản phẩm", "")).strip()
                if _name:
                    auto_loai_by_product[_name] = str(_row.get("Loại", "")).strip()

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

        # Nếu người dùng sửa tay cột "Loại" khác với phân loại tự động ban đầu
        # → lưu lại để các lần phân loại sau tự nhớ (theo tên sản phẩm)
        if "Loại" in edited_df.columns and "Tên sản phẩm" in edited_df.columns:
            for _, _row in edited_df.iterrows():
                _name = str(_row.get("Tên sản phẩm", "")).strip()
                _new_loai = str(_row.get("Loại", "")).strip()
                if not _name or not _new_loai:
                    continue
                _old_loai = auto_loai_by_product.get(_name)
                if _old_loai is not None and _new_loai != _old_loai:
                    save_override(_name, _new_loai)

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
