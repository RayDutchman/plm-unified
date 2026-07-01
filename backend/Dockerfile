FROM python:3.12-slim

WORKDIR /app

# 系统依赖:
#   libGL/xvfb 等 — Mayo OpenGL 需求
#   libreoffice(soffice) — Office(doc/docx/ppt/pptx/xls/xlsx) 转 PDF 预览
#   fonts-noto-cjk — 保证中文文档转 PDF 时不缺字
RUN apt-get update -qqy && apt-get install -qqy --no-install-recommends \
        xvfb libgl1 libfontconfig1 libxkbcommon0 libglib2.0-0 libegl1 \
        libreoffice fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Mayo CLI (OCC原生STEP→GLB转换) — AppImage 提取模式（无需FUSE）
COPY MayoConv-0.9.0-x86_64.AppImage /tmp/MayoConv
RUN chmod +x /tmp/MayoConv && cd /tmp && /tmp/MayoConv --appimage-extract && mv /tmp/squashfs-root /opt/mayo && printf '#!/bin/sh\nexec /opt/mayo/AppRun "$@"' > /usr/local/bin/MayoConv && chmod +x /usr/local/bin/MayoConv && mkdir -p /app/mayo_settings && rm /tmp/MayoConv

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY app/ ./app/
COPY alembic.ini .
COPY migrations/ ./migrations/

# 启动
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
