# Telekom Speedport (for Home Assistant)

[![GitHub Release](https://img.shields.io/github/release/FaserF/ha-speedport.svg?style=flat-square)](https://github.com/FaserF/ha-speedport/releases)
[![License](https://img.shields.io/github/license/FaserF/ha-speedport.svg?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-custom-orange.svg?style=flat-square)](https://hacs.xyz)
[![Add to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=speedport)
[![CI Orchestrator](https://img.shields.io/github/actions/workflow/status/FaserF/ha-speedport/ci-orchestrator.yml?label=CI)](https://github.com/FaserF/ha-speedport/actions/workflows/ci-orchestrator.yml)

A high-performance, modern Home Assistant integration for Telekom Speedport routers. Monitor your internet connection, track connected devices, manage WiFi, and control your router directly from Home Assistant.

> [!IMPORTANT]
> **Testing Disclaimer**: This integration is primarily developed and tested using a **Speedport W 724V**. While it is designed to be theoretically compatible with all Speedport routers using the native web API, I cannot guarantee full functionality for other models. Bug reports for other models can only be addressed with limited support as I lack the hardware for live testing.

---

## 🧭 Quick Links

| | | | |
| :--- | :--- | :--- | :--- |
| [✨ Features](#-features) | [📦 Installation](#-installation) | [⚙️ Configuration](#-configuration) | [🛠️ Options](#-options) |
| [🧱 Entities](#-entities) | [📶 Supported Models](#-supported-models) | [🧑‍💻 Development](#-development) | [📄 License](#-license) |

### Why use this integration?
Most Telekom Speedport routers are closed systems with limited external access. This integration uses the native web interface APIs (JSON-based) to provide real-time monitoring and control without needing any special firmware or hacks. It is designed to be stable, lightweight, and fully compatible with modern Home Assistant standards.

## 📶 Supported Models

| Model | Status | Notes |
| :--- | :--- | :--- |
| **Speedport W 724V** | ✅ **Tested** | Primary development model. |
| **Speedport Smart 4R Typ A** | ✅ **Tested** | Confirmed working by user ([#10](https://github.com/FaserF/ha-speedport/issues/10)). |
| Speedport Smart 3 / 4 | ⚠️ Theoretical | Should work via encrypted API, but untested. |
| Speedport Pro / Pro Plus | ⚠️ Theoretical | Should work via encrypted API, but untested. |
| Other W / Neo models | ⚠️ Theoretical | Basic sensors should work. |

## ✨ Features

- **Real-time Monitoring**:
  - Track **Online Status**, **Public IP (IPv4/IPv6)**, and **DSL Sync speeds**.
  - Monitor live **Internet Throughput** (Download/Upload rates).
  - Track the number of **Connected Devices**.
- **WiFi Management**:
  - Toggle **Main WiFi** and **Guest WiFi** via switches.
  - View **SSIDs** for 2.4 GHz, 5 GHz, and Guest networks.
  - Trigger **WPS Pairing** via a button.
- **Router Control**:
  - **Reboot** the router directly from HA.
  - Trigger an **Internet Reconnect** to get a new IP address.
- **Device Tracking**:
  - Automatically discovers and tracks all devices connected to the router.
  - Provides reliable presence detection for your home network.
- **Native Experience**:
  - **Full Localization**: English and German translations included.
  - **Visit Button**: Direct link to your router's web interface from the device page.
  - **Firmware & Model**: Accurate display of your router's hardware model and current firmware version.

## 📦 Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=FaserF&repository=ha-speedport&category=integration)

1. Open HACS in Home Assistant.
2. Click on the three dots in the top right corner and select **Custom repositories**.
3. Add `https://github.com/FaserF/ha-speedport` with category **Integration**.
4. Search for "Speedport".
5. Install and restart Home Assistant.

### Manual Installation

1. Download the latest release from the [Releases page](https://github.com/FaserF/ha-speedport/releases).
2. Extract the `custom_components/speedport` folder into your Home Assistant's `custom_components` directory.
3. Restart Home Assistant.

## ⚙️ Configuration

1. Navigate to **Settings > Devices & Services** in Home Assistant.
2. Click **Add Integration** and search for **Telekom Speedport**.
3. Enter your router's **IP Address** (usually `192.168.2.1` or `speedport.ip`) and your **Router Password**.

## 🛠️ Options

Click **Configure** on the integration page to adjust the **Update Interval** (default: 30 seconds).

## 🧱 Entities

The integration provides the following entities (depending on your router model):

| Platform | Entity | Description |
| :--- | :--- | :--- |
| **Sensor** | Router State | Current state of the router system. |
| **Sensor** | Online Status | Detailed connectivity status. |
| **Sensor** | Public IPv4/v6 | Your external IP addresses. |
| **Sensor** | DSL Up/Down | Synchronized DSL speeds. |
| **Sensor** | Internet Up/Down | Real-time traffic throughput. |
| **Sensor** | Internet Uptime | When the current session started. |
| **Sensor** | DSL PoP | The DSL access point (Point of Presence). |
| **Binary Sensor** | Internet Connection | Overall connectivity status. |
| **Binary Sensor** | DSL Link / WiFi | State of the physical link and radios. |
| **Switch** | WiFi / Guest WiFi | Control your wireless networks. |
| **Button** | Reboot / Reconnect | Remote management controls. |
| **Button** | WPS Pairing | Trigger WPS connection process. |
| **Update** | Firmware Update | Monitor and install router updates. |
| **Device Tracker** | [Device Name] | Presence tracking for all network clients. |

## 🧑‍💻 Development

This project uses modern Python development tools:
- `ruff` for linting and formatting
- `mypy` for static typing
- `pytest` for unit testing

### Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_test.txt
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
