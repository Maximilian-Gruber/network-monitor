import os
import time
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text

EXPORT_INTERVAL_HOURS = int(os.getenv("EXPORT_INTERVAL_HOURS"))
EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")
DATABASE_URL = os.getenv("DATABASE_URL")
EMAIL_TO = [email.strip() for email in os.getenv("EMAIL_TO", "").split(",") if email.strip()]
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))

os.makedirs(EXPORT_DIR, exist_ok=True)

engine = create_engine(DATABASE_URL)

def export_and_send():
    while True:
        try:
            now = datetime.now(timezone(timedelta(hours=2)))
            since = now - timedelta(hours=EXPORT_INTERVAL_HOURS)
            csv_path = f"{EXPORT_DIR}/pings_{now.strftime('%Y%m%d_%H%M')}.csv"

            with engine.connect() as conn:
                df = pd.read_sql_query(
                    text("SELECT * FROM pings WHERE timestamp >= :since"),
                    conn,
                    params={"since": since.strftime("%Y-%m-%d %H:%M:%S")},
                )

                if not df.empty:
                    df.to_csv(csv_path, index=False)
                    print(f"[EXPORT] CSV saved: {csv_path}")
                else:
                    print("[EXPORT] No new pings in the time period.")

                stats = pd.read_sql_query(
                    text("""
                        SELECT 
                            target,
                            COUNT(*) AS total_pings,
                            SUM(CASE WHEN latency IS NULL THEN 1 ELSE 0 END) AS timeouts,
                            ROUND(AVG(latency)::numeric, 2) AS avg_latency,
                            ROUND(MAX(latency)::numeric, 2) AS max_latency
                        FROM pings
                        WHERE timestamp >= :since
                        GROUP BY target
                    """),
                    conn,
                    params={"since": since.strftime("%Y-%m-%d %H:%M:%S")},
                )

                if not stats.empty:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS ping_stats (
                            id SERIAL PRIMARY KEY,
                            target TEXT,
                            timestamp TEXT,
                            total_pings INTEGER,
                            timeouts INTEGER,
                            avg_latency DOUBLE PRECISION,
                            max_latency DOUBLE PRECISION
                        )
                    """))

                    for _, row in stats.iterrows():
                        conn.execute(
                            text("""
                                INSERT INTO ping_stats (target, timestamp, total_pings, timeouts, avg_latency, max_latency)
                                VALUES (:target, :timestamp, :total_pings, :timeouts, :avg_latency, :max_latency)
                            """),
                            {
                                "target": row["target"],
                                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                                "total_pings": int(row["total_pings"]),
                                "timeouts": int(row["timeouts"]),
                                "avg_latency": float(row["avg_latency"]) if row["avg_latency"] else None,
                                "max_latency": float(row["max_latency"]) if row["max_latency"] else None,
                            },
                        )
                    conn.commit()
                    print(f"[STATS] Statistics saved ({len(stats)} targets)")

                    send_email(csv_path, stats)

        except Exception as e:
            print(f"[ERROR] ExportService: {e}")

        print(f"[SERVICE] Next run in {EXPORT_INTERVAL_HOURS} hours...")
        time.sleep(EXPORT_INTERVAL_HOURS * 3600)


def send_email(csv_path, stats_df):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_FROM
        msg["To"] = ", ".join(EMAIL_TO)
        msg["Subject"] = f"Network Report {datetime.now().strftime('%Y-%m-%d %H:%M')}"

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
                print(f"[MAIL] Report sent to {recipient}.")

    except Exception as e:
        print(f"[MAIL ERROR] {e}")


def start_export_service():
    import threading
    thread = threading.Thread(target=export_and_send, daemon=True)
    thread.start()
    print("[SERVICE] Export & Email service started.")
