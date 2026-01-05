import threading, time, logging, os
from dash import Dash, dcc, html, dash_table
from dash.dependencies import Input, Output
from sqlalchemy import create_engine, text
import plotly.graph_objs as go
import pandas as pd
from flask import Flask
from datetime import datetime, timezone
import pytz

DATABASE_URL = os.getenv("DATABASE_URL")
INTERVAL_MS = int(os.getenv("DASH_REFRESH_MS", 5000))
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

def latency_distribution():
    q = """
    SELECT
      bucket AS bucket,
      COUNT(*) AS count,
      ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percent
    FROM (
      SELECT CASE
        WHEN latency IS NULL THEN 'Timeout / keine Antwort'
        WHEN latency < 1 THEN '< 1 ms'
        WHEN latency < 5 THEN '1 – 5 ms'
        WHEN latency < 10 THEN '5 – 10 ms'
        WHEN latency < 50 THEN '10 – 50 ms'
        WHEN latency < 100 THEN '50 – 100 ms'
        ELSE '≥ 100 ms' END AS bucket
      FROM pings
    ) t
    GROUP BY bucket
    ORDER BY
      CASE bucket
        WHEN 'Timeout / keine Antwort' THEN 0
        WHEN '< 1 ms' THEN 1
        WHEN '1 – 5 ms' THEN 2
        WHEN '5 – 10 ms' THEN 3
        WHEN '10 – 50 ms' THEN 4
        WHEN '50 – 100 ms' THEN 5
        ELSE 6 END;
    """
    return pd.read_sql(text(q), engine)

def packet_loss_table():
    q = """
    SELECT
      target AS target,
      COUNT(*) AS total,
      SUM(CASE WHEN latency IS NULL THEN 1 ELSE 0 END) AS timeouts,
      ROUND(100.0 * SUM(CASE WHEN latency IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS loss_percent
    FROM pings
    GROUP BY target
    ORDER BY loss_percent DESC
    LIMIT 10;
    """
    return pd.read_sql(text(q), engine)

def latency_stats_table():
    q = """
    SELECT
      target AS target,
      ROUND(AVG(latency)::numeric, 2) AS avg_latency,
      ROUND(STDDEV_SAMP(latency)::numeric, 2) AS stddev_latency,
      ROUND(MIN(latency)::numeric, 2) AS min_latency,
      ROUND(MAX(latency)::numeric, 2) AS max_latency
    FROM pings
    WHERE latency IS NOT NULL
    GROUP BY target
    ORDER BY avg_latency DESC
    LIMIT 10;
    """
    return pd.read_sql(text(q), engine)

def latency_over_time():
    q = """
    SELECT
      to_timestamp(
        floor(extract(epoch FROM timestamp) / :bucket) * :bucket) AS ts,
      ROUND(AVG(latency)::numeric, 2) AS avg_latency,
      ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency)::numeric, 2) AS p95
    FROM pings
    WHERE timestamp >= now() - INTERVAL '3 hours' AND latency IS NOT NULL
    GROUP BY 1
    ORDER BY 1;
    """
    return pd.read_sql(text(q), engine, params={"bucket": 5})

def targets_list():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT target FROM pings")).fetchall()
    return [r[0] for r in rows] if rows else ["8.8.8.8"]

def run_dash():
    app = Dash(__name__)
    app.title = "Network Monitor + Analyse"

    targets = targets_list()

    app.layout = html.Div([
        html.H2("Network Monitor & Analyse"),
        dcc.Interval(id="refresh", interval=INTERVAL_MS),
        
        html.H3("Latenzverteilung"),
        dcc.Graph(id="latency_dist"),
        
        html.H3("Paketverlust"),
        dash_table.DataTable(id="packet_loss",
                             columns=[{"name": c, "id": c} for c in packet_loss_table().columns],
                             style_cell={'textAlign': 'center'}),
        
        html.H3("Durchschnittliche Latenz"),
        dash_table.DataTable(id="latency_stats",
                             columns=[{"name": c, "id": c} for c in latency_stats_table().columns],
                             style_cell={'textAlign': 'center'}),
        
        html.H3("Latenz über Zeit"),
        dcc.Graph(id="latency_time"),
        
    ])

    @app.callback(Output("latency_dist", "figure"), Input("refresh", "n_intervals"))
    def update_latency_dist(_):
        df = latency_distribution()
        fig = go.Figure([go.Bar(x=df['bucket'], y=df['percent'], text=df['percent'], textposition='auto')])
        fig.update_layout(template="plotly_dark", yaxis_title="Prozent (%)", xaxis_title="Latenz-Bereich")
        return fig

    @app.callback(Output("packet_loss", "data"), Input("refresh", "n_intervals"))
    def update_packet_loss(_):
        return packet_loss_table().to_dict("records")

    @app.callback(Output("latency_stats", "data"), Input("refresh", "n_intervals"))
    def update_latency_stats(_):
        return latency_stats_table().to_dict("records")

    @app.callback(Output("latency_time", "figure"), Input("refresh", "n_intervals"))
    def update_latency_time(_):
        df = latency_over_time()
        if df.empty:
            return go.Figure()
        x = [r.astimezone(LOCAL_TZ) if r.tzinfo else r.replace(tzinfo=LOCAL_TZ) for r in df['ts']]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x, y=df['avg_latency'], mode="lines+markers", name="Avg"))
        fig.add_trace(go.Scatter(x=x, y=df['p95'], mode="lines", name="P95", line=dict(dash="dot")))
        fig.update_layout(template="plotly_dark", yaxis_title="Latenz (ms)", xaxis_title="Zeit")
        return fig

    for t in targets:
        @app.callback(Output(f"target_{t.replace('.', '_')}", "figure"), Input("refresh", "n_intervals"))
        def update_target_graph(_t=t):
            q = text("""
            SELECT timestamp, latency
            FROM pings
            WHERE target=:t AND latency IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT :limit
            """)
            df = pd.read_sql(q, engine, params={"t": _t, "limit": MAX_POINTS})
            df = df[::-1]
            if df.empty:
                return go.Figure()
            x = [r.astimezone(LOCAL_TZ) if r.tzinfo else r.replace(tzinfo=LOCAL_TZ) for r in df['timestamp']]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x, y=df['latency'], mode="lines+markers", name="Ping"))
            fig.update_layout(title=_t, template="plotly_dark", yaxis_title="Latenz (ms)", xaxis_title="Zeit")
            return fig

    app.run(host="0.0.0.0", port=8050, debug=False)

flask_app = Flask(__name__)
@flask_app.route("/health")
def health():
    return "OK", 200

def run_health():
    flask_app.run(host="0.0.0.0", port=8051)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_dash, daemon=True).start()
    threading.Thread(target=run_health, daemon=True).start()
    while True:
        time.sleep(60)
        logging.info("Heartbeat: dashboard running")
