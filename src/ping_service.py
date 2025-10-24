import socket, time, threading, os, logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from flask import Flask

DATABASE_URL = os.getenv("DATABASE_URL")
TARGETS_FILEPATH = os.getenv("TARGETS_FILEPATH", "./targets.txt")
PING_INTERVAL = float(os.getenv("PING_INTERVAL", 1))
PING_TIMEOUT = float(os.getenv("PING_TIMEOUT", 2))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
logging.basicConfig(level=logging.INFO, format='[PING] %(asctime)s %(message)s')

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pings (
                id SERIAL PRIMARY KEY,
                target TEXT,
                timestamp TIMESTAMP,
                latency DOUBLE PRECISION
            );
            CREATE INDEX IF NOT EXISTS idx_pings_target_time ON pings(target, timestamp);
        """))
    logging.info("DB initialized.")

def ping_once(target):
    try:
        logging.info("[PING] Pinging " + target)
        start = time.time()
        s = socket.create_connection((target, 53), timeout=PING_TIMEOUT)
        s.close()
        return (time.time() - start) * 1000
    except Exception:
        return None

def ping_loop(target):
    while True:
        latency = ping_once(target)
        now = datetime.now(timezone.utc)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO pings (target, timestamp, latency) VALUES (:t, :ts, :l)"),
                    {"t": target, "ts": now, "l": latency}
                )
        except Exception as e:
            logging.error(f"DB insert failed for {target}: {e}")
            time.sleep(5)
        time.sleep(PING_INTERVAL)

app = Flask(__name__)
@app.route("/health")
def health():
    return "OK", 200

def run_health():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    init_db()
    if not os.path.exists(TARGETS_FILEPATH):
        raise FileNotFoundError(TARGETS_FILEPATH)
    with open(TARGETS_FILEPATH) as f:
        TARGETS = [line.strip() for line in f if line.strip()]
    logging.info(f"Monitoring {len(TARGETS)} targets: {', '.join(TARGETS)}")
    for t in TARGETS:
        threading.Thread(target=ping_loop, args=(t,), daemon=True).start()
    while True:
        time.sleep(60)
        logging.info("Heartbeat: ping service running.")
