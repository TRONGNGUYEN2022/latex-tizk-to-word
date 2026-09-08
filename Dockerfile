FROM python:3.10-slim-bookworm

# Cài đặt chính xác các gói cần thiết:
# - texlive-latex-base, texlive-pictures, texlive-latex-recommended: Core LaTeX & TikZ
# - texlive-latex-extra: standalone.cls
# - texlive-lang-other: t5enc.def (hỗ trợ tiếng Việt T5)
# - texlive-fonts-recommended: Phông chữ chuẩn
# - poppler-utils: Chuyển đổi PDF sang ảnh
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-pictures \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-lang-other \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000
CMD ["sh", "-c", "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"]
