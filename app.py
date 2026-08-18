import streamlit as st
import os
import re
import json
import subprocess
import tempfile
import shutil
from pdf2image import convert_from_path
import pypandoc
from gemini_rotator import GeminiKeyRotator

st.set_page_config(page_title="PDF & LaTeX to Word Studio", layout="wide")

# ----------------- QUẢN LÝ LƯU TRỮ API KEYS -----------------
KEYS_FILE = "api_keys.json"

def load_saved_keys():
    try:
        if os.path.exists(KEYS_FILE):
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                keys = json.load(f)
                return [k.strip() for k in keys if isinstance(k, str) and k.strip()]
    except Exception:
        pass
    return []

def save_keys_to_file(keys):
    try:
        with open(KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(keys, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.sidebar.error(f"Lỗi lưu file key: {e}")

if "gemini_keys" not in st.session_state:
    st.session_state["gemini_keys"] = load_saved_keys()

if "current_tex_code" not in st.session_state:
    st.session_state["current_tex_code"] = ""

# ----------------- SIDEBAR QUẢN LÝ KEYS -----------------
with st.sidebar:
    st.header("🔑 Gemini API Keys")
    with st.form("add_key_form", clear_on_submit=True):
        new_key = st.text_input("Thêm API Key mới:", type="password", placeholder="AIzaSy...")
        btn_add = st.form_submit_button("➕ Lưu Key")
        if btn_add and new_key.strip():
            k = new_key.strip()
            if k not in st.session_state["gemini_keys"]:
                st.session_state["gemini_keys"].append(k)
                save_keys_to_file(st.session_state["gemini_keys"])
                st.success("✅ Đã lưu Key!")
                st.rerun()

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

        if st.button("🔄 Xóa toàn bộ"):
            st.session_state["gemini_keys"] = []
            save_keys_to_file([])
            st.rerun()
    else:
        st.info("Chưa có Key nào.")

# ----------------- HÀM BIÊN DỊCH LATEX/TIKZ SANG WORD -----------------
def compile_single_tikz(tikz_code, output_dir, dpi=300):
    clean_tikz = re.sub(r"\\begin\{center\}|\\end\{center\}|\\centering", "", tikz_code).strip()
    if not clean_tikz.startswith(r"\begin{tikzpicture}"):
        match = re.search(r"(\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\})", clean_tikz)
        clean_tikz = match.group(1) if match else f"\\begin{{tikzpicture}}\n{clean_tikz}\n\\end{{tikzpicture}}"

    tex_doc = f"""\\documentclass[border=2mm,varwidth=\\maxdimen]{{standalone}}
\\usepackage[utf8]{{vietnam}}
\\usepackage{{amsmath,amssymb,amsfonts}}
\\usepackage{{tikz}}
\\usetikzlibrary{{calc,angles,quotes,patterns,intersections}}
\\begin{{document}}
{clean_tikz}
\\end{{document}}
"""
    job_name = "tikz_temp"
    tex_path = os.path.join(output_dir, f"{job_name}.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_doc)

    subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={output_dir}", tex_path],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    pdf_path = os.path.join(output_dir, f"{job_name}.pdf")
    if not os.path.exists(pdf_path):
        return None

    images = convert_from_path(pdf_path, dpi=dpi)
    if images:
        png_path = os.path.join(output_dir, f"{job_name}.png")
        images[0].save(png_path, "PNG")
        with open(png_path, "rb") as f:
            return f.read()
    return None

def convert_latex_to_docx(raw_tex):
    temp_dir = tempfile.mkdtemp()
    try:
        content = raw_tex
        body_match = re.search(r"\\begin\{document\}([\s\S]*?)\\end\{document\}", raw_tex)
        if body_match:
            content = body_match.group(1)

        parts = re.split(r"(\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\})", content)
        reconstructed = []
        img_idx = 0

        for part in parts:
            if part.startswith(r"\begin{tikzpicture}") and part.endswith(r"\end{tikzpicture}"):
                png_bytes = compile_single_tikz(part, temp_dir)
                if png_bytes:
                    img_file = os.path.join(temp_dir, f"fig_{img_idx}.png")
                    with open(img_file, "wb") as f:
                        f.write(png_bytes)
                    norm_path = img_file.replace("\\", "/")
                    reconstructed.append(f"\n\\begin{{center}}\\includegraphics[width=0.5\\textwidth]{{{norm_path}}}\\end{{center}}\n")
                    img_idx += 1
                else:
                    reconstructed.append(part)
            else:
                reconstructed.append(part)

        final_tex = "".join(reconstructed)
        tex_file = os.path.join(temp_dir, "input.tex")
        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(final_tex)

        docx_file = os.path.join(temp_dir, "output.docx")
        pypandoc.convert_file(
            tex_file,
            "docx",
            outputfile=docx_file,
            extra_args=["--mathml", f"--resource-path={temp_dir}", "--wrap=none"]
        )

        with open(docx_file, "rb") as f:
            return f.read(), img_idx
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ----------------- GIAO DIỆN CHÍNH (2 TABS) -----------------
st.title("⚡ PDF & LaTeX to Word Studio")

tab1, tab2 = st.tabs([
    "1️⃣ OCR PDF sang LaTeX (.tex)",
    "2️⃣ Chuyển đổi LaTeX (.tex) sang Word (.docx)"
])

# TAB 1: PDF SANG LATEX
with tab1:
    st.subheader("Nhận diện PDF bài tập $\\rightarrow$ Sinh mã LaTeX / TikZ")
    up_pdf = st.file_uploader("📁 Tải lên file PDF:", type=["pdf"], key="pdf_tab1")
    prompt_txt = st.text_area("Yêu cầu nhận diện:", value="Chuyển toàn bộ bài tập trong PDF sang LaTeX. Vẽ tất cả hình bằng môi trường tikzpicture.")

    if st.button("🚀 Gửi PDF lên Gemini & Tạo LaTeX", type="primary"):
        if not st.session_state["gemini_keys"]:
            st.error("⚠️ Cần thêm ít nhất 1 API Key ở sidebar!")
        elif not up_pdf:
            st.warning("⚠️ Hãy chọn file PDF.")
        else:
            with st.spinner("Gemini đang đọc PDF và sinh mã LaTeX/TikZ..."):
                try:
                    rotator = GeminiKeyRotator(st.session_state["gemini_keys"])
                    raw_out = rotator.convert_pdf_to_latex(up_pdf.read(), prompt_txt)
                    clean_tex = re.sub(r"^```latex\s*|^```\s*", "", raw_out, flags=re.MULTILINE)
                    clean_tex = re.sub(r"```$", "", clean_tex.strip())
                    
                    st.session_state["current_tex_code"] = clean_tex
                    st.success("✅ Đã nhận diện xong mã LaTeX!")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    if st.session_state["current_tex_code"]:
        st.markdown("---")
        st.text_area("Mã LaTeX thu được:", value=st.session_state["current_tex_code"], height=300)
        
        c1, c2 = st.columns([1, 1])
        c1.download_button(
            "📥 Tải file .tex về máy",
            data=st.session_state["current_tex_code"],
            file_name="output.tex",
            mime="text/x-tex"
        )
        c2.info("👉 Chuyển sang **Tab 2** để chuyển mã này thành file Word (.docx)!")

# TAB 2: LATEX SANG WORD
with tab2:
    st.subheader("Chuyển mã LaTeX (.tex) sang Word (.docx)")
    
    up_tex = st.file_uploader("📁 Tải file .tex từ máy tính (tuỳ chọn):", type=["tex", "txt"], key="tex_tab2")
    if up_tex:
        st.session_state["current_tex_code"] = up_tex.read().decode("utf-8", errors="ignore")

    tex_input = st.text_area(
        "Nội dung mã LaTeX cần xuất Word (đã đồng bộ tự động từ Tab 1):",
        value=st.session_state["current_tex_code"],
        height=350
    )

    if st.button("🚀 Chuyển đổi mã này sang Word (.docx)", type="primary"):
        if not tex_input.strip():
            st.warning("⚠️ Mã LaTeX trống. Vui lòng nhập mã hoặc thực hiện OCR ở Tab 1 trước.")
        else:
            with st.spinner("Đang biên dịch hình TikZ và tạo tài liệu Word MathML..."):
                try:
                    docx_data, total_imgs = convert_latex_to_docx(tex_input)
                    st.success(f"✅ Đã xuất Word thành công! Xử lý hoàn tất {total_imgs} hình vẽ TikZ.")
                    st.download_button(
                        label="📥 Tải file Word (.docx) về máy",
                        data=docx_data,
                        file_name="Tai_Lieu_Hoan_Chinh.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary"
                    )
                except Exception as e:
                    st.error(f"❌ Lỗi chuyển Word: {e}")