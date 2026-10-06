FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    TMPDIR=/tmp

RUN set -eux; \
    echo 'bot:x:10001:' >> /etc/group; \
    echo 'bot:x:10001:10001:3xui bot runtime:/nonexistent:/usr/sbin/nologin' >> /etc/passwd

WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY . .
# Build context modes depend on the checkout umask. Keep application code
# root-owned but normalize it to be readable/traversable by the non-root runtime.
RUN set -eux; \
    chown -R 0:0 /app; \
    chmod -R u=rwX,go=rX /app

USER 10001:10001
ENTRYPOINT ["python", "restore_bootstrap.py"]
