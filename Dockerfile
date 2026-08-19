# EmoQunt 镜像：Python 运行（单镜像直托宿主机预构建的 frontend/dist，零 CORS）
# 构建：
#   cd frontend && npm run build   # 宿主机预构建（国内网络无需拉取 node 镜像）
#   docker compose build            # 推荐，或 docker build -t emoqunt .
# 运行：docker compose up -d && docker compose logs -f app
#
# 国内镜像加速：Docker Desktop → Settings → Docker Engine 中配置 registry-mirrors，
# 例如 "registry-mirrors": ["https://docker.m.daocloud.io", "https://1ms.run"]。
# 本 Dockerfile 基础镜像已改用 daocloud 前缀，pip 源默认走清华，可用 --build-arg PIP_INDEX_URL 覆盖。

FROM docker.m.daocloud.io/library/python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_PROGRESS_BAR=off
# 国内 pip 镜像（构建时可用 --build-arg PIP_INDEX_URL 覆盖）
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.txt ./
RUN pip install -i ${PIP_INDEX_URL} --trusted-host pypi.tuna.tsinghua.edu.cn -r requirements.txt
COPY . ./
# frontend/dist 由 .dockerignore 排除，需宿主机预构建后随 COPY . 一并带入；
# 若 dist 不存在，容器内 /spa/* 将返回 503（web_app.py 的 fallback）。
EXPOSE 8000
# 非 root 运行（与 compose 的 cap_drop/no-new-privileges 配合）
RUN useradd -m app && chown -R app:app /app
USER app
HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=30s CMD python -c "import os,urllib.request,sys; p=os.environ.get('QDT_WEB_PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://localhost:{p}/api/health', timeout=5).status==200 else 1)"
CMD ["python", "web_app.py", "--host", "0.0.0.0"]
