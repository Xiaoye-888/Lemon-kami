FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.cloud.tencent.com/pypi/simple

COPY . .

# 生产环境默认关闭调试模式
ENV DEBUG=false

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
