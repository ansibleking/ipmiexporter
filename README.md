<<<<<<< HEAD
# ipmiexporter
ipmiexporter - For Hardware Monitoring
=======
# Server Hardware Monitoring Dashboard

A centralized dashboard for monitoring server hardware metrics with Microsoft Teams integration.

## Features

- Real-time monitoring of CPU, Memory, Disk, and Network usage
- Modern, responsive dashboard interface
- Automatic alerts via Microsoft Teams
- Critical threshold monitoring
- Automatic updates every 30 seconds

## Setup

1. Install Python 3.8 or higher
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Teams webhook URL:
   ```
   TEAMS_WEBHOOK_URL=your_teams_webhook_url_here
   ```
4. Run the application:
   ```bash
   python app.py
   ```

## Microsoft Teams Integration

To set up Teams integration:

1. Create a Microsoft Teams channel
2. Add the "Incoming Webhook" connector to your channel
3. Copy the webhook URL and add it to your `.env` file

## Accessing the Dashboard

Once the application is running, open your web browser and navigate to:

```
http://localhost:5000
```

The dashboard will automatically refresh every 30 seconds to show the latest metrics.
>>>>>>> 2c005ee (new code for hardware monitoring)
