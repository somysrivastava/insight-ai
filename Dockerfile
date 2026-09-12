# Dev image — runs the app with --reload against a bind-mounted source
# tree (see docker-compose.yml). A leaner multi-stage, non-root, no-reload
# variant is planned for the Day 21 production build; this one optimizes
# for fast local iteration, not image size or hardening.
FROM python:3.14.5-slim-bookworm

WORKDIR /app

# Dependencies first so this layer only rebuilds when requirements.txt
# actually changes, not on every source edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
