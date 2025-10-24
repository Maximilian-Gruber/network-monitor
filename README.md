# Network Monitor

**Network Monitor** is a lightweight, containerized network monitoring tool that visualizes latency fluctuations in real time. It is especially useful for diagnosing connectivity issues after network upgrades such as fiber optic installations. ;-)

The application continuously pings configured targets and stores the results in a PostgreSQL database. A web dashboard provides interactive graphs, and automatic reports summarize network performance.

---

## Features

- **Real-time latency monitoring**: Continuous pinging of multiple targets.
- **Historical storage**: All results (target, timestamp, latency) are stored in PostgreSQL.
- **Interactive dashboard**: Live graphs with timeout markers and adjustable time windows.
- **Automatic CSV exports**: Full ping history per target can be exported.
- **Scheduled reports**: Summarized statistics (average, maximum, timeout count) and CSV are automatically emailed.
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
POSTGRES_USER=admin
POSTGRES_PASSWORD=YourStrongPassword
POSTGRES_DB=networkdb

# Target hosts
TARGETS_FILEPATH=targets.txt

# Email reporting
EMAIL_TO=recipient1@example.com,recipient2@example.com
EMAIL_FROM=youremail@example.com
EMAIL_PASS=your_email_app_password
SMTP_SERVER=smtp.example.com
SMTP_PORT=587

# Automatic export interval (in hours)
EXPORT_INTERVAL_HOURS=12

# Directory for CSV exports
EXPORT_DIR=/app/exports

# Dashboard
DASH_REFRESH_MS=10000
MAX_POINTS=500

# Ping service
PING_INTERVAL=1
PING_TIMEOUT=2
```

## Target Configuration

Targets are configured in the ```src/targets.txt``` file. Each target (IP or hostname) should be on a seperate line.

## Running the Application
Build and start the containers using Docker Compose:
```bash
docker-compose up --build
```
* Dashboard is available at: ```http://localhost:8050```
* Adminer (PostgreSQL web client) is available at: ```http://localhost:8080````

## Dashboard Features
* Live latency graphs for all configured targets.
* Timeout markers shown in red to identify connectivity issues.

## Automatic Reporting
* The export service generates a CSV file and summary statistics every ```EXPORT_INTERVAL_HOURS```
* Only new pings since the last export are included.
* Emails include
    * Average latency per target
    * Maximum latency per target
    * Total number of pings and timeouts
    * Attached CSV file with detailed ping history

## License
MIT License - free to use and modify