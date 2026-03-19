cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aceite_outreach.py .

RUN mkdir -p /app/logs

RUN echo "0 8 * * 1-5 cd /app && python3 aceite_outreach.py >> /proc/1/fd/1 2>&1" | crontab -

# Mantiene el contenedor vivo con cron en primer plano
CMD ["cron", "-f", "-l", "2"]
EOF

git add Dockerfile
git commit -m "Fix cron foreground"
git push