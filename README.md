# Midea Boiler

Home Assistant custom integration for controlling Midea electric boilers (type 0xC1) via the Midea SmartHome cloud API.

## Features

- **Power on/off** — turn the boiler on or off
- **Set target temperature** — adjust the heating target temperature (30-80°C)
- **Current temperature** — read the current water temperature
- **Token refresh** — automatic token renewal via `tokenPwd` (no re-login needed)
- **Session persistence** — access token and refresh token saved in config entry, survives HA restarts
- **Config flow** — setup via UI (email + password + device selection)
- **Russian & English translations** included

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS:
   - Type: **Integration**
   -    URL: `https://github.com/Grind34/midea-boiler`
2. Click **Install**
3. Restart Home Assistant

### Manual

1. Copy the `custom_components/midea_boiler/` folder to your HA `custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Midea Boiler**
3. Enter your Midea SmartHome account email and password
4. Select your boiler from the device list
5. Done

## Supported Devices

- Midea electric boilers (device type `0xC1`)
- Tested with "Электрический котёл" on SmartHome cloud (app_id 1010)

## How It Works

The integration communicates with the Midea SmartHome cloud API (`mp-ru-prod.appsmb.com`) using:
- HMAC-SHA256 request signing
- Basic auth (app_key:iot_key)
- Lua control channel (`COMMON_LUA`) for device commands

### Token Management

- On first setup: full login with email/password → receives `accessToken` + `tokenPwd`
- On HA restart: reuses saved `accessToken` (no login needed)
- Before token expiry: proactive refresh via `/mj/user/autoLogin` with `tokenPwd`
- On session error (3106/3144): refresh → fallback to full login

## License

MIT
