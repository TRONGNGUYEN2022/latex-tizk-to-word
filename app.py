import streamlit as st
import os
import re
import subprocess
import tempfile
import shutil
import base64
import zipfile
from PIL import Image
from pdf2image import convert_from_path
import pypandoc

st.set_page_config(page_title="LaTeX & TikZ Studio Pro", layout="wide")

def compile_raw_tikz_to_formats(tikz_code, output_dir, dpi=300):
    """
    Biên dịch riêng khối TikZ sang PDF, PNG, JPEG, SVG
    """
    # Tự động bọc begin/end nếu người dùng chỉ dán phần thân \draw...
    clean_tikz = tikz_code.strip()
    if not clean_tikz.startswith(r"\begin{tikzpicture}"):
        clean_tikz = f"\\begin{{tikzpicture}}\n{clean_tikz}\n\\end{{tikzpicture}}"

    tex_content = f"""\\documentclass[border=3mm]{{standalone}}
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
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    pdf_file = os.path.join(output_dir, f"{job_name}.pdf")
    if not os.path.exists(pdf_file):
        log_file = os.path.join(output_dir, f"{job_name}.log")
        error_log = ""
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8", errors="ignore") as lf:
                error_log = lf.read()[-1000:]
        raise RuntimeError(f"Lỗi biên dịch LaTeX TikZ:\n{error_log}")

    # Chuyển đổi sang PNG
    images = convert_from_path(pdf_file, dpi=dpi)
    if not images:
        raise RuntimeError("Không thể chuyển PDF sang định dạng hình ảnh.")

    png_path = os.path.join(output_dir, f"{job_name}.png")
    jpg_path = os.path.join(output_dir, f"{job_name}.jpg")
    
    # Lưu PNG nền trong suốt / trắng
    images[0].save(png_path, "PNG")
    
    # Lưu JPEG nền trắng
    rgb_img = images[0].convert('RGB')
    rgb_img.save(jpg_path, "JPEG", quality=95)

    with open(png_path, "rb") as f:
        png_bytes = f.read()
    with open(jpg_path, "rb") as f:
        jpg_bytes = f.read()
    with open(pdf_file, "rb") as f:
        pdf_bytes = f.read()

    return {
        "png": png_bytes,
        "jpeg": jpg_bytes,
        "pdf": pdf_bytes,
        "preview_img": images[0]
    }

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
          }},
          options: {{
            skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
          }}
        }};
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <style>
        body {{
            background-color: #525659;
            margin: 0;
            padding: 20px 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
            font-family: "Times New Roman", Times, serif;
        }}
        .toolbar {{
            width: 100%;
            max-width: 800px;
            display: flex;
            justify-content: flex-end;
            margin-bottom: 12px;
        }}
        .copy-btn {{
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 9px 18px;
            font-size: 14px;
            font-weight: bold;
            border-radius: 4px;
            cursor: pointer;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            transition: 0.2s;
        }}
        .copy-btn:hover {{ background-color: #106ebe; }}
        .a4-page {{
            background-color: white;
            width: 100%;
            max-width: 800px;
            min-height: 1050px;
            padding: 50px 60px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
            font-size: 15.5px;
            line-height: 1.6;
            color: #111;
            box-sizing: border-box;
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
    <div class="a4-page" id="doc-content">
        {html_body}
    </div>
    <script>
        async function copyDocumentToWord() {{
            const docElement = document.getElementById("doc-content");
            const btn = document.getElementById("copyButton");
            try {{
                const blobHtml = new Blob([docElement.innerHTML], {{ type: "text/html" }});
                const blobText = new Blob([docElement.innerText], {{ type: "text/plain" }});
                const data = [new ClipboardItem({{ "text/html": blobHtml, "text/plain": blobText }})];
                await navigator.clipboard.write(data);
                btn.innerText = "✅ Đã sao chép! Mở Word và bấm Ctrl+V";
                btn.style.backgroundColor = "#107c41";
                setTimeout(() => {{
                    btn.innerText = "📋 Sao chép nội dung (Dán vào Word)";
                    btn.style.backgroundColor = "#0078d4";
                }}, 3500);
            }} catch (err) {{
                const selection = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(docElement);
                selection.removeAllRanges();
                selection.addRange(range);
                document.execCommand('copy');
                selection.removeAllRanges();
                btn.innerText = "✅ Đã sao chép! Mở Word và bấm Ctrl+V";
                btn.style.backgroundColor = "#107c41";
                setTimeout(() => {{
                    btn.innerText = "📋 Sao chép nội dung (Dán vào Word)";
                    btn.style.backgroundColor = "#0078d4";
                }}, 3500);
            }}
        }}
    </script>
</body>
</html>
"""
        b64_html = base64.b64encode(standalone_html.encode('utf-8')).decode('utf-8')
        return f'<iframe src="data:text/html;base64,{b64_html}" style="width:100%; height:900px; border:none; border-radius:8px;"></iframe>'
    except Exception as e:
        return f"<p style='color:red;'>Lỗi xem trước: {str(e)}</p>"

def process_latex_document(raw_tex):
    temp_dir = tempfile.mkdtemp()
    try:
        tikz_pattern = re.compile(r"(\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\})")
        parts = tikz_pattern.split(raw_tex)
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

# ----------------- GIAO DIỆN ỨNG DỤNG -----------------
st.title("⚡ LaTeX & TikZ Studio")

tab1, tab2 = st.tabs(["🎨 Vẽ & Tải Ảnh TikZ Trực Tiếp", "📄 Chuyển Đổi Tài Liệu LaTeX Sang Word"])

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
                    st.image(img_data["preview_img"], caption="Bản xem trước hình ảnh", use_container_width=True)
                    
                    st.markdown("### 📥 Chọn định dạng tải về:")
                    dcol1, dcol2, dcol3 = st.columns(3)
                    with dcol1:
                        st.download_button(
                            label="Tải ảnh PNG",
                            data=img_data["png"],
                            file_name="tikz_hinh_ve.png",
                            mime="image/png",
                            use_container_width=True
                        )
                    with dcol2:
                        st.download_button(
                            label="Tải ảnh JPEG",
                            data=img_data["jpeg"],
                            file_name="tikz_hinh_ve.jpg",
                            mime="image/jpeg",
                            use_container_width=True
                        )
                    with dcol3:
                        st.download_button(
                            label="Tải file PDF",
                            data=img_data["pdf"],
                            file_name="tikz_hinh_ve.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    st.error(f"❌ {str(e)}")

# TAB 2: CHUYỂN TÀI LIỆU TOÀN DIỆN SANG WORD
with tab2:
    st.subheader("Chuyển toàn bộ file/mã LaTeX sang Word (.docx)")
    c1, c2 = st.columns([1, 1])
    with c1:
        uploaded_doc = st.file_uploader("📁 Tải file .tex lên", type=["tex", "txt"], key="doc_uploader")
        doc_text = st.text_area("Hoặc dán toàn bộ tài liệu LaTeX tại đây:", height=200, key="doc_text")
        btn_convert_doc = st.button("🚀 Bắt đầu chuyển đổi sang Word", type="primary", key="btn_doc")

    raw_doc = ""
    if uploaded_doc is not None:
        raw_doc = uploaded_doc.read().decode("utf-8", errors="ignore")
    elif doc_text.strip():
        raw_doc = doc_text

    if btn_convert_doc and raw_doc.strip():
        with st.spinner("Đang xử lý toàn bộ tài liệu và phương trình MathML..."):
            try:
                docx_bytes, preview_html, total_img = process_latex_document(raw_doc)
                st.session_state["full_docx"] = docx_bytes
                st.session_state["full_preview"] = preview_html
                st.success(f"✅ Chuyển đổi thành công! Đã tự động vẽ {total_img} hình TikZ.")
            except Exception as e:
                st.error(f"❌ {str(e)}")

    with c2:
        if "full_docx" in st.session_state:
            st.markdown("### 📥 Tải File Word")
            st.download_button(
                label="📥 Tải file Word (.docx)",
                data=st.session_state["full_docx"],
                file_name="Tai_Lieu_Word.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True
            )

    st.markdown("---")
    st.subheader("📑 Bản Xem Trước Trang Tài Liệu A4 (Kèm nút Copy sang Word)")
    if "full_preview" in st.session_state:
        st.components.v1.html(st.session_state["full_preview"], height=900, scrolling=True)