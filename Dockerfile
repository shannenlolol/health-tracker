FROM python:3.14-slim
# Run the bot as an unprivileged user. The app files stay root-owned and
# read-only to it, so a compromised bot cannot alter its own code.
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
USER app
CMD ["python", "-m", "app.main"]
