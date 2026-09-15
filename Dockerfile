# Dev image — runs the app with --reload against a bind-mounted source
# tree (see docker-compose.yml). A leaner multi-stage, non-root, no-reload
# variant is planned for the Day 29 production build; this one optimizes
# for fast local iteration, not image size or hardening.
FROM python:3.14.5-slim-bookworm

WORKDIR /app

# WeasyPrint (Day 18, PDF export) needs these native libraries at
# runtime — the Python package installs fine without them, but crashes
# on import with "cannot load library 'libgobject-2.0-0'" the moment
# it's actually used. Confirmed by trying to render a PDF without them
# before adding this.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first so this layer only rebuilds when requirements.txt
# actually changes, not on every source edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
