import datetime
import os
import yaml
import threading
from tinydb import TinyDB, Query
from typing import Any, Optional, Dict, List

# Define configuration directory and path at the module level
CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../etc'))
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.yaml')
DB_DIR = os.path.join(CONFIG_DIR, 'tinyDb')

# Ensure directories exist
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

# Some other constants
DEVICE_SALUS = "salus"
DEVICE_SALUS_BUTTON_BATHROOM = "salus_button_bathroom"
DEVICE_WAVE = "wave"
LOG_TYPE_ERROR = "error"


class ConfigManager:
    """Handles configuration loading and saving."""

    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path

    def get_config(self) -> dict:
        # Load configuration from a YAML file.
        try:
            with open(self.config_path, "r") as stream:
                return yaml.safe_load(stream) or {}
        except FileNotFoundError:
            return {}
        except yaml.YAMLError as e:
            return {}

    def save_config(self, config: dict) -> None:
        # Save configuration to a YAML file.
        try:
            with open(self.config_path, "w") as stream:
                yaml.dump(config, stream)
        except Exception as e:
            raise


class DatabaseManager:
    """Handles database interactions using TinyDB."""

    MAX_DB_SIZE_MB = 1.5

    def __init__(self):
        self.db_dir = DB_DIR
        self.lock = threading.Lock()

    def get_db(self, db_name: str = "db") -> TinyDB:
        # Get a TinyDB instance for the specified database name.
        file_path = os.path.join(self.db_dir, f"{db_name}.json")
        with self.lock:
            if not os.path.exists(file_path):
                open(file_path, "a").close()
            else:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if file_size_mb > self.MAX_DB_SIZE_MB:
                    os.remove(file_path)
                    open(file_path, "a").close()
        return TinyDB(file_path)


class FlagManager:
    """Handles flag storage and retrieval."""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self._flag_cache: Dict[str, Any] = {}
        self._flag_table = None

    def set_flag_namespace(self, new_flag_data: Dict[str, Any]) -> None:
        # Save or update flags in the database.
        db = self.db_manager.get_db("db")
        table = db.table("flags")
        Flag = Query()
        for key, value in new_flag_data.items():
            table.upsert({"key": key, "value": value}, Flag.key == key)
            self._flag_cache[key] = value  # Update cache

    def get_flag(self, key: str) -> Optional[Any]:
        # Retrieve the value of a flag by key.
        if key in self._flag_cache:
            return self._flag_cache[key]

        if not self._flag_table:
            db = self.db_manager.get_db("db")
            self._flag_table = db.table("flags")

        Flag = Query()
        result = self._flag_table.get(Flag.key == key)
        if result:
            value = result["value"]
            self._flag_cache[key] = value
            return value
        return None

    def get_flags(self) -> Dict[str, Any]:
        # Retrieve all flags as a dictionary.
        if not self._flag_table:
            db = self.db_manager.get_db("db")
            self._flag_table = db.table("flags")

        results = self._flag_table.all()
        return {record["key"]: record["value"] for record in results}


class LogManager:
    """Handles logging to a TinyDB database."""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.lock = threading.Lock()
        self._log_table = None

    def _get_log_table(self) -> Any:
        # Get the 'logs' table from the database.
        if self._log_table is None:
            db = self.db_manager.get_db("logs")
            self._log_table = db.table("logs")
        return self._log_table

    def set_log(self, message: str = "", device: str = "", log_type: str = "info") -> None:
        # Save a log entry to the database.
        log_entry = {
            "date": Helper.get_current_formatted_date(),
            "device": device,
            "type": log_type,
            "message": message,
        }

        try:
            with self.lock:
                table = self._get_log_table()
                table.insert(log_entry)
        except Exception as e:
            # TODO: move this to native logging
            print(f"Failed to save log entry: {e}")

    def get_logs(self) -> List[Dict[str, Any]]:
        # Retrieve all log entries from the database.
        try:
            table = self._get_log_table()
            return table.all()
        except Exception as e:
            # TODO: move this to native logging
            print(f"Failed to retrieve logs: {e}")
            return []


class Helper:
    """Contains utility methods for diffrent purposes."""

    @staticmethod
    def get_current_formatted_date() -> str:
        # Get the current date and time formatted as a string.
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
