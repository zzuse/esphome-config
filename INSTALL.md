# INSTALL

From-scratch setup for flashing the Waveshare ESP32-P4 WiFi6 Touch LCD 10.1 panel in this
repo. For cloning/updating an *existing* checkout, see [README.md](README.md) — this doc
covers first-time tool setup and the first flash.

## 1. Install the tools

- **Python 3.11–3.13** from [python.org](https://www.python.org/) (Windows: check "Add to
  PATH" during install).
- **[VS Code](https://code.visualstudio.com/)**, then add the **ESPHome** extension from the
  marketplace (YAML validation/autocomplete for ESPHome configs).
- Open a VS Code terminal and install ESPHome into a virtual environment rather than
  globally:

  ```bash
  python -m venv esphome-env

  # Windows:
  esphome-env\Scripts\activate
  # macOS/Linux:
  source esphome-env/bin/activate

  pip install esphome
  ```

  Use the **latest** ESPHome release — ESP32-P4 + MIPI-DSI display support is recent
  (this repo's [esphome-modular-lvgl-buttons](esphome-modular-lvgl-buttons) library requires
  2026.7.0+ for its `image:` component; the Waveshare 10.1" hardware profile itself needs
  2026.5.0+). Old versions won't compile.

## 2. Get the project

If you're setting up this existing repo, follow the **Clone** and **Secrets** sections in
[README.md](README.md) (`git clone --recurse-submodules ...`, then `cp
secrets.yaml.example secrets.yaml` and fill in your wifi/location).

If you're instead starting a *new* panel project from scratch and just want the component
library:

```bash
mkdir esphome-config && cd esphome-config
git clone https://github.com/agillis/esphome-modular-lvgl-buttons.git
```

then create `secrets.yaml` next to it:

```yaml
wifi_ssid: "YourWiFi"
wifi_password: "YourPassword"
ap_password: "fallback-password"
```

and copy the closest example config as your starting device file:

```bash
cp esphome-modular-lvgl-buttons/example_code/waveshare-esp32-p4-wifi6-touch-lcd-10.1_display_modular.yaml my-panel.yaml
```

(In this repo, that step is already done — `my-panel.yaml` is the real device config, and
`sim.yaml` is the SDL-simulator equivalent for testing without hardware.)

## 3. Understand the hardware include

The line doing the heavy lifting in `my-panel.yaml` is the hardware package — it configures
the MIPI-DSI display driver, GT911 touchscreen, backlight, and the ESP32-C6 WiFi co-processor
link in one shot:

```yaml
packages:
  hardware: !include
    file: esphome-modular-lvgl-buttons/hardware/waveshare-esp32-p4-wifi6-touch-lcd-10.1.yaml
```

Other boards' hardware profiles live alongside it in
[`esphome-modular-lvgl-buttons/hardware/`](esphome-modular-lvgl-buttons/hardware) if you ever
swap panels.

## 4. Wire up your own entities

Buttons/tiles are added as ESPHome packages under `packages:` in `my-panel.yaml`, each
pointing at a UI component from the submodule with `vars:` for that tile's position and
target entity. For example:

```yaml
button_1: !include
  file: esphome-modular-lvgl-buttons/ui/switch/remote.yaml
  vars:
    uid: button_1
    row: 0
    column: 0
    text: Light
    icon: $mdi_lightbulb
    entity_id: "switch.athom_smart_plug_v3_50ebc0_switch"
```

Edit the `entity_id:` values (and `text`/`icon`) to match your own Home Assistant entities,
add more tiles by copying a block and pointing `file:` at another component under
`esphome-modular-lvgl-buttons/ui/<type>/`, or delete tiles you don't need. See
[esphome-modular-lvgl-buttons/README.md](esphome-modular-lvgl-buttons/README.md) for the
full list of available entity types (`switch`, `light`, `sensor`, `climate`, `button`, …)
and what each one supports.

## 5. First flash

Connect the board over USB, then from the activated venv:

```bash
esphome run my-panel.yaml
```

The first run needs a USB connection to install initial firmware; ESPHome will prompt you to
pick the serial port. After that, ESPHome can flash over WiFi (OTA) as long as the device is
online — subsequent `esphome run` calls will offer the network address as an option.

Want to iterate on the UI without hardware? Run the SDL simulator instead:

```bash
esphome run sim.yaml
```
