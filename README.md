# Network Monitor

**Network Monitor** is a lightweight, containerized network monitoring tool for visualizing latency fluctuations in real-time. It is particularly useful for diagnosing connectivity issues after network upgrades such as fiber optic installations.

The application continuously pings configured targets and stores results in a PostgreSQL database. A web interface provides interactive graphs and automatic reports, making it easy to track network stability and historical performance.

---

## Features

- **Real-time latency monitoring**: Continuous ping to multiple targets.
- **Historical storage**: All results (Target IP, Timestamp, Latency) are stored in PostgreSQL.
- **Interactive dashboard**: Live graphs with timeout markers and adjustable time windows.
- **Automatic CSV exports**: Full history of pings can be exported per target.
- **Scheduled reports**: Summarized statistics (average, max, timeout count) and CSV are automatically emailed at configurable intervals.
- **Multiple recipients**: Reports can be sent to one or more email addresses.
- **Containerized deployment**: Runs in Docker with minimal setup.

---

## Requirements

- Docker & Docker Compose
- PostgreSQL database
- SMTP credentials for sending email reports

---

## Environment Variables

Create a `.env` file in the project root with the following configuration:

```env
# Database
POSTGRES_USER=<your_db_user>
POSTGRES_PASSWORD=<your_db_password>
POSTGRES_DB=<your_db_name>

# Target hosts
TARGETS_FILEPATH=src/targets.txt

# Email reporting
EMAIL_TO="recipient1@example.com,recipient2@example.com"
EMAIL_FROM=<your_email>
EMAIL_PASS=<your_email_app_password>
SMTP_SERVER=<smtp_server>
SMTP_PORT=<smtp_port>

# Automatic export interval (in hours)
EXPORT_INTERVAL_HOURS=12
```
## Target Configuration
Targets are configured in the `src/targets.txt` file. Each target (IP or hostname) should be on a seperate line.

## Running the Application
Build and start the containers using Docker Compose
```bash
docker compose up --build
```
* Dashboard is available at `http://localhost:8050`
* Adminer is available at `http://localhost:8080`

## Dashboard Features
* Live latency graphs for all configured targets
* Timeout markers shown in red do identify connectivity issues

## Automatic Reporting
* The service automatically generates a CSV file and summary statistics every `EXPORT_INTERVAL_HOURS`
* Emails include
    * Average latency per target
    * Maximum latency per target
    * Total number of pings and timeouts
    * Attached CSV file with detailed ping history

## License
MIT License - free to use and modify