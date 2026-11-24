# Review-Oberfläche inkl. Pipeline (Playwright/Chromium für das Rendering).
# Bauen:   docker build -t creative-automation-agent .
# Starten: docker run --rm -p 127.0.0.1:8501:8501 --env-file .env creative-automation-agent
# bookworm (Debian 12): von Playwright offiziell unterstützt; «slim» ohne Zusatz ist inzwischen Debian 13
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

# Erst nur die Abhängigkeiten (gut gecacht), dann der Code
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --no-install-project
# Diagnose: welche Python-Umgebung wird genutzt? Bricht klar ab, falls Playwright fehlt
RUN /app/.venv/bin/python -c "import sys, playwright; print(sys.executable, playwright.__file__)"
RUN /app/.venv/bin/python -m playwright install --with-deps chromium

COPY src ./src
COPY skills ./skills
COPY templates ./templates
COPY eval ./eval
COPY tests/fixtures ./tests/fixtures
COPY .streamlit ./.streamlit
RUN uv sync --frozen --no-dev

# Nicht als root laufen
RUN useradd --create-home app && mkdir -p output data && chown -R app:app output data
USER app

EXPOSE 8501
# Im Container auf allen Schnittstellen lauschen; nach aussen nur via 127.0.0.1-Portfreigabe
CMD ["streamlit", "run", "src/creative_agent/review/app.py", "--server.address=0.0.0.0"]
