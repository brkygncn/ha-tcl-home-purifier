from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)

# ... import other necessary base classes from the integration ...

class TCLBreevaFan(TCLDevice, FanEntity):
    """Representation of a TCL Breeva Air Purifier."""

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator, device_id)
        # You might need to set specific supported features here
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED | 
            FanEntityFeature.PRESET_MODE | 
            FanEntityFeature.TURN_ON | 
            FanEntityFeature.TURN_OFF
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.coordinator.data[self.device_id].get("powerSwitch") == 1

    @property
    def percentage(self) -> int:
        """Return the current speed as a percentage."""
        # Map windSpeed (e.g., 1, 2, 3) to percentage
        speed = self.coordinator.data[self.device_id].get("windSpeed", 1)
        return int(speed) * 33  # Assuming 3 speeds (33, 66, 100)

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        mode = self.coordinator.data[self.device_id].get("workMode")
        # You'll need to test what 0, 1, 2 correspond to (Auto, Sleep, etc.)
        if mode == 0: return "auto" 
        if mode == 1: return "sleep"
        return "standard"

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs) -> None:
        """Turn on the device."""
        # The integration likely has a send_command method
        await self.coordinator.send_command(self.device_id, {"powerSwitch": 1})
        
        if percentage:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the device."""
        await self.coordinator.send_command(self.device_id, {"powerSwitch": 0})

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        # Reverse map percentage to windSpeed (1, 2, 3)
        if percentage == 0:
            await self.async_turn_off()
            return
            
        speed = 1
        if percentage > 33: speed = 2
        if percentage > 66: speed = 3
        
        await self.coordinator.send_command(self.device_id, {"windSpeed": speed})
