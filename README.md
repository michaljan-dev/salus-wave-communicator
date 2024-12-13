## Salus Controls - Bosch Wave Communicator

### A system designed to control underfloor heating zones and bathroom radiators on demand, while maintaining separate schedules for hot water without losing control or efficiency.

Setting Up Python Environment
------------------------------
1. Use Poetry and pyenv to manage different Python versions.
2. Install dependencies required for Python development:
   libxml2-dev libxslt-dev python-dev python-dev-is-python3

Configuring Poetry Environment
------------------------------
- Specify the Python version for Poetry to use:
  poetry env use {pythonVersion}

Main app configuration
----------------------------------
- Rename config.dist.yaml to config.yaml. Update the required settings variables accordingly.

Main app
----------------------------------
- Run main script via Poetry's environment:
  poetry run python cron.py

Optional: Flask application for actions and logs monitoring
-------------------------
- Start the Flask application with the following command:
  poetry run flask run --host=0.0.0.0 --debug

Managing services for the main functionality and the Flask app (Ubuntu).
-----------------
  1. Navigate to the systemd directory:
     cd /etc/systemd/system
     and add files from systemmd. Update the base path to the folder where the app is located.
  2. Manage the services using systemctl:
     - Check service enable/status/stop:
       sudo systemctl enable salus.service
  3. Repeat for salus.cron.timer as needed.

Troubleshooting
---------------
- Check logs using journalctl:
  - View logs for a specific service:
    journalctl -u salus.cron.service -xr
