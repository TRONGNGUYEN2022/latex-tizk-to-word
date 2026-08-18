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
from pdf2image import convert_from_path, convert_from_bytes
import pypandoc
from gemini_rotator import GeminiKeyRotator

st.set_page_config(page_title="LaTeX & TikZ Studio Pro", layout="wide")

# ----------------- LƯU TRỮ VĨNH VIỄN API KEYS -----------------
KEYS_FILE = "api_keys.json"

def load_saved_keys():
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                keys = json.load(f)
                return [k.strip() for k in keys if isinstance(k, str) and k.strip()]
        except Exception:
            return []
    return []

def save_keys_to_file(keys):
    try:
        with open(KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(keys, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Không thể lưu file key: {e}")

if "gemini_keys" not in st.session_state:
    st.session_state["gemini_keys"] = load_saved_keys()

with st.sidebar:
    st.header("🔑 Quản lý Gemini API Keys")
    with st.form("add_key_form", clear_on_submit=True):
        new_key = st.text_input("Nhập API Key mới:", type="password", placeholder="AIzaSy...")
        btn_add = st.form_submit_button("➕ Thêm & Lưu Vĩnh Viễn")
        if btn_add and new_key.strip():
            k = new_key.strip()
            if k not in st.session_state["gemini_keys"]:
                st.session_state["gemini_keys"].append(k)
                save_keys_to_file(st.session_state["gemini_keys"])
                st.success("✅ Đã lưu Key vào hệ thống!")
                st.rerun()
            else:
                st.warning("Key này đã có trong danh sách.")

    st.markdown("### 📋 Danh sách Key đã lưu:")
    if st.session_state["gemini_keys"]:
        keys_to_remove = []
        for idx, k in enumerate(st.session_state["gemini_keys"]):
            col_k1, col_k2 = st.columns([3.5, 1])
            masked_key = f"{k[:4]}...{k[-4:]}" if len(k) >= 8 else "Key ẩn"
            col_k1.code(f"#{idx+1}: {masked_key}")
            if col_k2.button("🗑️", key=f"del_{idx}"):
                keys_to_remove.append(idx)

        if keys_to_remove:
            for idx in reversed(keys_to_remove):
                st.session_state["gemini_keys"].pop(idx)
            save_keys_to_file(st.session_state["gemini_keys"])
            st.rerun()

        if st.button("🔄 Xóa toàn bộ Keys", type="secondary"):
            st.session_state["gemini_keys"] = []
            save_keys_to_file([])
            st.rerun()
    else:
        st.info("Chưa có Key nào. Vui lòng thêm ít nhất 1 Key để sử dụng OCR AI.")

# ----------------- XỬ LÝ BIÊN DỊCH TIKZ VÀ LATEX -----------------
def compile_raw_tikz_to_formats(tikz_code, output_dir, dpi=300):
    clean_tikz = tikz_code.strip()
    clean_tikz = re.sub(r"\\begin\{center\}", "", clean_tikz)
    clean_tikz = re.sub(r"\\end\{center\}", "", clean_tikz)
    clean_tikz = re.sub(r"\\centering", "", clean_tikz)
    clean_tikz = clean_tikz.strip()

    if not clean_tikz.startswith(r"\begin{tikzpicture}"):
        match = re.search(r"(\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\})", clean_tikz)
        if match:
            clean_tikz = match.group(1)
        else:
            clean_tikz = f"\\begin{{tikzpicture}}\n{clean_tikz}\n\\end{{tikzpicture}}"

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

    cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={output_dir}", tex_file]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    pdf_file = os.path.join(output_dir, f"{job_name}.pdf")
    if not os.path.exists(pdf_file):
        log_file = os.path.join(output_dir, f"{job_name}.log")
        error_log = ""
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8", errors="ignore") as lf:
                error_log = lf.read()[-1000:]
        raise RuntimeError(f"Lỗi biên dịch LaTeX TikZ:\n{error_log}")

    images = convert_from_path(pdf_file, dpi=dpi)
    if not images:
        raise RuntimeError("Không thể chuyển PDF sang định dạng hình ảnh.")

    png_path = os.path.join(output_dir, f"{job_name}.png")
    jpg_path = os.path.join(output_dir, f"{job_name}.jpg")
    images[0].save(png_path, "PNG")
    images[0].convert('RGB').save(jpg_path, "JPEG", quality=95)

    with open(png_path, "rb") as f:
        png_bytes = f.read()
    with open(jpg_path, "rb") as f:
        jpg_bytes = f.read()
    with open(pdf_file, "rb") as f:
        pdf_bytes = f.read()

    return {"png": png_bytes, "jpeg": jpg_bytes, "pdf": pdf_bytes, "preview_img": images[0]}

def convert_latex_to_html_preview(tex_file, temp_dir):
    try:
        html_out = os.path.join(temp_dir, "preview.html")
        pypandoc.convert_file(
            tex_file,
            "html5",
            outputfile=html_out,
            extra_args=["--mathjax", f"--resource-path={temp_dir}", "--metadata", "title=Xem trước tài liệu"]
        )
        with open(html_out, "r", encoding="utf-8") as f:
            html_body = f.read()

        def replace_img_with_base64(match):
            img_src = match.group(1)
            actual_path = img_src if os.path.isabs(img_src) else os.path.join(temp_dir, img_src)
            if os.path.exists(actual_path):
                with open(actual_path, "rb") as img_f:
                    b64_data = base64.b64encode(img_f.read()).decode("utf-8")
                return f'src="data:image/png;base64,{b64_data}"'
            return match.group(0)

        html_body = re.sub(r'src="([^"]+\.png)"', replace_img_with_base64, html_body)

        standalone_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script>
        window.MathJax = {{
          tex: {{
            inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
            displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
            processEscapes: true
          }}
        }};
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <style>
        body {{
            background-color: #525659;
            margin: 0; padding: 20px 10px;
            display: flex; flex-direction: column; align-items: center;
            font-family: "Times New Roman", Times, serif;
        }}
        .toolbar {{ width: 100%; max-width: 800px; display: flex; justify-content: flex-end; margin-bottom: 12px; }}
        .copy-btn {{
            background-color: #0078d4; color: white; border: none; padding: 9px 18px;
            font-size: 14px; font-weight: bold; border-radius: 4px; cursor: pointer;
        }}
        .a4-page {{
            background-color: white; width: 100%; max-width: 800px; min-height: 1050px;
            padding: 50px 60px; box-shadow: 0 4px 15px rgba(0,0,0,0.4); font-size: 15.5px;
            line-height: 1.6; color: #111; box-sizing: border-box;
        }}
        img {{ max-width: 85%; height: auto; display: block; margin: 15px auto; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #333; padding: 6px 10px; text-align: left; }}
    </style>
</head>
<body>
    <div class="toolbar">
        <button class="copy-btn" id="copyButton" onclick="copyDocumentToWord()">📋 Sao chép nội dung (Dán vào Word)</button>
    </div>
    <div class="a4-page" id="doc-content">{html_body}</div>
    <script>
        async function copyDocumentToWord() {{
            const docElement = document.getElementById("doc-content");
            const btn = document.getElementById("copyButton");
            try {{
                const htmlContent = docElement.innerHTML;
                const textContent = docElement.innerText;
                const blobHtml = new Blob([htmlContent], {{ type: "text/html" }});
                const blobText = new Blob([textContent], {{ type: "text/plain" }});
                const data = [new ClipboardItem({{ "text/html": blobHtml, "text/plain": blobText }})];
                await navigator.clipboard.write(data);
                btn.innerText = "✅ Đã sao chép! Mở Word và bấm Ctrl+V";
                btn.style.backgroundColor = "#107c41";
                setTimeout(() => {{
                    btn.innerText = "📋 Sao chép nội dung (Dán vào Word)";
                    btn.style.backgroundColor = "#0078d4";
                }}, 3500);
            }} catch (err) {{
                document.execCommand('copy');
            }}
        }}
    </script>
</body>
</html>"""
        b64_html = base64.b64encode(standalone_html.encode('utf-8')).decode('utf-8')
        return f'<iframe src="data:text/html;base64,{b64_html}" style="width:100%; height:900px; border:none; border-radius:8px;"></iframe>'
    except Exception as e:
        return f"<p style='color:red;'>Lỗi xem trước: {str(e)}</p>"

def process_latex_document(raw_tex):
    temp_dir = tempfile.mkdtemp()
    try:
        content = raw_tex
        body_match = re.search(r"\\begin\{document\}([\s\S]*?)\\end\{document\}", raw_tex)
        if body_match:
            content = body_match.group(1)

        tikz_pattern = re.compile(r"(\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\})")
        parts = tikz_pattern.split(content)
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
        final_latex = re.sub(r"\\begin\{minipage\}\[[^\]]*\]\{[^}]*\}", "\n", final_latex)
        final_latex = re.sub(r"\\end\{minipage\}", "\n", final_latex)

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

        html_preview = convert_latex_to_html_preview(modified_tex_file, temp_dir)
        return docx_bytes, html_preview, img_counter
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ----------------- GIAO DIỆN STREAMLIT -----------------
st.title("⚡ LaTeX & TikZ Studio")

tab_ai, tab1, tab2 = st.tabs([
    "🤖 OCR PDF/Ảnh sang Word (Gemini)",
    "🎨 Vẽ & Tải Ảnh TikZ Trực Tiếp",
    "📄 Chuyển Đổi Mã LaTeX Sang Word"
])

# TAB 0: CONVERT PDF/IMAGE SANG WORD
with tab_ai:
    st.subheader("Chuyển đổi trực tiếp tài liệu PDF hoặc Ảnh sang file Word (.docx)")
    col_ai1, col_ai2 = st.columns([1, 1])
    with col_ai1:
        uploaded_media = st.file_uploader("📁 Chọn file PDF hoặc Ảnh bài tập:", type=["pdf", "png", "jpg", "jpeg"])
        ocr_prompt = st.text_area(
            "Yêu cầu bổ sung cho AI (tuỳ chọn):",
            value="Hãy chuyển đổi toàn bộ đề toán và lời giải sang mã LaTeX chuẩn. Với các hình vẽ hình học hoặc đồ thị, hãy dựng bằng TikZ/pgfplots chính xác 100%."
        )
        btn_start_ai = st.button("🚀 Bắt đầu nhận diện & Chuyển sang Word", type="primary")

    if btn_start_ai:
        if not st.session_state["gemini_keys"]:
            st.error("⚠️ Vui lòng thêm ít nhất một Gemini API Key ở thanh Sidebar bên trái!")
        elif uploaded_media is None:
            st.warning("⚠️ Vui lòng tải lên file PDF hoặc Ảnh cần chuyển đổi!")
        else:
            with st.spinner("Đang xử lý qua Gemini AI và biên dịch TikZ..."):
                try:
                    rotator = GeminiKeyRotator(st.session_state["gemini_keys"])
                    media_bytes = uploaded_media.read()
                    pil_images = []

                    if uploaded_media.name.lower().endswith(".pdf"):
                        pil_images = convert_from_bytes(media_bytes, dpi=150)
                    else:
                        pil_images = [Image.open(io.BytesIO(media_bytes))]

                    sys_inst = """Bạn là chuyên gia chuyển đổi tài liệu Toán học sang LaTeX.
Nhiệm vụ: Chuyển toàn bộ nội dung trong ảnh thành mã LaTeX. 
Mọi công thức toán nằm trong $...$ hoặc $$...$$. 
Tất cả hình vẽ hình học, đồ thị hàm số, bảng biến thiên BẮT BUỘC dựng bằng môi trường \\begin{tikzpicture}...\\end{tikzpicture}.
Chỉ trả về trực tiếp mã LaTeX giữa \\begin{document} và \\end{document}, không viết lời mở đầu."""

                    contents_payload = [ocr_prompt]
                    for img in pil_images:
                        contents_payload.append(img)

                    ai_latex_code = rotator.generate_content_with_retry(
                        contents=contents_payload,
                        model="gemini-2.5-flash",
                        system_instruction=sys_inst
                    )
                    
                    ai_latex_code = re.sub(r"^```latex\s*", "", ai_latex_code, flags=re.MULTILINE)
                    ai_latex_code = re.sub(r"^```\s*", "", ai_latex_code, flags=re.MULTILINE)

                    docx_bytes, preview_html, total_img = process_latex_document(ai_latex_code)
                    
                    st.session_state["ai_docx"] = docx_bytes
                    st.session_state["ai_preview"] = preview_html
                    st.session_state["ai_code"] = ai_latex_code
                    st.success(f"✅ Hoàn tất nhận diện! Đã trích xuất và dựng thành công {total_img} hình TikZ.")
                except Exception as e:
                    st.error(f"❌ Xảy ra lỗi: {str(e)}")

    with col_ai2:
        if "ai_docx" in st.session_state:
            st.markdown("### 📥 Tải Về Kết Quả Word")
            st.download_button(
                label="📥 Tải file Word (.docx)",
                data=st.session_state["ai_docx"],
                file_name="Tai_Lieu_Gemini_OCR.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True
            )
            with st.expander("📝 Xem mã nguồn LaTeX AI đã sinh"):
                st.code(st.session_state.get("ai_code", ""), language="latex")

    st.markdown("---")
    st.subheader("📑 Bản Xem Trước A4")
    if "ai_preview" in st.session_state:
        st.components.v1.html(st.session_state["ai_preview"], height=900, scrolling=True)

# TAB 1: RENDER VÀ TẢI ẢNH TIKZ RIÊNG LẺ
with tab1:
    st.subheader("Dán mã TikZ $\\rightarrow$ Xem trước & Tải về file ảnh (PNG / JPEG / PDF)")
    col_t1, col_t2 = st.columns([1.1, 1])
    with col_t1:
        tikz_single_code = st.text_area(
            "Nhập khối mã TikZ:",
            height=260,
            value=r"""\begin{tikzpicture}[scale=1]
    \draw[thick, blue] (0,0) circle (2cm);
    \draw[thick, fill=orange!20] (-1.2,-1) rectangle (1.2,1);
    \node at (0,0) {\textbf{TikZ Image}};
\end{tikzpicture}"""
        )
        dpi_choice = st.select_slider("Độ phân giải ảnh (DPI):", options=[150, 300, 600], value=300)
        btn_render_img = st.button("🖼️ Render & Tạo File Ảnh", type="primary")

    with col_t2:
        if btn_render_img and tikz_single_code.strip():
            with st.spinner("Đang biên dịch TikZ sang ảnh..."):
                try:
                    temp_dir = tempfile.mkdtemp()
                    img_data = compile_raw_tikz_to_formats(tikz_single_code, temp_dir, dpi=dpi_choice)
                    st.success("✅ Biên dịch thành công!")
                    st.image(img_data["preview_img"], caption="Bản xem trước", use_container_width=True)
                    
                    dcol1, dcol2, dcol3 = st.columns(3)
                    dcol1.download_button("Tải PNG", img_data["png"], "tikz.png", "image/png", use_container_width=True)
                    dcol2.download_button("Tải JPEG", img_data["jpeg"], "tikz.jpg", "image/jpeg", use_container_width=True)
                    dcol3.download_button("Tải PDF", img_data["pdf"], "tikz.pdf", "application/pdf", use_container_width=True)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    st.error(f"❌ {str(e)}")

# TAB 2: CHUYỂN ĐỔI LATEX DOCUMENT SANG WORD THỦ CÔNG
with tab2:
    st.subheader("Chuyển toàn bộ file/mã LaTeX thủ công sang Word (.docx)")
    c1, c2 = st.columns([1, 1])
    with c1:
        uploaded_doc = st.file_uploader("📁 Tải file .tex", type=["tex", "txt"], key="manual_tex")
        doc_text = st.text_area("Hoặc dán mã LaTeX tại đây:", height=200, key="manual_text")
        btn_convert_doc = st.button("🚀 Chuyển đổi sang Word", type="primary", key="btn_manual")

    raw_doc = uploaded_doc.read().decode("utf-8", errors="ignore") if uploaded_doc else doc_text

    if btn_convert_doc and raw_doc.strip():
        with st.spinner("Đang xử lý sang MathML..."):
            try:
                docx_bytes, preview_html, total_img = process_latex_document(raw_doc)
                st.session_state["man_docx"] = docx_bytes
                st.session_state["man_preview"] = preview_html
                st.success(f"✅ Đã xử lý {total_img} hình TikZ.")
            except Exception as e:
                st.error(f"❌ {str(e)}")

    with c2:
        if "man_docx" in st.session_state:
            st.download_button(
                label="📥 Tải file Word (.docx)",
                data=st.session_state["man_docx"],
                file_name="Tai_Lieu_Word.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True
            )

    st.markdown("---")
    st.subheader("📑 Bản Xem Trước A4")
    if "man_preview" in st.session_state:
        st.components.v1.html(st.session_state["man_preview"], height=900, scrolling=True)