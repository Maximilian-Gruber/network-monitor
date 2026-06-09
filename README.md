# Network Monitor

A Python-based network monitoring application that continuously pings target hosts and visualizes the results through an interactive web dashboard.

## Overview

Network Monitor consists of three main components:
- **Ping Service**: Continuously pings configured targets and records latency data
- **PostgreSQL Database**: Stores all ping statistics and metrics
- **Dashboard**: Interactive Plotly/Dash web interface to visualize network performance

The application tracks latency distributions, response times, and timeouts for multiple network targets.

## Features

- 🎯 Continuous network monitoring with configurable ping intervals
- 📊 Interactive web dashboard with real-time visualizations
- 💾 PostgreSQL backend for reliable data persistence
- 📈 Latency distribution analysis and statistics
- 🐳 Docker and Docker Compose support for easy deployment
- ⚙️ Highly configurable via environment variables

## Project Structure

```
network-monitor/
├── src/                   # Application source code
│   ├── ping_service.py    # Ping monitoring service
│   ├── dashboard.py       # Dash web dashboard
│   ├── export_service.py  # Data export utilities
│   ├── Dockerfile         # Container image definition
│   └── requirements.txt   # Python dependencies
├── docker-compose.yml     # Container orchestration
├── targets.txt            # List of hosts/IPs to monitor
├── email_recipients.txt   # Email notification recipients
├── exports/               # CSV and SQL exports of data
└── local_analysis/        # Local analysis tools
```

## Requirements

### Docker & Docker Compose
- Docker Engine 20.10+
- Docker Compose 2.0+

### Local Development (without Docker)
- Python 3.9+
- PostgreSQL 12+
- pip or equivalent package manager

## Configuration

### Targets

Edit [targets.txt](targets.txt) to specify which hosts/IPs to monitor. Add one target per line:

```
8.8.8.8
1.1.1.1
example.com
```

### Email Recipients

Edit [email_recipients.txt](email_recipients.txt) to specify email addresses for notifications. Add email addresses separated by semicolons on a single line:

```
user1@example.com; user2@example.com; admin@example.com
```

### Environment Variables (.env)

Create a `.env` file in the project root with the following variables. All are required unless marked as optional.

#### Database Configuration

| Variable | Example | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `admin` | PostgreSQL database username; used to authenticate with the database server |
| `POSTGRES_PASSWORD` | `your_secure_password` | PostgreSQL database password; use a strong password in production |
| `POSTGRES_DB` | `networkdb` | PostgreSQL database name to store ping statistics |

#### Email Notification Configuration

| Variable | Example | Description |
|----------|---------|-------------|
| `EMAIL_FROM` | `your@email.com` | Sender email address for notifications; must match your SMTP account |
| `EMAIL_PASS` | `aaaa aaaa aaaa aaaa` | Email account password or app-specific password for SMTP authentication (for Gmail, use app-specific password) |
| `SMTP_SERVER` | `smtp.gmail.com` | SMTP server address (e.g., `smtp.gmail.com` for Gmail, `smtp.outlook.com` for Outlook) |
| `SMTP_PORT` | `587` | SMTP port number (typically `587` for TLS or `465` for SSL) |
| `EMAIL_TO_FILEPATH` | `/app/email_recipients.txt` | Path to email recipients file; Docker path or local path depending on deployment |

#### Monitoring & Export Configuration

| Variable | Example | Description |
|----------|---------|-------------|
| `PING_INTERVAL` | `1` | Seconds between ping attempts per target; lower values = more frequent monitoring |
| `PING_TIMEOUT` | `2` | Maximum seconds to wait for ping response; increase for slow/distant targets |
| `TARGETS_FILEPATH` | `/app/targets.txt` | Path to targets file; Docker path or local path depending on deployment |
| `EXPORT_INTERVAL_HOURS` | `24` | Hours between automated data exports to CSV/SQL; set to desired backup frequency |
| `EXPORT_DIR` | `/app/exports` | Directory path for storing exported data files; Docker path or local path depending on deployment |

#### Dashboard Configuration

| Variable | Example | Description |
|----------|---------|-------------|
| `DASH_REFRESH_MS` | `5000` | Dashboard auto-refresh interval in milliseconds; lower values = more frequent updates (affects server load) |
| `MAX_POINTS` | `250` | Maximum data points to display on dashboard charts; higher values = more history, lower values = better performance |

#### Example `.env` File

```bash
# Database
POSTGRES_USER=netmon
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=networkdb

# Email Notifications
EMAIL_FROM=your-email@gmail.com
EMAIL_PASS=your_app_specific_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_TO_FILEPATH=/app/email_recipients.txt

# Monitoring
PING_INTERVAL=1
PING_TIMEOUT=2
TARGETS_FILEPATH=/app/targets.txt

# Export
EXPORT_INTERVAL_HOURS=24
EXPORT_DIR=/app/exports

# Dashboard
DASH_REFRESH_MS=5000
MAX_POINTS=250
```

#### Important Notes

- **Keep `.env` secure**: Add `.env` to `.gitignore` to prevent committing sensitive credentials
- **Gmail App Password**: For Gmail, generate an [app-specific password](https://support.google.com/accounts/answer/185833) instead of using your main password
- **Docker vs Local Paths**: When running with Docker Compose, use container paths (e.g., `/app/exports`); for local development, use relative or absolute filesystem paths
- **Strong Passwords**: Always use strong, randomly generated passwords in production environments
- **SMTP Configuration**: Verify your email provider's SMTP settings and ensure the account has permission for "less secure apps" or has 2FA app passwords enabled

## Quick Start

### Option 1: Docker Compose (Recommended)

1. **Create environment file** (`.env`):
   ```bash
   cat > .env << EOF
   POSTGRES_USER=netmon
   POSTGRES_PASSWORD=your_secure_password_here
   POSTGRES_DB=networkdb
   EMAIL_FROM=your-email@gmail.com
   EMAIL_PASS=your_app_specific_password
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   EMAIL_TO_FILEPATH=/app/email_recipients.txt
   PING_INTERVAL=1
   PING_TIMEOUT=2
   TARGETS_FILEPATH=/app/targets.txt
   EXPORT_INTERVAL_HOURS=24
   EXPORT_DIR=/app/exports
   DASH_REFRESH_MS=5000
   MAX_POINTS=250
   EOF
   ```
   
   **⚠️ Important**: Update the values above with your actual configuration:
   - Set strong `POSTGRES_PASSWORD`
   - Configure your email credentials (SMTP server, port, email, app-specific password)
   - Adjust monitoring intervals (`PING_INTERVAL`, `DASH_REFRESH_MS`) as needed

2. **Start services**:
   ```bash
   docker-compose up -d
   ```

3. **Verify services are running**:
   ```bash
   docker-compose ps
   ```

4. **Access the dashboard**:
   - Open browser to: `http://localhost:8050`
   - The dashboard will display ping statistics and latency distribution

5. **View logs**:
   ```bash
   docker-compose logs -f ping-service    # Monitor ping service
   docker-compose logs -f dashboard       # Monitor dashboard
   docker-compose logs -f db              # Monitor database
   ```

6. **Stop services**:
   ```bash
   docker-compose down
   ```

### Option 2: Local Development Setup

1. **Install dependencies**:
   ```bash
   cd src
   pip install -r requirements.txt
   ```

2. **Set up PostgreSQL**:
   - Start PostgreSQL server
   - Create database: `createdb netmon_db`
   - Create user: `createuser netmon` (use password when prompted)

3. **Configure environment**:
   ```bash
   export DATABASE_URL="postgresql://netmon:securepassword123@localhost:5432/netmon_db"
   export TARGETS_FILEPATH="./targets.txt"
   export PING_INTERVAL=1
   export PING_TIMEOUT=2
   export DASH_REFRESH_MS=5000
   export MAX_POINTS=500
   ```

4. **Start the ping service** (Terminal 1):
   ```bash
   python ping_service.py
   ```

5. **Start the dashboard** (Terminal 2):
   ```bash
   python dashboard.py
   ```

6. **Access the dashboard**:
   - Open browser to: `http://localhost:8050`

## Usage

### Monitoring Targets

Add targets to [targets.txt](targets.txt). The ping service will immediately start monitoring new targets.

```
# Edit targets.txt
8.8.8.8           # Google DNS
1.1.1.1           # Cloudflare DNS
8.8.4.4           # Google secondary DNS
```

### Exporting Data

Query and export ping data from the `pings` table:

```sql
-- Recent pings for a specific target
SELECT target, timestamp, latency FROM pings 
WHERE target = '8.8.8.8' 
ORDER BY timestamp DESC 
LIMIT 100;

-- Average latency per target over last 24 hours
SELECT target, AVG(latency) as avg_latency
FROM pings 
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY target;
```

Data exports are available in the [exports/](exports/) directory.

## Troubleshooting

### Dashboard not responding
- Check Docker containers: `docker-compose ps`
- Verify database is healthy: `docker-compose logs db`
- Restart dashboard: `docker-compose restart dashboard`

### Ping service not collecting data
- Verify targets.txt is properly formatted
- Check network connectivity to targets
- Review service logs: `docker-compose logs ping-service`

### Database connection errors
- Ensure PostgreSQL is running
- Verify DATABASE_URL environment variable is set correctly
- Check credentials in `.env` file

### Permission denied when running Docker
- Add user to docker group: `sudo usermod -aG docker $USER`
- Restart Docker: `sudo systemctl restart docker`

## Development

### Viewing Database

Connect directly with psql:

```bash
psql postgresql://netmon:password@localhost:5432/netmon_db
```

Query ping data:
```sql
SELECT COUNT(*) FROM pings;
SELECT DISTINCT target FROM pings;
```

## Data

### Pings Table Schema

```sql
CREATE TABLE pings (
    id SERIAL PRIMARY KEY,
    target TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    latency DOUBLE PRECISION
);
```

- `latency`: Measured in milliseconds; NULL indicates timeout/no response
- `timestamp`: Stored in Europe/Vienna timezone

## License

See [LICENSE](LICENSE) file for details.

## Support

For issues or questions, check the logs and ensure all environment variables are properly configured.

---

**Last Updated**: June 9, 2026
