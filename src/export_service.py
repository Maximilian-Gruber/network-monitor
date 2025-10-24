import os, time, pandas as pd, smtplib, threading, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text
from flask import Flask

EXPORT_INTERVAL_HOURS = int(os.getenv("EXPORT_INTERVAL_HOURS", 12))
EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")
DATABASE_URL = os.getenv("DATABASE_URL")
EMAIL_TO = [email.strip() for email in os.getenv("EMAIL_TO", "").split(",") if email.strip()]
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

os.makedirs(EXPORT_DIR, exist_ok=True)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
logging.basicConfig(level=logging.INFO, format='[EXPORT] %(asctime)s %(message)s')

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ping_stats (
                id SERIAL PRIMARY KEY,
                target TEXT,
                timestamp TEXT,
                total_pings INTEGER,
                timeouts INTEGER,
                avg_latency DOUBLE PRECISION,
                max_latency DOUBLE PRECISION
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS export_checkpoint (
                id SERIAL PRIMARY KEY,
                last_export TIMESTAMP
            );
        """))
        last = conn.execute(text("SELECT last_export FROM export_checkpoint ORDER BY id DESC LIMIT 1")).fetchone()
        if last is None:
            conn.execute(text("INSERT INTO export_checkpoint (last_export) VALUES (:ts)"), {"ts": datetime.now(timezone.utc)})

def get_last_export_time():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT last_export FROM export_checkpoint ORDER BY id DESC LIMIT 1")).fetchone()
        return result[0] if result else datetime.now(timezone.utc)

def update_last_export_time(ts):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO export_checkpoint (last_export) VALUES (:ts)"), {"ts": ts})

def export_and_send():
    logging.info(f"Service started. Export every {EXPORT_INTERVAL_HOURS} hours.")
    while True:
        time.sleep(EXPORT_INTERVAL_HOURS * 3600)
        try:
            last_export = get_last_export_time()
            now = datetime.now(timezone.utc)
            csv_path = f"{EXPORT_DIR}/pings_{now.strftime('%Y%m%d_%H%M')}.csv"

            with engine.connect() as conn:
                df = pd.read_sql_query(
                    text("SELECT * FROM pings WHERE timestamp > :since"),
                    conn,
                    params={"since": last_export.strftime("%Y-%m-%d %H:%M:%S")},
                )

            if not df.empty:
                df['latency'] = pd.to_numeric(df['latency'], errors='coerce')
                df.to_csv(csv_path, index=False, float_format="%.3f")
                logging.info(f"CSV exported: {csv_path}")

            stats = df.groupby("target").agg(
                total_pings=pd.NamedAgg(column="latency", aggfunc="count"),
                timeouts=pd.NamedAgg(column="latency", aggfunc=lambda x: x.isna().sum()),
                avg_latency=pd.NamedAgg(column="latency", aggfunc="mean"),
                max_latency=pd.NamedAgg(column="latency", aggfunc="max")
            ).reset_index()

            if not stats.empty:
                with engine.begin() as conn:
                    for _, row in stats.iterrows():
                        conn.execute(text("""
                            INSERT INTO ping_stats (target, timestamp, total_pings, timeouts, avg_latency, max_latency)
                            VALUES (:target, :timestamp, :total_pings, :timeouts, :avg_latency, :max_latency)
                        """), {
                            "target": row["target"],
                            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                            "total_pings": int(row["total_pings"]),
                            "timeouts": int(row["timeouts"]),
                            "avg_latency": float(row["avg_latency"]) if not pd.isna(row["avg_latency"]) else None,
                            "max_latency": float(row["max_latency"]) if not pd.isna(row["max_latency"]) else None
                        })

                send_email(csv_path, stats)
            update_last_export_time(now)

        except Exception as e:
            logging.error(f"Export failed: {e}")
            time.sleep(60)

def send_email(csv_path, stats_df):
    if not EMAIL_TO or not EMAIL_FROM or not EMAIL_PASS:
        logging.warning("Email not configured, skipping send.")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_FROM
        msg["To"] = ", ".join(EMAIL_TO)
        now = datetime.now(timezone.utc)
        msg["Subject"] = f"Network Report - {now.strftime('%Y%m%d_%H%M')}"

        body = "Automatically generated network report:\n\n"
        body += stats_df.to_string(index=False)
        msg.attach(MIMEText(body, "plain"))

        if os.path.exists(csv_path):
            with open(csv_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(csv_path))
            part["Content-Disposition"] = f'attachment; filename="{os.path.basename(csv_path)}"'
            msg.attach(part)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASS)
            for recipient in EMAIL_TO:
                server.sendmail(EMAIL_FROM, recipient, msg.as_string())
                logging.info(f"Mail sent to {recipient}.")
    except Exception as e:
        logging.error(f"Mail send failed: {e}")

app = Flask(__name__)
@app.route("/health")
def health():
    return "OK", 200

def run_health():
    app.run(host="0.0.0.0", port=5050)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_health, daemon=True).start()
    threading.Thread(target=export_and_send, daemon=True).start()
    while True:
        time.sleep(60)
        logging.info("Heartbeat: export service running.")
