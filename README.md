# Monitoring Agent

A system monitoring agent that collects and reports various system metrics to a centralized monitoring server. The agent can run either as a standalone Python script or as a system service.

## Features

- System metrics collection:
  - CPU usage and count
  - Memory usage (total and used)
  - Disk usage (total and free)
  - System uptime
  - System updates status (total and security updates)
  - Reboot requirement status
- Automatic dependency management
- Configurable collection interval
- Rotating log files
- Systemd service integration

## System Requirements

- Python 3.12
- Ubuntu 24.04 (primarily tested on this version, may work on other Ubuntu/Debian versions)
- Required Python packages:
  - netifaces==0.11.0
  - psutil==6.1.1
  - requests==2.32.3

## Installation & Usage

There are two methods to use this monitoring agent:

### Method 1: Direct Python Script Usage

This method involves using the Python script directly from the source code.


1. Clone the repository:
```bash
git clone https://github.com/Gu1llaum-3/monitoring-agent.git
cd monitoring-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the script:
```bash
python3 monitoring-agent.py --url http://<SERVER_IP> --port <PORT> --token <YOUR_TOKEN>
```

4. (Optional) Install as a service:
```bash
python3 monitoring-agent.py --url http://<SERVER_IP> --port <PORT> --token <YOUR_TOKEN> --install-service
```

The script will automatically create and start the systemd service for you.

### Method 2: Using Pre-compiled Binary

This method uses the pre-compiled binary, which is easier to deploy and doesn't require Python installation on the target system.

1. Download the latest release using wget:
```bash
wget https://github.com/Gu1llaum-3/monitoring-agent/releases/latest/download/monitoring-agent
```

2. Make the binary executable:
```bash
chmod +x monitoring-agent
```

3. Move to the appropriate directory:
```bash
sudo mv monitoring-agent /opt/
```

4. Create the systemd service file:
```bash
sudo nano /etc/systemd/system/monitoring-agent.service
```

5. Add the following content (replace <IP>, <PORT>, and <TOKEN> with your values):

```ini
[Unit]
Description=Agent de Monitoring
After=network.target

[Service]
ExecStart=/opt/monitoring-agent --url http://<IP> --port <PORT> --token <TOKEN>
Restart=always
User=root
Group=root
WorkingDirectory=/opt

[Install]
WantedBy=multi-user.target
```

6. Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable monitoring-agent
sudo systemctl start monitoring-agent
```

7. Verify the service is running:
```bash
sudo systemctl status monitoring-agent
```

## Command Line Options

The following options are available for both methods:
- `--url`: The monitoring server URL (required)
- `--port`: The monitoring server port (required)
- `--token`: Authentication token for the API (required)
- `--interval`: Collection interval in minutes (default: 1)
- `--log_file`: Custom log file path (default: /var/log/agent_monitor.log)
- `--install-service`: Install and start as a systemd service (Python script method only)

## Building from Source

To create a standalone executable:

```bash
pyinstaller --onefile --name monitoring-agent --clean monitoring-agent.py
```

The compiled binary will be available in the `dist` directory.

## Logs

Logs are stored in `/var/log/agent_monitor.log` by default, with automatic rotation (5MB max size, keeping 3 backup files).

## Configuration

The agent requires three mandatory parameters:
- `--url`: The monitoring server URL
- `--port`: The monitoring server port
- `--token`: Authentication token for the API

These can be provided either as command-line arguments or configured in the systemd service file.
