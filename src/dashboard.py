import threading, time, logging, os
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
from sqlalchemy import create_engine, text
import plotly.graph_objs as go
from flask import Flask
from datetime import datetime
import pytz

DATABASE_URL = os.getenv("DATABASE_URL")
INTERVAL_MS = int(os.getenv("DASH_REFRESH_MS", 2000))
MAX_POINTS = int(os.getenv("MAX_POINTS", 500))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
logging.basicConfig(level=logging.INFO, format='[DASH] %(asctime)s %(message)s')
LOCAL_TZ = pytz.timezone("Europe/Vienna")

def now():
    return datetime.now(LOCAL_TZ)

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pings (
                id SERIAL PRIMARY KEY,
                target TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                latency DOUBLE PRECISION
            );
        """))
    logging.info("Ensured table pings exists.")

def wait_for_targets():
    for _ in range(30):
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT DISTINCT target FROM pings")).fetchall()
            if rows:
                return [r[0] for r in rows]
        logging.info("Waiting for ping data...")
        time.sleep(2)
    return ["8.8.8.8", "1.1.1.1"]

def monitored_dash_loop():
    app = Dash(__name__)
    app.title = "Network Monitor"

    targets = wait_for_targets()
    app.layout = html.Div([
        html.H2("Network Latency Monitor"),
        dcc.Interval(id="refresh", interval=INTERVAL_MS),
        html.Div([dcc.Graph(id=t.replace('.', '_')) for t in targets])
    ])

    def make_callback(target):
        def update(_):
            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT timestamp, latency
                        FROM pings
                        WHERE target=:t
                        ORDER BY timestamp DESC
                        LIMIT :limit
                    """), {"t": target, "limit": MAX_POINTS}
                ).fetchall()
            rows.reverse()
            if not rows:
                return go.Figure(layout_title_text=f"No data for {target}")
            x = [r[0].astimezone(LOCAL_TZ) for r in rows]
            y = [r[1] for r in rows]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="Ping",
                                     line=dict(color="blue")))
            timeout_x = [x[i] for i, v in enumerate(y) if v is None]
            fig.add_trace(go.Scatter(x=timeout_x, y=[0]*len(timeout_x), mode="markers",
                                     marker=dict(color="red", symbol="x", size=10), name="Timeout"))
            fig.update_layout(title=f"{target} Latency (ms)", template="plotly_dark",
                              yaxis_title="Latenz (ms)", xaxis_title="Zeit")
            return fig
        return update

    for t in targets:
        app.callback(Output(t.replace('.', '_'), "figure"), Input("refresh", "n_intervals"))(make_callback(t))

    app.run(host="0.0.0.0", port=8050, debug=False)

flask_app = Flask(__name__)
@flask_app.route("/health")
def health():
    return "OK", 200

def run_health():
    flask_app.run(host="0.0.0.0", port=8051)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=monitored_dash_loop, daemon=True).start()
    threading.Thread(target=run_health, daemon=True).start()
    while True:
        time.sleep(60)
        logging.info("Heartbeat: dashboard running")
