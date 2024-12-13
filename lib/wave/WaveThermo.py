from lib.wave.SetBot import SetBot
from lib.wave.StatusBot import StatusBot

class WaveThermo:

    def __init__(self, serial_number, access_code, password):
        self.status = StatusBot(serial_number=serial_number,
                                access_code=access_code,
                                password=password)

        self.setter = SetBot(serial_number=serial_number,
                             access_code=access_code,
                             password=password)

    async def set_mode(self, mode):
        """
        Set the control mode of the thermostat

        Parameters
        ----------
        mode : str
            Control mode, either "manual" or "clock"
        """
        await  self.setter.post_message("/heatingCircuits/hc1/usermode", mode)

    async def set_temperature(self, temperature):
        #await self.status.update()

        if self.status.program_mode == 'manual':
            await self.setter.post_message("/heatingCircuits/hc1/temperatureRoomManual", temperature)
        else:

            #https://gist.github.com/pszafer/20513389782d5bb50801106d0c5e36cb
            #https://github.com/bosch-thermostat/home-assistant-bosch-custom-component/issues/283

            
            await self.setter.post_message("/heatingCircuits/hc1/temperatureRoomManual", temperature)
            await self.setter.post_message("/heatingCircuits/hc1/manualTempOverride/status", "on")
            await self.setter.post_message("/heatingCircuits/hc1/manualTempOverride/temperature", temperature)

            #await self.setter.post_message("/heatingCircuits/hc1/manualTempOverride/temperature", temperature)

        #await self.status.update()
    async def override(self, b):
        if b:
            await self.setter.post_message("/heatingCircuits/hc1/manualTempOverride/status", 'on')
        else:
            await self.setter.post_message("/heatingCircuits/hc1/manualTempOverride/status", 'off')
    
    async def set_hot_water(self, b):
        await self.setter.post_message("/heatingCircuits/hc1/temperatureRoomManual", '15')