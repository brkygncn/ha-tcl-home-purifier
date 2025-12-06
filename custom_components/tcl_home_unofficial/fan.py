"""Fan platform for the TCL Breeva Air Purifier."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import ordered_list_item_to_percentage, percentage_to_ordered_list_item

# Import necessary constants and base classes from your integration
# NOTE: Check if your base class is named 'TCLDevice' or 'TclEntityBase' and adjust the import/class definition if needed.
from .const import DOMAIN, DeviceTypeEnum # Assuming you have DeviceTypeEnum available
from .tcl_entity_base import TCLDevice # Assuming TCLDevice is your base entity class
from .device_features import DeviceFeatures # Assuming DeviceFeatures is used for setup

_LOGGER = logging.getLogger(__name__)

# --- Breeva A5 Mode and Speed Definitions ---

# TCL workMode values based on common TCL air purifier systems (check against logs if errors occur)
TCL_MODE_AUTO = 0
TCL_MODE_SLEEP = 1
TCL_MODE_MANUAL = 2 # Setting a manual speed often requires switching to this mode

# Mapping from TCL values to Home Assistant standard names
HA_PRESET_AUTO = "Auto"
HA_PRESET_SLEEP = "Sleep"
HA_PRESET_MANUAL = "Manual"

# List of supported modes for HA
SUPPORTED_PRESET_MODES = [HA_PRESET_AUTO, HA_PRESET_SLEEP, HA_PRESET_MANUAL]

# Mapping HA preset name to TCL workMode integer
HA_PRESET_TO_TCL_MODE: dict[str, int] = {
    HA_PRESET_AUTO: TCL_MODE_AUTO,
    HA_PRESET_SLEEP: TCL_MODE_SLEEP,
    HA_PRESET_MANUAL: TCL_MODE_MANUAL,
}
TCL_MODE_TO_HA_PRESET: dict[int, str] = {v: k for k, v in HA_PRESET_TO_TCL_MODE.items()}


# Ordered list of speeds (1, 2, 3) for HA percentage calculation
ORDERED_FAN_SPEEDS = ["Low", "Medium", "High"]
TCL_SPEED_TO_HA_ITEM: dict[int, str] = {
    1: "Low",
    2: "Medium",
    3: "High",
}
HA_ITEM_TO_TCL_SPEED: dict[str, int] = {v: k for k, v in TCL_SPEED_TO_HA_ITEM.items()}


# --- Setup Function ---

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TCL Air Purifier fan from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id].coordinator
    entities: list[TCLBreevaFan] = []
    
    # NOTE: Ensure FAN_AIR_PURIFIER_CL is defined and correctly mapped in device_features.py and device.py
    if DeviceFeatures.FAN_AIR_PURIFIER_CL in coordinator.supported_features: 
        for device_id, device_data in coordinator.data.items():
            # You might need to check the device category/type here, e.g., if device_data.get("category") == "CL":
            if coordinator.devices.get(device_id).device_type == DeviceTypeEnum.AIR_PURIFIER_CL:
                entities.append(TCLBreevaFan(coordinator, device_id))

    async_add_entities(entities, update_before_add=False)


# --- Fan Entity Class ---

class TCLBreevaFan(TCLDevice, FanEntity):
    """Representation of a TCL Breeva Air Purifier."""

    def __init__(self, coordinator, device_id):
        """Initialize the Breeva Fan entity."""
        # Assuming TCLDevice handles unique_id and name based on device_id
        super().__init__(coordinator, device_id)
        
        self._attr_supported_features = (
            FanEntityFeature.TURN_ON | 
            FanEntityFeature.TURN_OFF |
            FanEntityFeature.SET_SPEED |  
            FanEntityFeature.PRESET_MODE 
        )
        self._attr_preset_modes = SUPPORTED_PRESET_MODES

    # --- STATE PROPERTIES (Reading Data) ---

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.coordinator.data[self.device_id].get("powerSwitch") == 1

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        speed = self.coordinator.data[self.device_id].get("windSpeed")
        if speed is None or speed not in TCL_SPEED_TO_HA_ITEM:
            return None
            
        ha_speed_item = TCL_SPEED_TO_HA_ITEM[speed]
        return ordered_list_item_to_percentage(ORDERED_FAN_SPEEDS, ha_speed_item)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        mode = self.coordinator.data[self.device_id].get("workMode")
        return TCL_MODE_TO_HA_PRESET.get(mode)

    # --- COMMAND METHODS (Writing Data) ---

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        """Turn on the device."""
        # 1. Turn on the power
        await self.coordinator.send_command(self.device_id, {"powerSwitch": 1})
        
        # 2. Set mode/speed if specified
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            # If turning on without specific settings, default to Auto mode
            await self.async_set_preset_mode(HA_PRESET_AUTO)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self.coordinator.send_command(self.device_id, {"powerSwitch": 0})

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan by percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return
            
        # 1. Convert HA percentage to one of the ordered list items ("Low", "Medium", "High")
        ha_speed_item = percentage_to_ordered_list_item(ORDERED_FAN_SPEEDS, percentage)
        
        # 2. Get the corresponding TCL integer speed (1, 2, or 3)
        tcl_speed = HA_ITEM_TO_TCL_SPEED.get(ha_speed_item)
        
        if tcl_speed is None:
            _LOGGER.error("Could not map percentage %s to TCL speed", percentage)
            return

        # 3. CRITICAL: Switch to Manual mode before setting speed
        await self.coordinator.send_command(self.device_id, {"workMode": TCL_MODE_MANUAL})
        
        # 4. Set the wind speed
        await self.coordinator.send_command(self.device_id, {"windSpeed": tcl_speed})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode not in SUPPORTED_PRESET_MODES:
            _LOGGER.error("Invalid preset mode requested: %s", preset_mode)
            return

        tcl_mode = HA_PRESET_TO_TCL_MODE.get(preset_mode)

        if tcl_mode is None:
            _LOGGER.error("Failed to map preset mode %s to TCL workMode", preset_mode)
            return
            
        # Ensure device is on if setting a mode
        if not self.is_on:
             await self.async_turn_on()
             
        # Set the work mode
        await self.coordinator.send_command(self.device_id, {"workMode": tcl_mode})
