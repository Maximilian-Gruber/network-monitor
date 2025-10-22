# Network Monitor

A lightweight and containerized network monitoring tool for visualizing latency fluctuations — especially useful for diagnosing connectivity issues after fiber optic installation ;-)

When the Docker container is started, the application begins pinging the configured targets while simultaneously running a Flask-based web server that visualizes the collected data in interactive graphs, accessible via [http://localhost:8050](http://localhost:8050).

All results — including **Target IP**, **Timestamp**, and **Latency** — are stored in an PostgreSQL database, enabling in-depth historical analysis and performance tracking.
