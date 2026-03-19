# AceiteDirecto — Outreach Automatizado

Secuencia de contacto con almazaras: Email 1 → Email 2 → Email 3 → WhatsApp pendiente.
Se integra directamente con Airtable y manda un resumen por email cada día.

---

## Instalación

```bash
pip install requests python-dotenv colorama
```

Copia `.env.example` a `.env` y rellena tus credenciales.

---

## Uso manual

```bash
# Simular sin mandar nada (recomendado la primera vez)
python aceite_outreach.py --dry-run

# Ejecución real
python aceite_outreach.py

# Ver estado del CRM sin hacer nada
python aceite_outreach.py --resumen
```

---

## Cron en el servidor — solo lunes a viernes, 9:00 Madrid

```bash
crontab -e
```

Añade una de estas líneas según la época del año:

```
# INVIERNO (UTC+1) — de finales de octubre a finales de marzo
0 8 * * 1-5 cd /ruta/aceite && python3 aceite_outreach.py >> /dev/null 2>&1

# VERANO (UTC+2) — de finales de marzo a finales de octubre
0 7 * * 1-5 cd /ruta/aceite && python3 aceite_outreach.py >> /dev/null 2>&1
```

El `1-5` al final es lo que limita a lunes-viernes.
El script también lleva una comprobación interna como doble seguridad.

---

## Pipeline de estados en Airtable

```
🔍 Detectada
    ↓  (tú cambias manualmente a "Por contactar")
📋 Por contactar
    ↓  (script — día 1)
📧 Email 1 enviado
    ↓  (script — +7 días sin respuesta)
📧 Email 2 enviado
    ↓  (script — +7 días sin respuesta)
📧 Email 3 enviado
    ↓  (script — +2 días sin respuesta)
📱 WhatsApp pendiente   ← tú mandas el WA manualmente
    ↓
📱 WhatsApp enviado
    ↓
💬 En conversación  /  ❌ No interesa
    ↓
✅ Partner activo
```

---

## Logs

Los logs se guardan en `./logs/outreach.log` con rotación automática (máx 5 MB × 3 archivos).
Cada día recibes también un email de resumen en HTML con todo lo que pasó.

---

## Variables configurables en el script

| Variable | Valor por defecto | Qué hace |
|---|---|---|
| `MAX_ENVIOS` | 10 | Máximo emails por ejecución |
| `PAUSA_ENTRE_ENVIOS` | 4 seg | Pausa entre emails |
| `DIAS_E1_E2` | 7 | Días entre Email 1 y 2 |
| `DIAS_E2_E3` | 7 | Días entre Email 2 y 3 |
| `DIAS_E3_WA` | 2 | Días entre Email 3 y marcar WhatsApp |
