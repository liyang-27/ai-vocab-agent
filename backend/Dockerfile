# ① 使用官方 Python 3.11 轻量镜像
FROM python:3.11-slim

# ② 设置工作目录
WORKDIR /app

# ③ 安装 FAISS 依赖的系统库（避免报 libgomp 错误）
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# ④ 复制依赖文件并安装 Python 包
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# ⑤ 复制当前目录下所有后端代码到容器 /app
COPY . .

# ⑥ 创建 data 目录（用于挂载持久数据）
RUN mkdir -p /app/data

# ⑦ 声明端口
EXPOSE 8000

# ⑧ 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]