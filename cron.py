import sys
import asyncio
import nest_asyncio
from lib.wave.WaveThermo import WaveThermo
from pyit600.exceptions import IT600AuthenticationError, IT600ConnectionError
from pyit600.gateway_singleton import IT600GatewaySingleton
from lib.heathub.bathroom.salus import SmartButton
from lib.heathub.utils import (
    ConfigManager,
    FlagManager,
    LogManager,
    Helper,
    DEVICE_SALUS,
    DEVICE_WAVE,
    LOG_TYPE_ERROR,
)

# Apply nest_asyncio to fix event loop issues
nest_asyncio.apply()

# Load configurations
config_manager = ConfigManager()
config = config_manager.get_config()
config_salus = config.get("salus", {})
config_wave = config.get("wave", {})
config_app = config.get("app", {})

# Initialize flag and log managers
flag_manager = FlagManager()
log_manager = LogManager()


# Asynchronous main function
async def main():
    # Update flags with the last run date
    flag_manager.set_flag_namespace(
        {"last_date_app_run": Helper.get_current_formatted_date()}
    )

    # Log the gateway run
    log_manager.set_log("Gateway run", device=DEVICE_SALUS)

    # Salus logic to get data from thermostats
    try:
        async with IT600GatewaySingleton.get_instance(
            host=config_salus.get("gateway_host"),
            euid=config_salus.get("gateway_euid"),
            debug=1,
        ) as gateway:
            await gateway.connect()
            await gateway.poll_status(send_callback=False)
            climate_devices = gateway.get_climate_devices()

            wave_status_thermostat = "off"
            for climate_device_id, thermostat in climate_devices.items():
                if thermostat.hvac_action == "heating":
                    wave_status_thermostat = "on"
                    log_message = (
                        f"Heat mode ON - trigger: {thermostat.name} - "
                        f"current temperature: {thermostat.current_temperature} - "
                        f"target temperature: {thermostat.target_temperature}"
                    )
                    log_manager.set_log(log_message, device=DEVICE_SALUS)
                    break
    except IT600ConnectionError:
        log_manager.set_log(
            "Connection error: check if you have specified gateway's IP address correctly.",
            device=DEVICE_SALUS,
            log_type=LOG_TYPE_ERROR,
        )
        sys.exit()
    except IT600AuthenticationError:
        log_manager.set_log(
            "Authentication error: check if you have specified gateway's EUID correctly.",
            device=DEVICE_SALUS,
            log_type=LOG_TYPE_ERROR,
        )
        sys.exit()
    except Exception as e:
        log_manager.set_log(
            f"An unexpected error occurred: {e}",
            device=DEVICE_SALUS,
            log_type=LOG_TYPE_ERROR,
        )
        sys.exit()

    # Salus logic to get data from bathroom smart button
    wave_status_button_bathroom = "off"
    if config_app.get("enabled_device_button_bathroom"):
        log_manager.set_log("Smart button run", device=DEVICE_SALUS)
        smart_button_bathroom = SmartButton()
        wave_status_button_bathroom = await smart_button_bathroom.get_heat_status()
        if wave_status_button_bathroom:
            log_manager.set_log(
                f"Smart button status: {wave_status_button_bathroom}",
                device=DEVICE_SALUS,
            )
        if wave_status_button_bathroom == "on":
            flag_manager.set_flag_namespace(
                {"last_date_button_bathroom_on": Helper.get_current_formatted_date()}
            )

    # Wave logic to run boiler
    log_manager.set_log("App run", device=DEVICE_WAVE)
    wave = WaveThermo(
        serial_number=config_wave.get("serial_number"),
        access_code=config_wave.get("access_code"),
        password=config_wave.get("password"),
    )
    await wave.status.update()
    temperature_set = None

    # Determine if heating should be turned on or off
    if wave_status_thermostat == "on" or wave_status_button_bathroom == "on":
        log_manager.set_log("Heat mode ON", device=DEVICE_WAVE)
        if wave.status.current_temp >= wave.status.set_point:
            temperature_set = wave.status.current_temp + 2
            log_manager.set_log(
                f"Heat mode ENABLE; Wave current: {wave.status.current_temp}; "
                f"setpoint: {wave.status.set_point}",
                device=DEVICE_WAVE,
            )
            flag_manager.set_flag_namespace(
                {"last_date_heat_on": Helper.get_current_formatted_date()}
            )
    elif wave.status.current_temp < wave.status.set_point:
        temperature_set = 17
        log_manager.set_log("Heat mode DISABLE", device=DEVICE_WAVE)

    log_manager.set_log("App run end", device=DEVICE_WAVE)

    # Set the new temperature if necessary
    if temperature_set is not None:
        await wave.set_temperature(temperature_set)
        await wave.status.update()
        log_manager.set_log(
            f"Temperature set to: {temperature_set}; Wave set temp: {wave.status.set_point}",
            device=DEVICE_WAVE,
        )

# Run the main function
asyncio.run(main())
