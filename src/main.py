import socket
import time
import threading
from datetime import datetime, timezone, timedelta 
from sqlalchemy import create_engine
from sqlalchemy import text
import os

from dash import Dash, dcc, html
from dash.dependencies import Output, Input
import plotly.graph_objs as go
from sqlalchemy import create_engine

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
conn = engine.connect()

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pings (
            id SERIAL PRIMARY KEY,
            target TEXT,
            timestamp TEXT,
            latency DOUBLE PRECISION
        )
    """))
    conn.commit()

TARGETS = ["8.8.8.8", "1.1.1.1", "192.168.33.1"]
INTERVAL = 0.5
MAX_POINTS = 100000
TIMEOUT_MS = 2000


def ping_once(target: str, port=53, timeout=1):
    try:
        start = time.time()
        s = socket.create_connection((target, port), timeout=timeout)
        s.close()
        latency = (time.time() - start) * 1000
        return latency
    except Exception:
        return None

def ping_target_loop(target):
    while True:
        now = datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        latency = ping_once(target, timeout=TIMEOUT_MS / 1000)
        with engine.connect() as conn:
            conn.execute(
                text("INSERT INTO pings (target, timestamp, latency) VALUES (:target, :timestamp, :latency)"),
                {"target": target, "timestamp": now, "latency": latency}
            )
            conn.commit()
        time.sleep(INTERVAL)

for t in TARGETS:
    threading.Thread(target=ping_target_loop, args=(t,), daemon=True).start()

app = Dash(__name__)
graph_ids = {t: t.replace(".", "_") for t in TARGETS}
app.layout = html.Div([
    html.H2("Live Network Latency Monitor"),
    dcc.Interval(id="update-interval", interval=int(INTERVAL*1000), n_intervals=0),
    html.Div([dcc.Graph(id=graph_ids[t]) for t in TARGETS])
])

for target in TARGETS:
    def make_callback(t):
        def update_graph(_):
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT timestamp, latency FROM pings WHERE target=:t ORDER BY timestamp DESC LIMIT :limit"),
                    {"t": t, "limit": MAX_POINTS}
                )
                rows = result.fetchall()

            rows.reverse()
            x_values = [datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone(timedelta(hours=2))) for r in rows]
            y_values = [r[1] for r in rows]

            fig = go.Figure()

            ping_y = [y if y is not None else None for y in y_values]
            fig.add_trace(go.Scatter(
                x=x_values,
                y=ping_y,
                mode="lines+markers",
                name="Ping",
                line=dict(color="blue", width=2),
                marker=dict(size=4)
            ))

            timeout_x = [x for x, y in zip(x_values, y_values) if y is None]
            fig.add_trace(go.Scatter(
                x=timeout_x,
                y=[0]*len(timeout_x),
                mode="lines+markers",
                name="Timeout",
                line=dict(color="red", width=2),
                marker=dict(size=4, symbol="x")
            ))

            normal_values = [v for v in y_values if v is not None]
            if normal_values:
                y_max = max(normal_values) * 1.1
            else:
                y_max = 100

            fig.update_layout(
                title=f"Ping Latency for {t} (ms)",
                xaxis_title="Zeit",
                yaxis_title="Latenz (ms)",
                template="plotly_dark",
                yaxis=dict(range=[0, y_max]),
                xaxis=dict(tickformat="%H:%M:%S.%L")
            )

            return fig

        return update_graph

    app.callback(Output(graph_ids[target], "figure"), Input("update-interval", "n_intervals"))(make_callback(target))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
