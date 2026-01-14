# Network Monitor

**Network Monitor** is a lightweight, containerized network monitoring tool that visualizes latency fluctuations in real time.  
It is especially useful for diagnosing connectivity issues after network upgrades such as fiber optic installations 😉

The application continuously pings configured targets and stores the results in a PostgreSQL database.  
A web dashboard provides interactive graphs and aggregated latency statistics.

---

## Features

- **Real-time latency monitoring**  
  Continuous pinging of one or more targets

- **Historical storage**  
  All results (target, timestamp, latency) are stored in PostgreSQL

- **Interactive dashboard**
  - Latency distribution
  - Packet loss
  - Average latency
  - Latency over time (high frequency configurable)

- **Percentile-based metrics**  
  Includes P95 latency for spotting spikes

- **Configurable refresh rates**  
  Dashboard update interval and time resolution are adjustable

- **Automatic CSV exports & reports**  
  Periodic exports with summary statistics

- **Email reporting**  
  Reports can be sent to one or multiple recipients via SMTP

- **Fully containerized**  
  Runs entirely in Docker with minimal setup

---

## Requirements

- Docker Desktop

Check installation:

- docker --version
- docker compose version

- Docker installation guide: `https://docs.docker.com/get-docker/`

---

## Environment Variables

Rename `.env.example` to `.env` and adjust as needed:

```
### Database
POSTGRES_USER=admin
POSTGRES_PASSWORD=admin
POSTGRES_DB=db

### Email reporting
EMAIL_FROM=example@example.com
EMAIL_PASS=examplepassword
SMTP_SERVER=smtp.example.com
SMTP_PORT=587

### Automatic export interval (hours)
EXPORT_INTERVAL_HOURS=24

### Export directory
EXPORT_DIR=/app/exports

### Dashboard
DASH_REFRESH_MS=5000
MAX_POINTS=250

### Ping service
PING_INTERVAL=1
PING_TIMEOUT=2
```
---

## Running the Application

Build and start all services using Docker Compose:

- docker compose up --build

Or using the setup script:
- Switch to the directory named of your OS and execute the start.bat or start.sh file
- For linux and mac execute chmod +x setup.sh before starting the application

---

## Access

- **Dashboard**  
  http://localhost:8050

- **Adminer (PostgreSQL Web UI)**  
  http://localhost:8080

---

## Dashboard Overview

- Live latency visualization
- Latency distribution buckets
- Packet loss percentage
- Average and percentile latency
- High-resolution latency-over-time graph

---

## Automatic Reporting

- Reports are generated every `EXPORT_INTERVAL_HOURS`
- Only new pings since the last export are included
- Each report contains:
  - Average latency per target
  - Maximum latency per target
  - Total number of pings
  - Timeout / packet loss count
  - Attached CSV with detailed ping history

---

## Database Access

- The database can be accessed with adminer via http://localhost:8080 as described above
- With adminer, SQL statements can be executed or the whole accumulated data can be exported as a csv or sql file
- The credentials for adminer can be defined in `.env.example`

## License

MIT License – free to use and modify
