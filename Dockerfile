FROM python:3.10-slim-bookworm

# Cài đặt trọn bộ TeX Live đầy đủ (texlive-full) chứa mọi gói, class, font và bảng mã (bao gồm cả T5)
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-full \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000
CMD ["sh", "-c", "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"]
