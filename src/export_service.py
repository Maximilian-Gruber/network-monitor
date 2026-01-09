import os, time, pandas as pd, smtplib, threading, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from sqlalchemy import create_engine, text
from flask import Flask
from datetime import datetime
import pytz

EXPORT_INTERVAL_HOURS = int(os.getenv("EXPORT_INTERVAL_HOURS", 12))
EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")
DATABASE_URL = os.getenv("DATABASE_URL")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

def load_emails():
    if os.path.exists("emails.txt"):
        with open("emails.txt") as f:
            return [l.strip() for l in f if l.strip()]
    return []

EMAIL_TO = load_emails()

os.makedirs(EXPORT_DIR, exist_ok=True)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
logging.basicConfig(level=logging.INFO, format='[EXPORT] %(asctime)s %(message)s')
LOCAL_TZ = pytz.timezone("Europe/Vienna")

UTC = pytz.UTC

def now_utc():
    return datetime.now(UTC)

def now():
    return datetime.now(LOCAL_TZ)

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
            conn.execute(text("INSERT INTO export_checkpoint (last_export) VALUES (:ts)"), {"ts": now()})

def get_last_export_time():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT last_export FROM export_checkpoint ORDER BY id DESC LIMIT 1")).fetchone()
        return result[0] if result else now()

def update_last_export_time(ts):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO export_checkpoint (last_export) VALUES (:ts)"), {"ts": ts})

def monitored_export():
    logging.info(f"Export service started. Interval: {EXPORT_INTERVAL_HOURS}h")
    while True:
        try:
            time.sleep(EXPORT_INTERVAL_HOURS * 3600)
            
            last_export = get_last_export_time()
            now_ts_utc = now_utc()
            
            df = pd.read_sql_query(
                text("SELECT * FROM pings WHERE timestamp > :since"),
                engine.connect(),
                params={"since": last_export.strftime("%Y-%m-%d %H:%M:%S")}
            )

            if not df.empty:
                now_ts_vienna = now_ts_utc.astimezone(LOCAL_TZ)
                csv_path = f"{EXPORT_DIR}/pings_{now_ts_vienna.strftime('%Y%m%d_%H%M')}.csv"
                df.to_csv(csv_path, index=False, float_format="%.3f")
                logging.info(f"CSV exported: {csv_path}")

                stats = df.groupby("target").agg(
                    total_pings=pd.NamedAgg(column="latency", aggfunc="count"),
                    timeouts=pd.NamedAgg(column="latency", aggfunc=lambda x: x.isna().sum()),
                    avg_latency=pd.NamedAgg(column="latency", aggfunc="mean"),
                    max_latency=pd.NamedAgg(column="latency", aggfunc="max")
                ).reset_index()

                with engine.begin() as conn:
                    for _, row in stats.iterrows():
                        conn.execute(text("""
                            INSERT INTO ping_stats (target, timestamp, total_pings, timeouts, avg_latency, max_latency)
                            VALUES (:target, :timestamp, :total_pings, :timeouts, :avg_latency, :max_latency)
                        """), {
                            "target": row["target"],
                            "timestamp": now_ts_utc.strftime("%Y-%m-%d %H:%M:%S"),
                            "total_pings": int(row["total_pings"]),
                            "timeouts": int(row["timeouts"]),
                            "avg_latency": float(row["avg_latency"]) if not pd.isna(row["avg_latency"]) else None,
                            "max_latency": float(row["max_latency"]) if not pd.isna(row["max_latency"]) else None
                        })

                send_email(csv_path, stats)

            update_last_export_time(now_ts_utc)

        except Exception as e:
            logging.error(f"Export service error: {e}")
            time.sleep(60)


def send_email(csv_path, stats_df):
    if not EMAIL_TO or not EMAIL_FROM or not EMAIL_PASS:
        logging.warning("Email not configured, skipping send.")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = EMAIL_FROM
        msg["To"] = ", ".join(EMAIL_TO)
        now_ts = now()
        msg["Subject"] = f"Network Report – {now_ts.strftime('%Y-%m-%d %H:%M')}"

        text_body = (
            "Network Monitor – Automatic Report\n"
            f"Generated at: {now_ts.strftime('%Y-%m-%d %H:%M %Z')}\n\n"
            "Summary per target:\n\n"
            f"{stats_df.to_string(index=False)}\n\n"
            "See attached CSV for full details."
        )

        html_rows = ""
        for _, r in stats_df.iterrows():
            html_rows += f"""
            <tr>
                <td>{r['target']}</td>
                <td>{int(r['total_pings'])}</td>
                <td>{int(r['timeouts'])}</td>
                <td>{f"{r['avg_latency']:.2f}" if pd.notna(r['avg_latency']) else "–"}</td>
                <td>{f"{r['max_latency']:.2f}" if pd.notna(r['max_latency']) else "–"}</td>
            </tr>
            """

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background:#0f172a; color:#e5e7eb; padding:20px">
            <h2 style="color:#38bdf8;">📡 Network Monitor – Report</h2>

            <p>
                <strong>Generated:</strong>
                {now_ts.strftime('%Y-%m-%d %H:%M %Z')}
            </p>

            <table style="border-collapse:collapse; margin-top:15px; width:100%;">
                <thead>
                    <tr style="background:#1e293b;">
                        <th style="padding:8px; border:1px solid #334155;">Target</th>
                        <th style="padding:8px; border:1px solid #334155;">Pings</th>
                        <th style="padding:8px; border:1px solid #334155;">Timeouts</th>
                        <th style="padding:8px; border:1px solid #334155;">Avg (ms)</th>
                        <th style="padding:8px; border:1px solid #334155;">Max (ms)</th>
                    </tr>
                </thead>
                <tbody>
                    {html_rows}
                </tbody>
            </table>

            <p style="margin-top:20px; font-size:13px; color:#94a3b8;">
                📎 Full ping history is attached as CSV.
            </p>
        </body>
        </html>
        """

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        if os.path.exists(csv_path):
            with open(csv_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(csv_path))
            part["Content-Disposition"] = f'attachment; filename="{os.path.basename(csv_path)}"'
            msg.attach(part)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        logging.info(f"Mail sent to: {', '.join(EMAIL_TO)}")

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
    threading.Thread(target=monitored_export, daemon=True).start()
    while True:
        time.sleep(60)
        logging.info("Heartbeat: export service running")
