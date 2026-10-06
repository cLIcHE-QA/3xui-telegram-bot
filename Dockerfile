FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    TMPDIR=/tmp

RUN set -eux; \
    echo 'bot:x:10001:' >> /etc/group; \
    echo 'bot:x:10001:10001:3xui bot runtime:/nonexistent:/usr/sbin/nologin' >> /etc/passwd

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=10001:10001 . .

USER 10001:10001
ENTRYPOINT ["python", "restore_bootstrap.py"]
