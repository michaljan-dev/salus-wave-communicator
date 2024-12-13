from flask import Flask, render_template
from typing import List, Dict, Any
from lib.heathub.utils import FlagManager, LogManager

app = Flask(__name__)

flag_manager = FlagManager()
log_manager = LogManager()


@app.route("/")
def index() -> str:
    logs: List[Dict[str, Any]] = log_manager.get_logs()
    logs = sorted(logs, key=lambda log: log["date"], reverse=True)
    flags: Dict[str, Any] = flag_manager.get_flags()
    return render_template("index.html", logs=logs, flags=flags)
