#!/bin/bash

cd /srv/events_feed
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r req.txt

# Define the service content
SERVICE_CONTENT="
[Unit]
Description=Events Feed App Service
After=network.target

[Service]
User=root
WorkingDirectory=/srv/events_feed
ExecStart=venv/bin/streamlit run src/ui.py
Restart=always
RestartSec=5
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=streamlit_app

[Install]
WantedBy=multi-user.target
"

echo "$SERVICE_CONTENT" | sudo tee /etc/systemd/system/events_feed_app.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable events_feed_app
sudo systemctl start events_feed_app
sudo systemctl status events_feed_app
