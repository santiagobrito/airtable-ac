"""
╔══════════════════════════════════════════════════════════════════╗
║         AceiteDirecto — Outreach Automatizado v1.2              ║
║         Email 1 → Email 2 → Email 3 → WhatsApp pendiente        ║
║         + Resumen diario por email a Santiago                    ║
║         + Solo lunes a viernes (doble seguridad)                 ║
╚══════════════════════════════════════════════════════════════════╝

INSTALACIÓN:
    pip install requests python-dotenv colorama

CONFIGURACIÓN:
    Copia .env.example a .env y rellena tus credenciales.

CRON EN EL SERVIDOR (solo L-V, 9:00 Madrid):
    Invierno (UTC+1):  0 8 * * 1-5 cd /ruta/aceite && python3 aceite_outreach.py
    Verano   (UTC+2):  0 7 * * 1-5 cd /ruta/aceite && python3 aceite_outreach.py

USO MANUAL:
    python aceite_outreach.py            → ejecución real
    python aceite_outreach.py --dry-run  → simula sin tocar nada
    python aceite_outreach.py --resumen  → muestra estado del CRM
"""

import smtplib, time, logging, argparse, sys, os, requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)
load_dotenv()

# ══════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN — edita aquí o en el .env
# ══════════════════════════════════════════════════════════════════

AIRTABLE_API_KEY  = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID  = "applseF2kAh5CHY1k"
AIRTABLE_TABLE_ID = "tblLxid5wJ7iLTapr"

# IDs de campos Airtable
FIELD_NOMBRE      = "flduanUvc5bpvdvJh"
FIELD_EMAIL       = "fldB7bUDEZyiBecm0"
FIELD_ESTADO      = "fldSNkEpEXsegEdrE"
FIELD_ULTIMO_CONT = "fldbj7UJf0Q72kmVS"
FIELD_TELEFONO    = "fldSyhbYs3lUw0j0a"

# Pipeline de estados
ESTADO_POR_CONTACTAR = "📋 Por contactar"
ESTADO_EMAIL1        = "📧 Email 1 enviado"
ESTADO_EMAIL2        = "📧 Email 2 enviado"
ESTADO_EMAIL3        = "📧 Email 3 enviado"
ESTADO_WA_PENDIENTE  = "📱 WhatsApp pendiente"
ESTADO_WA_ENVIADO    = "📱 WhatsApp enviado"
ESTADO_CONVERSACION  = "💬 En conversación"
ESTADO_NO_INTERESA   = "❌ No interesa"
ESTADO_PARTNER       = "✅ Partner activo"

# Días de espera entre pasos
DIAS_E1_E2   = 7
DIAS_E2_E3   = 7
DIAS_E3_WA   = 2

# SMTP
SMTP_HOST     = os.getenv("SMTP_HOST")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_NAME     = "Santiago · AceiteDirecto"
FROM_EMAIL    = SMTP_USER

# Email donde recibes el resumen diario (por defecto el mismo SMTP)
RESUMEN_EMAIL = os.getenv("RESUMEN_EMAIL", SMTP_USER)

# Límites de envío
MAX_ENVIOS         = 10   # máximo emails por ejecución
PAUSA_ENTRE_ENVIOS = 4    # segundos entre cada email

# Logs
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
LOG_DIR     = os.path.join(BASE_DIR, "logs")
LOG_ARCHIVO = os.path.join(LOG_DIR, "outreach.log")

# ══════════════════════════════════════════════════════════════════
#  LOGGING — colores en consola + archivo rotativo
# ══════════════════════════════════════════════════════════════════

os.makedirs(LOG_DIR, exist_ok=True)

class ColorFormatter(logging.Formatter):
    COLORES = {
        logging.DEBUG:    Fore.CYAN,
        logging.INFO:     Fore.WHITE,
        logging.WARNING:  Fore.YELLOW,
        logging.ERROR:    Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }
    def format(self, record):
        c  = self.COLORES.get(record.levelno, Fore.WHITE)
        ts = datetime.now().strftime("%H:%M:%S")
        return f"{Fore.LIGHTBLACK_EX}{ts}{Style.RESET_ALL}  {c}{record.getMessage()}{Style.RESET_ALL}"

class PlainFormatter(logging.Formatter):
    def format(self, record):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"{ts}  {record.levelname:<8}  {record.getMessage()}"

def setup_logger():
    log = logging.getLogger("aceite")
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(ColorFormatter())
    fh = RotatingFileHandler(LOG_ARCHIVO, maxBytes=5*1024*1024,
                             backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(PlainFormatter())
    log.addHandler(ch)
    log.addHandler(fh)
    return log

log = setup_logger()

def sep(c="═", n=62): log.info(c * n)
def titulo(t):        sep(); log.info(f"  {t}"); sep()
def subtitulo(t):     log.info(f"\n  ── {t} ──")

# ══════════════════════════════════════════════════════════════════
#  TEMPLATES DE OUTREACH
# ══════════════════════════════════════════════════════════════════

EMAILS = {
    1: {
        "asunto": "Tu aceite merece llegar directamente a quien lo va a valorar",
        "cuerpo": lambda n: f"""Hola,

Soy Santiago. Estoy construyendo AceiteDirecto.com, y cuando encontré {n} me pareció exactamente el tipo de productor que tiene sentido en el proyecto.

La idea es simple: un marketplace donde el cliente compra, vosotros enviáis, y el aceite llega con nombre y apellidos — no como «aceite de Jaén genérico». Cada almazara tiene su propio espacio: historia, descripción, referencias. Lo que hacéis bien, bien explicado.

Yo me encargo de la tienda, el posicionamiento SEO y la publicidad. Vosotros vendéis a precio especial y el margen funciona para los dos sin comisiones de por medio.

No os pido nada todavía. Solo quería saber si esto resuena con lo que estáis intentando hacer con la venta online, o si ya tenéis ese canal cubierto.

¿Le damos una vuelta?

Saludos,
Santiago
AceiteDirecto.com"""
    },
    2: {
        "asunto": "Re: Tu aceite merece llegar directamente a quien lo va a valorar",
        "cuerpo": lambda n: f"""Hola de nuevo,

Te escribí hace unos días sobre AceiteDirecto.com — por si se perdió entre los correos.

En resumen: un canal de venta directa online para {n}, sin comisiones de intermediarios, donde yo pongo el escaparate y vosotros el producto.

¿Tiene sentido para vosotros o no encaja ahora mismo?

Saludos,
Santiago
AceiteDirecto.com"""
    },
    3: {
        "asunto": "Último mensaje — AceiteDirecto.com",
        "cuerpo": lambda n: f"""Hola,

Tercer y último intento — no quiero molestar más.

Si en algún momento queréis explorar un canal online propio sin comisiones para {n}, aquí estaré.

Mucho ánimo con la campaña.

Santiago
AceiteDirecto.com"""
    }
}

# ══════════════════════════════════════════════════════════════════
#  AIRTABLE
# ══════════════════════════════════════════════════════════════════

def _h():
    return {"Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json"}

def get_registros():
    url     = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
    records = []
    params  = {"pageSize": 100, "returnFieldsByFieldId": "true"}
    while True:
        r = requests.get(url, headers=_h(), params=params)
        r.raise_for_status()
        data = r.json()
        for rec in data.get("records", []):
            f      = rec.get("fields", {})
            nombre = f.get(FIELD_NOMBRE, "").strip()
            email  = f.get(FIELD_EMAIL,  "").strip()
            er     = f.get(FIELD_ESTADO)
            estado = er.get("name", "") if isinstance(er, dict) else (er or "")
            if nombre and email and "@" in email:
                records.append({
                    "id":          rec["id"],
                    "nombre":      nombre,
                    "email":       email,
                    "estado":      estado,
                    "ultimo_cont": f.get(FIELD_ULTIMO_CONT, ""),
                    "telefono":    f.get(FIELD_TELEFONO, ""),
                })
        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset
    return records

def actualizar_estado(record_id, nuevo_estado):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}/{record_id}"
    requests.patch(url, headers=_h(), json={
        "fields": {
            FIELD_ESTADO:      nuevo_estado,
            FIELD_ULTIMO_CONT: date.today().isoformat()
        }
    }).raise_for_status()

def dias_desde(fecha_str):
    if not fecha_str: return 999
    try:   return (date.today() - date.fromisoformat(fecha_str[:10])).days
    except: return 999

# ══════════════════════════════════════════════════════════════════
#  SMTP GENÉRICO
# ══════════════════════════════════════════════════════════════════

def enviar_smtp(destinatario, asunto, texto=None, html=None, from_name=None):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = f"{from_name or FROM_NAME} <{FROM_EMAIL}>"
    msg["To"]      = destinatario
    if texto: msg.attach(MIMEText(texto, "plain", "utf-8"))
    if html:  msg.attach(MIMEText(html,  "html",  "utf-8"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo(); s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(FROM_EMAIL, destinatario, msg.as_string())
        return True
    except Exception as e:
        log.error(f"    ✗ SMTP error: {e}")
        return False

# ══════════════════════════════════════════════════════════════════
#  EMAIL DE RESUMEN DIARIO A SANTIAGO
# ══════════════════════════════════════════════════════════════════

def construir_html_resumen(stats, dry_run):
    hoy  = datetime.now().strftime("%d/%m/%Y")
    hora = datetime.now().strftime("%H:%M")
    modo = "🧪 DRY RUN — nada real enviado" if dry_run else "✅ Ejecución real"

    t_emails = sum(len(stats.get(k, [])) for k in ["email1", "email2", "email3"])
    t_wa     = len(stats.get("wa",      []))
    t_err    = len(stats.get("errores", []))

    def filas_tabla(items, icono):
        if not items:
            return ("<tr><td colspan='2' style='color:#bbb;font-size:13px;"
                    "padding:6px 0;font-style:italic'>— ninguna —</td></tr>")
        return "".join(
            f"<tr>"
            f"<td style='padding:5px 16px 5px 0;font-size:14px'>"
            f"  {icono} <b>{i['nombre']}</b>"
            f"</td>"
            f"<td style='color:#777;font-size:13px'>{i['email']}</td>"
            f"</tr>"
            for i in items
        )

    secciones = ""
    for label, key, icono, color in [
        ("Email 1 enviado",  "email1",  "📧", "#16a34a"),
        ("Email 2 enviado",  "email2",  "📧", "#2563eb"),
        ("Email 3 enviado",  "email3",  "📧", "#7c3aed"),
        ("WhatsApp marcado", "wa",      "📱", "#ea580c"),
        ("Errores de envío", "errores", "❌", "#dc2626"),
    ]:
        items = stats.get(key, [])
        if not items and key != "errores":
            continue
        secciones += f"""
        <h3 style='margin:24px 0 8px;font-size:12px;font-weight:700;
                   color:{color};text-transform:uppercase;letter-spacing:.8px'>
            {label}
            <span style='font-weight:400;color:#aaa'>({len(items)})</span>
        </h3>
        <table style='width:100%;border-collapse:collapse'>
            {filas_tabla(items, icono)}
        </table>
        <hr style='border:none;border-top:1px solid #f0f0f0;margin:14px 0 0'>
        """

    # Tarjetas de métricas
    def card(valor, label, bg, color_num):
        return (
            f"<td style='width:33.3%;padding-right:10px'>"
            f"<div style='background:{bg};border-radius:10px;padding:16px;text-align:center'>"
            f"<div style='font-size:28px;font-weight:700;color:{color_num}'>{valor}</div>"
            f"<div style='font-size:11px;color:#777;margin-top:4px;text-transform:uppercase;"
            f"letter-spacing:.5px'>{label}</div>"
            f"</div></td>"
        )

    # Pills del pipeline
    pipeline = stats.get("pipeline", {})
    orden_pipeline = [
        ESTADO_POR_CONTACTAR, ESTADO_EMAIL1, ESTADO_EMAIL2, ESTADO_EMAIL3,
        ESTADO_WA_PENDIENTE, ESTADO_WA_ENVIADO, ESTADO_CONVERSACION,
        "🤝 Interesado", ESTADO_NO_INTERESA, ESTADO_PARTNER, "🔍 Detectada",
    ]
    pills = ""
    for estado in orden_pipeline:
        n = pipeline.get(estado, 0)
        if n > 0:
            pills += (
                f"<span style='display:inline-block;background:#f5f5f5;"
                f"border-radius:20px;padding:5px 14px;margin:3px 3px 3px 0;"
                f"font-size:13px;color:#333'>{estado} <b>{n}</b></span>"
            )

    html = f"""
    <html>
    <body style='margin:0;padding:0;background:#efefef;font-family:Arial,sans-serif'>
    <div style='max-width:580px;margin:32px auto;border-radius:12px;
                overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,.10)'>

        <!-- CABECERA -->
        <div style='background:#111;padding:28px 32px'>
            <div style='font-size:22px;font-weight:700;color:#fff'>
                🫒 AceiteDirecto
            </div>
            <div style='font-size:13px;color:#888;margin-top:6px'>
                Outreach diario · {hoy} · {hora}
            </div>
        </div>

        <!-- SALUDO -->
        <div style='background:#fff;padding:28px 32px 0'>
            <p style='margin:0;font-size:16px;color:#111;line-height:1.5'>
                Hola Santiago, aquí tienes el resumen de la ejecución de hoy.
            </p>
            <p style='margin:8px 0 0;font-size:13px;color:#999'>{modo}</p>
        </div>

        <!-- MÉTRICAS -->
        <div style='background:#fff;padding:24px 32px'>
            <table style='width:100%;border-collapse:collapse'>
                <tr>
                    {card(t_emails, "emails enviados",    "#f0fdf4", "#16a34a")}
                    {card(t_wa,     "WhatsApp pendiente", "#fff7ed", "#ea580c")}
                    {card(t_err,    "errores",             "#fef2f2", "#dc2626")}
                </tr>
            </table>
        </div>

        <!-- DETALLE POR TIPO -->
        <div style='background:#fff;padding:0 32px 28px;border-top:1px solid #f5f5f5'>
            {secciones}
        </div>

        <!-- PIPELINE -->
        <div style='background:#fafafa;padding:20px 32px;border-top:1px solid #eee'>
            <div style='font-size:11px;font-weight:700;color:#aaa;
                        text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px'>
                Estado del CRM
            </div>
            <div>{pills if pills else '<span style="color:#bbb;font-size:13px">Sin datos</span>'}</div>
        </div>

        <!-- FOOTER -->
        <div style='background:#f0f0f0;padding:14px 32px;border-top:1px solid #e5e5e5;
                    font-size:11px;color:#bbb'>
            Log del servidor:
            <code style='background:#e5e5e5;padding:2px 6px;border-radius:4px;
                         font-size:11px'>{LOG_ARCHIVO}</code>
        </div>

    </div>
    </body>
    </html>
    """
    return html


def enviar_resumen(stats, dry_run):
    hoy        = datetime.now().strftime("%d/%m/%Y")
    t_emails   = sum(len(stats.get(k, [])) for k in ["email1", "email2", "email3"])
    sufijo     = "(DRY RUN)" if dry_run else "enviados"
    asunto     = f"🫒 AceiteDirecto · {hoy} — {t_emails} emails {sufijo}"
    html       = construir_html_resumen(stats, dry_run)

    ok = enviar_smtp(RESUMEN_EMAIL, asunto, html=html, from_name="AceiteDirecto Bot")
    if ok:
        log.info(f"  📬 Resumen enviado a {RESUMEN_EMAIL}")
    else:
        log.error("  ✗ No se pudo enviar el email de resumen")

# ══════════════════════════════════════════════════════════════════
#  LÓGICA PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def es_fin_de_semana():
    return datetime.now().weekday() >= 5  # 5=sábado, 6=domingo

def procesar(dry_run):
    titulo(
        f"AceiteDirecto Outreach  "
        f"{'[DRY RUN]' if dry_run else '[REAL]'}  "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    # ── Doble seguridad: no enviar en fin de semana ────────────────
    if es_fin_de_semana():
        dia = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][datetime.now().weekday()]
        log.warning(f"  📅 Hoy es {dia} — no se envían emails. El cron no debería haber lanzado esto.")
        log.warning("  Revisa tu configuración de cron (debe usar '1-5' para L-V).")
        sep()
        return

    registros = get_registros()
    log.info(f"  📋 Registros cargados de Airtable: {len(registros)}")

    # Clasificar en colas
    c1, c2, c3, cwa = [], [], [], []
    for r in registros:
        e = r["estado"]
        d = dias_desde(r["ultimo_cont"])
        if   e == ESTADO_POR_CONTACTAR:               c1.append(r)
        elif e == ESTADO_EMAIL1 and d >= DIAS_E1_E2:  c2.append(r)
        elif e == ESTADO_EMAIL2 and d >= DIAS_E2_E3:  c3.append(r)
        elif e == ESTADO_EMAIL3 and d >= DIAS_E3_WA:  cwa.append(r)

    subtitulo("Colas detectadas")
    log.info(f"  Email 1 pendientes : {len(c1)}")
    log.info(f"  Email 2 pendientes : {len(c2)}")
    log.info(f"  Email 3 pendientes : {len(c3)}")
    log.info(f"  WhatsApp pendiente : {len(cwa)}")

    stats = {"email1": [], "email2": [], "email3": [], "wa": [], "errores": []}
    total_enviados = 0

    for num, cola, estado_nuevo, key in [
        (1, c1, ESTADO_EMAIL1, "email1"),
        (2, c2, ESTADO_EMAIL2, "email2"),
        (3, c3, ESTADO_EMAIL3, "email3"),
    ]:
        if not cola:
            continue
        subtitulo(f"Email {num}")
        for r in cola:
            if total_enviados >= MAX_ENVIOS:
                log.warning(f"  ⚠ Límite de {MAX_ENVIOS} emails alcanzado. La próxima ejecución continúa.")
                break
            nombre = r["nombre"]
            email  = r["email"]
            log.info(f"  → {nombre:<36} {email}")
            item = {"nombre": nombre, "email": email}

            if dry_run:
                log.info(f"    [DRY RUN] Email {num} no enviado.")
                stats[key].append(item)
                total_enviados += 1
                continue

            t  = EMAILS[num]
            ok = enviar_smtp(email, t["asunto"], texto=t["cuerpo"](nombre))
            if ok:
                actualizar_estado(r["id"], estado_nuevo)
                log.info(f"    ✓ Enviado → {estado_nuevo}")
                stats[key].append(item)
                total_enviados += 1
            else:
                stats["errores"].append(item)

            time.sleep(PAUSA_ENTRE_ENVIOS)

    # WhatsApp pendiente
    if cwa:
        subtitulo("Marcando WhatsApp pendiente")
        for r in cwa:
            tel = r["telefono"] or "(sin teléfono)"
            log.info(f"  📱 {r['nombre']:<36} {tel}")
            if not dry_run:
                actualizar_estado(r["id"], ESTADO_WA_PENDIENTE)
            stats["wa"].append({"nombre": r["nombre"], "email": r["email"]})

    # Snapshot del pipeline para el resumen
    pipeline = {}
    for r in get_registros():
        e = r["estado"] or "Sin estado"
        pipeline[e] = pipeline.get(e, 0) + 1
    stats["pipeline"] = pipeline

    # Resumen en log
    t_env = sum(len(stats[k]) for k in ["email1", "email2", "email3"])
    sep("─")
    log.info("  RESUMEN DE EJECUCIÓN")
    sep("─")
    log.info(f"  Emails enviados  : {t_env}")
    log.info(f"  WA marcados      : {len(stats['wa'])}")
    log.info(f"  Errores          : {len(stats['errores'])}")
    log.info(f"  Modo             : {'DRY RUN' if dry_run else 'REAL'}")
    log.info(f"  Log guardado en  : {LOG_ARCHIVO}")
    sep()

    # Email de resumen a Santiago
    subtitulo("Enviando resumen por email")
    enviar_resumen(stats, dry_run)
    sep()


def resumen_crm():
    titulo(f"Estado del CRM  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    conteo = {}
    for r in get_registros():
        e = r["estado"] or "Sin estado"
        conteo[e] = conteo.get(e, 0) + 1
    orden = [
        ESTADO_POR_CONTACTAR, ESTADO_EMAIL1, ESTADO_EMAIL2, ESTADO_EMAIL3,
        ESTADO_WA_PENDIENTE, ESTADO_WA_ENVIADO, ESTADO_CONVERSACION,
        "🤝 Interesado", ESTADO_NO_INTERESA, ESTADO_PARTNER,
        "🔍 Detectada", "Sin estado",
    ]
    total = 0
    for e in orden:
        n = conteo.pop(e, 0)
        if n:
            barra = "█" * n + "░" * max(0, 40 - n)
            log.info(f"  {e:<32}  {barra}  {n:>3}")
            total += n
    for e, n in conteo.items():
        barra = "█" * n + "░" * max(0, 40 - n)
        log.info(f"  {e:<32}  {barra}  {n:>3}")
        total += n
    sep("─")
    log.info(f"  Total almazaras: {total}")
    sep()

# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AceiteDirecto Outreach")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sin mandar nada ni tocar Airtable")
    parser.add_argument("--resumen", action="store_true",
                        help="Solo muestra el estado actual del CRM")
    args = parser.parse_args()

    if args.resumen:
        resumen_crm()
    else:
        procesar(dry_run=args.dry_run)
