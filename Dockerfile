FROM python:3.10-slim

# Cài đặt bộ công cụ LaTeX và hệ thống (đã bỏ gói lang-vietnamese bị lỗi)
RUN apt-get update && apt-get install -y \
    texlive-latex-base \
    texlive-pictures \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000
CMD ["sh", "-c", "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"]
