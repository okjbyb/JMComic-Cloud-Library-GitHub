FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JM_LIBRARY_DIR=/data/pdf

WORKDIR /app

RUN sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 update \
    && apt-get install -y --no-install-recommends ghostscript \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 jmcomic \
    && useradd --uid 10001 --gid jmcomic --shell /usr/sbin/nologin jmcomic \
    && mkdir -p /data/pdf /data/.pdf-temp \
    && chown -R jmcomic:jmcomic /data

COPY requirements.txt ./
RUN pip install --no-cache-dir \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

COPY src ./src
COPY app.py cloud_ui.html login.html register.html account.html reader.html LICENSE ./

USER jmcomic
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/login', timeout=3)" || exit 1

CMD ["python", "app.py", "--port", "8765", "--no-browser"]
