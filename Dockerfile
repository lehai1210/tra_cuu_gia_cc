# Sử dụng một Python image chính thức làm base image
FROM python:3.11-slim

# Đặt thư mục làm việc bên trong container
WORKDIR /app

# Sao chép file requirements.txt vào thư mục làm việc
# Quan trọng: Chỉ sao chép requirements.txt trước để tận dụng Docker cache
# Nếu requirements.txt không thay đổi, Docker sẽ không cần cài lại thư viện ở các lần build sau
COPY requirements.txt requirements.txt

# Cài đặt các thư viện cần thiết từ requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ code còn lại của dự án vào thư mục làm việc
# Bao gồm main.py, file .env (nếu bạn muốn build nó vào image - không khuyến khích cho key thật)
# Hoặc tốt hơn là không copy .env mà truyền biến môi trường khi chạy container
COPY . .
# Nếu bạn không muốn copy file .env vào image, hãy đảm bảo bạn có file .env mẫu 
# hoặc cấu hình biến môi trường khi chạy container.
# Để đơn giản cho lần đầu, chúng ta có thể copy nó, nhưng hãy cẩn thận với key thật.
# Một cách tốt hơn là không copy .env và truyền biến môi trường lúc chạy.
# COPY main.py .
# (Và các file/thư mục khác nếu có)


# Expose cổng mà FastAPI/Uvicorn sẽ chạy (mặc định là 8000)
EXPOSE 8000

# Lệnh để chạy ứng dụng khi container khởi động
# Sử dụng 0.0.0.0 để có thể truy cập từ bên ngoài container
# PORT sẽ được cung cấp bởi nhiều nền tảng hosting, hoặc bạn có thể đặt mặc định là 8000
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# Hoặc nếu bạn dùng lệnh python main.py để chạy (vì đã có uvicorn.run trong main.py):
CMD ["python", "main.py"] 
# Lưu ý: Khi chạy `python main.py`, bạn cần đảm bảo `uvicorn.run` trong main.py
# được cấu hình để lắng nghe trên host "0.0.0.0" để có thể truy cập từ bên ngoài Docker.
# Sửa trong main.py: uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
# (Bỏ reload=True khi deploy)