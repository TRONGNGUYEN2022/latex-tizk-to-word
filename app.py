import streamlit as st
import os
import re
import subprocess
import tempfile
import shutil
import base64
from pdf2image import convert_from_path
import pypandoc

st.set_page_config(page_title="LaTeX (TikZ) to Word Pro", layout="wide")

def compile_single_tikz(tikz_code, output_dir, img_index):
    """Biên dịch khối TikZ thành ảnh PNG nét cao 300 DPI"""
    tex_content = f"""\\documentclass[border=4mm]{{standalone}}
\\usepackage[utf8]{{vietnam}}
\\usepackage{{amsmath,amssymb,amsfonts}}
\\usepackage{{tikz}}
\\usepackage{{tkz-euclide}}
\\usepackage{{pgfplots}}
\\pgfplotsset{{compat=1.18}}
\\usetikzlibrary{{calc,angles,quotes,patterns,intersections}}
\\begin{{document}}
{tikz_code}
\\end{{document}}
"""
    job_name = f"tikz_img_{img_index}"
    tex_file = os.path.join(output_dir, f"{job_name}.tex")
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(tex_content)
        
    cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={output_dir}", tex_file]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    pdf_file = os.path.join(output_dir, f"{job_name}.pdf")
    img_path = os.path.join(output_dir, f"{job_name}.png")
    
    if os.path.exists(pdf_file):
        try:
            images = convert_from_path(pdf_file, dpi=300)
            if images:
                images[0].save(img_path, "PNG")
                return img_path
        except Exception:
            return None
    return None

def convert_latex_to_html_preview(tex_file, temp_dir):
    """Chuyển đổi TeX sang HTML dạng A4 kèm MathJax và ảnh Base64"""
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
            justify-content: center;
            font-family: "Times New Roman", Times, serif;
        }}
        .a4-page {{
            background-color: white;
            width: 100%;
            max-width: 800px;
            min-height: 1000px;
            padding: 50px 60px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
            font-size: 15.5px;
            line-height: 1.6;
            color: #111;
            box-sizing: border-box;
        }}
        img {{
            max-width: 85%;
            height: auto;
            display: block;
            margin: 15px auto;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }}
        th, td {{
            border: 1px solid #333;
            padding: 6px 10px;
            text-align: left;
        }}
    </style>
</head>
<body>
    <div class="a4-page">
        {html_body}
    </div>
</body>
</html>
"""
        b64_html = base64.b64encode(standalone_html.encode('utf-8')).decode('utf-8')
        iframe_tag = f'<iframe src="data:text/html;base64,{b64_html}" style="width:100%; height:850px; border:none; border-radius:8px;"></iframe>'
        return iframe_tag
    except Exception as e:
        return f"<p style='color:red;'>Lỗi xem trước: {str(e)}</p>"

def process_latex(raw_tex):
    temp_dir = tempfile.mkdtemp()
    try:
        tikz_pattern = re.compile(r"(\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\})")
        parts = tikz_pattern.split(raw_tex)
        reconstructed_tex = []
        img_counter = 0

        for part in parts:
            if part.startswith(r"\begin{tikzpicture}") and part.endswith(r"\end{tikzpicture}"):
                img_path = compile_single_tikz(part, temp_dir, img_counter)
                if img_path:
                    norm_path = img_path.replace("\\", "/")
                    reconstructed_tex.append(f"\n\\begin{{center}}\\includegraphics[width=0.48\\textwidth]{{{norm_path}}}\\end{{center}}\n")
                    img_counter += 1
                else:
                    reconstructed_tex.append(part)
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

# Giao diện Streamlit
st.title("📄 Chuyển đổi LaTeX TikZ sang Word (.docx)")
st.markdown("Chuyển đổi công thức sang chuẩn **Word Equation (MathML)** và tự động vẽ **TikZ thành ảnh nét cao**.")

col1, col2 = st.columns([1, 1])

with col1:
    uploaded_file = st.file_uploader("📁 Tải file .tex lên", type=["tex", "txt"])
    text_input = st.text_area("Hoặc dán trực tiếp mã LaTeX vào đây:", height=250)
    btn_convert = st.button("🚀 Bắt đầu chuyển đổi", type="primary")

raw_latex = ""
if uploaded_file is not None:
    raw_latex = uploaded_file.read().decode("utf-8", errors="ignore")
elif text_input.strip():
    raw_latex = text_input

if btn_convert:
    if not raw_latex.strip():
        st.warning("⚠️ Vui lòng tải file hoặc dán mã LaTeX!")
    else:
        with st.spinner("Đang biên dịch TikZ và sinh tài liệu..."):
            try:
                docx_bytes, preview_html, total_img = process_latex(raw_latex)
                st.session_state["docx_bytes"] = docx_bytes
                st.session_state["preview_html"] = preview_html
                st.session_state["total_img"] = total_img
                st.success(f"✅ Đã xử lý thành công {total_img} hình TikZ!")
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")

with col2:
    if "docx_bytes" in st.session_state:
        st.download_button(
            label="📥 Tải file Word (.docx)",
            data=st.session_state["docx_bytes"],
            file_name="Tai_Lieu_Word.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary"
        )

st.markdown("---")
st.subheader("📑 Bản Xem Trước Trang Tài Liệu (A4 / Word Preview)")
if "preview_html" in st.session_state:
    st.components.v1.html(st.session_state["preview_html"], height=870, scrolling=True)
else:
    st.info("Nội dung tài liệu và công thức sau khi chuyển đổi sẽ hiển thị tại đây.")