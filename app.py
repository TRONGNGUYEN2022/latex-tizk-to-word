import streamlit as st
import os
import re
import json
import subprocess
import tempfile
import shutil
import base64
import io
from PIL import Image

st.set_page_config(page_title="LaTeX & TikZ Studio Pro", layout="wide")

# ----------------- QUẢN LÝ LƯU TRỮ KEYS AN TOÀN -----------------
KEYS_FILE = "api_keys.json"

def load_saved_keys():
    try:
        if os.path.exists(KEYS_FILE):
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                keys = json.load(f)
                return [k.strip() for k in keys if isinstance(k, str) and k.strip()]
    except Exception as e:
        st.sidebar.warning(f"Không thể đọc file key: {e}")
    return []

def save_keys_to_file(keys):
    try:
        with open(KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(keys, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.sidebar.error(f"Không có quyền ghi file key: {e}")

if "gemini_keys" not in st.session_state:
    st.session_state["gemini_keys"] = load_saved_keys()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.header("🔑 Quản lý Gemini API Keys")
    with st.form("add_key_form", clear_on_submit=True):
        new_key = st.text_input("Nhập API Key mới:", type="password", placeholder="AIzaSy...")
        btn_add = st.form_submit_button("➕ Thêm Key")
        if btn_add and new_key.strip():
            k = new_key.strip()
            if k not in st.session_state["gemini_keys"]:
                st.session_state["gemini_keys"].append(k)
                save_keys_to_file(st.session_state["gemini_keys"])
                st.success("✅ Đã lưu Key!")
                st.rerun()
            else:
                st.warning("Key này đã có sẵn.")

    if st.session_state["gemini_keys"]:
        st.markdown("### 📋 Danh sách Key:")
        keys_to_remove = []
        for idx, k in enumerate(st.session_state["gemini_keys"]):
            col_k1, col_k2 = st.columns([3.5, 1])
            masked = f"{k[:4]}...{k[-4:]}" if len(k) >= 8 else "Key"
            col_k1.code(f"#{idx+1}: {masked}")
            if col_k2.button("🗑️", key=f"del_{idx}"):
                keys_to_remove.append(idx)

        if keys_to_remove:
            for idx in reversed(keys_to_remove):
                st.session_state["gemini_keys"].pop(idx)
            save_keys_to_file(st.session_state["gemini_keys"])
            st.rerun()

        if st.button("🔄 Xóa toàn bộ Keys"):
            st.session_state["gemini_keys"] = []
            save_keys_to_file([])
            st.rerun()
    else:
        st.info("Chưa có Key nào trong hệ thống.")

# ----------------- XỬ LÝ BIÊN DỊCH VÀ CHUYỂN ĐỔI -----------------
def compile_raw_tikz_to_formats(tikz_code, output_dir, dpi=300):
    from pdf2image import convert_from_path
    clean_tikz = re.sub(r"\\begin\{center\}|\\end\{center\}|\\centering", "", tikz_code).strip()
    if not clean_tikz.startswith(r"\begin{tikzpicture}"):
        match = re.search(r"(\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\})", clean_tikz)
        clean_tikz = match.group(1) if match else f"\\begin{{tikzpicture}}\n{clean_tikz}\n\\end{{tikzpicture}}"

    tex_content = f"""\\documentclass[border=3mm,varwidth=\\maxdimen]{{standalone}}
\\usepackage[utf8]{{vietnam}}
\\usepackage{{amsmath,amssymb,amsfonts}}
\\usepackage{{tikz}}
\\usepackage{{tkz-euclide}}
\\usepackage{{pgfplots}}
\\pgfplotsset{{compat=1.18}}
\\usetikzlibrary{{calc,angles,quotes,patterns,intersections}}
\\begin{{document}}
{clean_tikz}
\\end{{document}}
"""
    job_name = "custom_tikz_render"
    tex_file = os.path.join(output_dir, f"{job_name}.tex")
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(tex_content)

    subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={output_dir}", tex_file],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    pdf_file = os.path.join(output_dir, f"{job_name}.pdf")
    if not os.path.exists(pdf_file):
        raise RuntimeError("Lỗi biên dịch pdflatex. Vui lòng kiểm tra lại cú pháp TikZ.")

    images = convert_from_path(pdf_file, dpi=dpi)
    if not images:
        raise RuntimeError("Không thể xuất ảnh từ PDF TikZ.")

    png_path = os.path.join(output_dir, f"{job_name}.png")
    jpg_path = os.path.join(output_dir, f"{job_name}.jpg")
    images[0].save(png_path, "PNG")
    images[0].convert('RGB').save(jpg_path, "JPEG", quality=95)

    with open(png_path, "rb") as f: png_bytes = f.read()
    with open(jpg_path, "rb") as f: jpg_bytes = f.read()
    with open(pdf_file, "rb") as f: pdf_bytes = f.read()

    return {"png": png_bytes, "jpeg": jpg_bytes, "pdf": pdf_bytes, "preview_img": images[0]}

def process_latex_document(raw_tex):
    import pypandoc
    temp_dir = tempfile.mkdtemp()
    try:
        content = raw_tex
        body_match = re.search(r"\\begin\{document\}([\s\S]*?)\\end\{document\}", raw_tex)
        if body_match:
            content = body_match.group(1)

        parts = re.split(r"(\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\})", content)
        reconstructed_tex = []
        img_counter = 0

        for part in parts:
            if part.startswith(r"\begin{tikzpicture}") and part.endswith(r"\end{tikzpicture}"):
                res = compile_raw_tikz_to_formats(part, temp_dir, dpi=300)
                img_path = os.path.join(temp_dir, f"doc_tikz_{img_counter}.png")
                with open(img_path, "wb") as f:
                    f.write(res["png"])
                norm_path = img_path.replace("\\", "/")
                reconstructed_tex.append(f"\n\\begin{{center}}\\includegraphics[width=0.48\\textwidth]{{{norm_path}}}\\end{{center}}\n")
                img_counter += 1
            else:
                reconstructed_tex.append(part)

        final_latex = "".join(reconstructed_tex)
        modified_tex_file = os.path.join(temp_dir, "document.tex")
        with open(modified_tex_file, "w", encoding="utf-8") as f:
            f.write(final_latex)

        docx_output_file = os.path.join(temp_dir, "Tai_Lieu_Word.docx")
        pypandoc.convert_file(
            modified_tex_file,
            "docx",
            outputfile=docx_output_file,
            extra_args=["--mathml", f"--resource-path={temp_dir}", "--wrap=none"]
        )

        with open(docx_output_file, "rb") as docx_f:
            docx_bytes = docx_f.read()

        return docx_bytes, img_counter
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ----------------- GIAO DIỆN CHÍNH -----------------
st.title("⚡ LaTeX & TikZ Studio")

tab_ai, tab1, tab2 = st.tabs([
    "🤖 OCR PDF/Ảnh sang Word (Gemini)",
    "🎨 Vẽ & Tải Ảnh TikZ Trực Tiếp",
    "📄 Chuyển Đổi Mã LaTeX Sang Word"
])

with tab_ai:
    st.subheader("Chuyển đổi PDF/Ảnh sang Word qua Gemini REST API")
    uploaded_media = st.file_uploader("📁 Tải file PDF hoặc Ảnh:", type=["pdf", "png", "jpg", "jpeg"])
    ocr_prompt = st.text_area("Yêu cầu thêm:", value="Chuyển toàn bộ nội dung sang LaTeX chuẩn. Dựng hình vẽ bằng TikZ.")
    
    if st.button("🚀 Bắt đầu nhận diện & Chuyển sang Word", type="primary"):
        if not st.session_state["gemini_keys"]:
            st.error("⚠️ Hãy thêm ít nhất 1 Gemini API Key ở thanh bên trái!")
        elif not uploaded_media:
            st.warning("⚠️ Vui lòng tải file lên trước.")
        else:
            with st.spinner("Đang nhận diện qua Gemini và tạo file Word..."):
                try:
                    from gemini_rotator import GeminiKeyRotator
                    from pdf2image import convert_from_bytes
                    
                    rotator = GeminiKeyRotator(st.session_state["gemini_keys"])
                    media_bytes = uploaded_media.read()
                    
                    if uploaded_media.name.lower().endswith(".pdf"):
                        pil_images = convert_from_bytes(media_bytes, dpi=150)
                    else:
                        pil_images = [Image.open(io.BytesIO(media_bytes))]

                    sys_inst = "Chuyển toàn bộ nội dung trong ảnh thành mã LaTeX. Mọi công thức đặt trong $...$. Hình vẽ dựng bằng \\begin{tikzpicture}...\\end{tikzpicture}. Chỉ trả về mã LaTeX."
                    
                    contents_payload = [ocr_prompt] + pil_images
                    ai_latex_code = rotator.generate_content_with_retry(
                        contents=contents_payload,
                        model="gemini-2.5-flash",
                        system_instruction=sys_inst
                    )
                    
                    ai_latex_code = re.sub(r"^```latex\s*|^```\s*", "", ai_latex_code, flags=re.MULTILINE)
                    docx_bytes, total_img = process_latex_document(ai_latex_code)
                    
                    st.success(f"✅ Hoàn tất! Đã dựng {total_img} hình TikZ.")
                    st.download_button("📥 Tải file Word (.docx)", docx_bytes, "Tai_Lieu_OCR.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    with st.expander("📝 Xem mã LaTeX đã sinh"):
                        st.code(ai_latex_code, language="latex")
                except Exception as e:
                    st.error(f"❌ Chi tiết lỗi: {str(e)}")

with tab1:
    st.subheader("Render mã TikZ sang file ảnh")
    tikz_single = st.text_area("Mã TikZ:", height=200, value=r"""\begin{tikzpicture}
\draw[thick, fill=blue!20] (0,0) circle (1.5cm);
\node at (0,0) {\textbf{TikZ OK}};
\end{tikzpicture}""")
    if st.button("🖼️ Render Ảnh", type="primary"):
        try:
            td = tempfile.mkdtemp()
            res = compile_raw_tikz_to_formats(tikz_single, td)
            st.image(res["preview_img"])
            st.download_button("Tải ảnh PNG", res["png"], "tikz.png", "image/png")
            shutil.rmtree(td, ignore_errors=True)
        except Exception as e:
            st.error(f"Lỗi: {e}")

with tab2:
    st.subheader("Chuyển mã LaTeX thủ công sang Word")
    raw_input = st.text_area("Dán mã LaTeX vào đây:", height=200)
    if st.button("🚀 Chuyển sang Word", key="btn_tab2"):
        if raw_input.strip():
            try:
                docx_bytes, total_img = process_latex_document(raw_input)
                st.success(f"✅ Hoàn tất! Đã xử lý {total_img} hình.")
                st.download_button("📥 Tải Word", docx_bytes, "Document.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            except Exception as e:
                st.error(f"Lỗi: {e}")