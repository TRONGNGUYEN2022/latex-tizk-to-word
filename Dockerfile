FROM python:3.10-slim-bookworm

# Cài đặt trọn bộ TeX Live tối ưu cho TikZ và công cụ xử lý ảnh PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-pictures \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    texlive-latex-extra \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt các thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn ứng dụng
COPY . .

# Mở cổng mặc định của Render
EXPOSE 10000

# Lệnh khởi chạy ứng dụng Streamlit
CMD ["sh", "-c", "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"]
