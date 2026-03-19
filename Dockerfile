FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aceite_outreach.py .

RUN mkdir -p /app/logs

RUN echo "0 8 * * 1-5 cd /app && python3 aceite_outreach.py >> /proc/1/fd/1 2>&1" | crontab -

CMD ["cron", "-f"]
```

---

**3. Crea el .gitignore** para que el .env no se suba

Crea otro archivo llamado `".gitignore"` (también entre comillas al guardar):
```
.env
logs/
__pycache__/