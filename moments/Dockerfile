FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY data ./data
COPY scripts ./scripts
COPY static ./static
# Utilisateur non-root
RUN useradd --create-home --uid 10001 moments && chown -R moments /app
USER moments
# Les données de démo sont générées au démarrage (SECRET_KEY et DEMO_PASSWORD viennent de l'environnement)
CMD python -m data.generate && python -m scripts.simulate_feedback && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
