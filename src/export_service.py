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

EMAIL_TO_FILEPATH = os.getenv("EMAIL_TO_FILEPATH")

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

os.makedirs(EXPORT_DIR, exist_ok=True)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
logging.basicConfig(level=logging.INFO, format='[EXPORT] %(asctime)s %(message)s')
LOCAL_TZ = pytz.timezone("Europe/Vienna")

UTC = pytz.UTC

def now_utc():
    return datetime.now(UTC)

def now():
    return datetime.now(LOCAL_TZ)

def load_email_recipients():
    if not EMAIL_TO_FILEPATH:
        logging.warning("EMAIL_TO_FILEPATH is not set in the environment variables.")
        return []
    
    if not os.path.exists(EMAIL_TO_FILEPATH):
        logging.warning(f"Email recipients file not found at: {EMAIL_TO_FILEPATH}")
        return []
    
    try:
        with open(EMAIL_TO_FILEPATH, "r", encoding="utf-8") as f:
            content = f.read()
            recipients = [email.strip() for email in content.split(";") if email.strip()]
            return recipients
    except Exception as e:
        logging.error(f"Error reading email recipients file: {e}")
        return []

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
            time.sleep(EXPORT_INTERVAL_HOURS * 60)
            
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
    email_to_list = load_email_recipients()

    if not email_to_list or not EMAIL_FROM or not EMAIL_PASS:
        logging.warning("Email configuration incomplete or recipient list empty. Skipping email sending.")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_FROM
        msg["To"] = ", ".join(email_to_list)
        now_ts = now()
        msg["Subject"] = f"Network Report | {now_ts.strftime('%Y-%m-%d %H:%M')}"

        table_rows = ""
        for _, row in stats_df.iterrows():
            if row['timeouts'] > 0:
                status_icon = "🔴"
                timeout_style = "color: #d93025; font-weight: bold;"
            else:
                status_icon = "🟢"
                timeout_style = "color: #202124;"

            avg_lat = f"{row['avg_latency']:.1f} ms" if not pd.isna(row['avg_latency']) else "-"
            max_lat = f"{row['max_latency']:.1f} ms" if not pd.isna(row['max_latency']) else "-"

            table_rows += f"""
            <tr style="border-bottom: 1px solid #e0e0e0;">
                <td style="padding: 12px 8px; font-weight: 500; color: #202124; word-break: break-all;">{status_icon} &nbsp; {row['target']}</td>
                <td style="padding: 12px 8px; text-align: center; color: #5f6368;">{int(row['total_pings'])}</td>
                <td style="padding: 12px 8px; text-align: center; {timeout_style}">{int(row['timeouts'])}</td>
                <td style="padding: 12px 8px; text-align: right; color: #202124; font-variant-numeric: tabular-nums; white-space: nowrap;">{avg_lat}</td>
                <td style="padding: 12px 8px; text-align: right; color: #5f6368; font-variant-numeric: tabular-nums; white-space: nowrap;">{max_lat}</td>
            </tr>
            """

        html_body = f"""
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #202124; background-color: #f4f6f8; padding: 20px 10px; margin: 0;">
            <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #e2e8f0;">
                
                <div style="background: #1e293b; padding: 25px 20px; color: #ffffff;">
                    <span style="text-transform: uppercase; letter-spacing: 1.5px; font-size: 10px; color: #94a3b8; font-weight: 700;">Automated System Notification</span>
                    <h2 style="margin: 5px 0 0 0; font-size: 20px; font-weight: 600; letter-spacing: -0.5px;">Network Performance Report</h2>
                    <p style="margin: 12px 0 0 0; font-size: 12px; color: #cbd5e1; opacity: 0.9;">
                        Timestamp: {now_ts.strftime('%Y-%m-%d at %H:%M:%S')} ({LOCAL_TZ.zone})
                    </p>
                </div>
                
                <div style="padding: 20px 15px;">
                    
                    <div style="width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin-bottom: 20px;">
                        <table style="width: 100%; min-width: 500px; border-collapse: collapse; font-size: 13px;">
                            <thead>
                                <tr style="border-bottom: 2px solid #e2e8f0; text-align: left;">
                                    <th style="padding: 8px; color: #64748b; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; width: 40%;">Target</th>
                                    <th style="padding: 8px; color: #64748b; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; text-align: center; width: 15%;">Pings</th>
                                    <th style="padding: 8px; color: #64748b; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; text-align: center; width: 15%;">Timeouts</th>
                                    <th style="padding: 8px; color: #64748b; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; text-align: right; width: 15%;">Avg Lat</th>
                                    <th style="padding: 8px; color: #64748b; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; text-align: right; width: 15%;">Max Lat</th>
                                </tr>
                            </thead>
                            <tbody>
                                {table_rows}
                            </tbody>
                        </table>
                    </div>
                    
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 15px; margin-top: 20px;">
                        <p style="margin: 0; font-size: 12px; color: #475569; line-height: 1.5;">
                            💡 <strong>Attachment:</strong> The full comprehensive dataset has been generated and appended as a <code>.csv</code> file for granular analysis.
                        </p>
                    </div>
                </div>
                
                <div style="background: #f1f5f9; padding: 20px; text-align: center; border-top: 1px solid #e2e8f0;">
                    <p style="font-size: 11px; color: #94a3b8; margin: 0; line-height: 1.4;">
                        This is an automated operational report. Replies to this address are unmonitored.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, "html"))

        if os.path.exists(csv_path):
            with open(csv_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(csv_path))
            part["Content-Disposition"] = f'attachment; filename="{os.path.basename(csv_path)}"'
            msg.attach(part)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASS)
            for recipient in email_to_list:
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
    initial_recipients = load_email_recipients()
    logging.info(f"Recipients file loaded. Found addresses: {len(initial_recipients)}")
    
    threading.Thread(target=run_health, daemon=True).start()
    threading.Thread(target=monitored_export, daemon=True).start()
    while True:
        time.sleep(60)
        logging.info("Heartbeat: export service running")