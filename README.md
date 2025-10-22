# Network Monitor

A lightweight and containerized network monitoring tool for visualizing latency fluctuations — especially useful for diagnosing connectivity issues after fiber optic installation ;-)

When the Docker container is started, the application begins pinging the configured targets while simultaneously running a Flask-based web server that visualizes the collected data in interactive graphs, accessible via [http://localhost:8050](http://localhost:8050).

All results — including **Target IP**, **Timestamp**, and **Latency** — are stored in an PostgreSQL database, enabling in-depth historical analysis and performance tracking.

To start the application, the following variables need to be configured in an .env file in the root directory
* POSTGRES_USER
* POSTGRES_PASSWORD
* POSTGRES_DB
* TARGETS_FILEPATH
## Target configuration
Configure targets by editing the `src/targets.txt` file, as shown with two example IPs (Google DNS, Cloudflare DNS).
Every IP needs to be in its own line.