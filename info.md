# Adaptive Thermal Control

**Advanced predictive heating control for floor heating systems with machine learning and Model Predictive Control (MPC).**

## Features

- **Multi-Zone Control** - Support for multiple rooms/zones
- **PI Controller** - Stable temperature control with anti-windup
- **Fair-Share Power Allocation** - Respects boiler power limits
- **Preset Modes** - HOME, AWAY, SLEEP, MANUAL
- **Multiple Valve Types** - Support for number, switch, and valve entities

### Planned Features

- **1R1C Thermal Model** - Physics-based room thermal modeling
- **Model Predictive Control (MPC)** - Advanced predictive control
- **Weather Forecast Integration** - Proactive heating adjustments
- **Solar Irradiance** - Window orientation-aware solar gains
- **Energy Cost Optimization** - TOU tariff-aware heating

## Requirements

- **Home Assistant**: 2024.1.0 or newer
- **Python**: 3.13+
- Floor heating system with controllable valves
- Temperature sensors for each room

## Configuration

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "Adaptive Thermal Control"
4. Follow the configuration wizard:
   - Configure global settings (optional)
   - Add room thermostats

## Documentation

For detailed installation and configuration instructions, see the [full README](https://gitlab.com/YOUR_USERNAME/adaptive-thermal-control#readme).

## Support

- [GitLab Issues](https://gitlab.com/YOUR_USERNAME/adaptive-thermal-control/-/issues)
- [Documentation](https://gitlab.com/YOUR_USERNAME/adaptive-thermal-control/-/tree/main/docs)

---

**⚠️ Note**: This integration is in early development (Phase 1). Advanced features (MPC, weather integration) are planned for future releases.
