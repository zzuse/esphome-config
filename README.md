# esphome-config

Personal ESPHome configuration for a Waveshare ESP32-P4 WiFi6 Touch LCD 10.1 smart panel.
UI components come from the [esphome-modular-lvgl-buttons](esphome-modular-lvgl-buttons)
library, pulled in here as a git submodule.

## Layout

| Path | What it is |
|---|---|
| `my-panel.yaml` | Real device config (Waveshare ESP32-P4 hardware target) |
| `sim.yaml` | SDL simulator config for testing UI changes without hardware |
| `ui-shared.yaml` | Shared includes/config used by both `my-panel.yaml` and `sim.yaml` |
| `secrets.yaml` | Local secrets (wifi, coordinates) — gitignored, not in the repo |
| `secrets.yaml.example` | Template for `secrets.yaml` |
| `esphome-modular-lvgl-buttons/` | Submodule: the UI component library (own repo/history) |
| `docker-compose.yml` | start speech to text service `docker compose up -d` |

## Clone

This repo uses a git submodule, so clone with `--recurse-submodules`:

```bash
git clone --recurse-submodules <this-repo-url>
```

If you already cloned without that flag:

```bash
git submodule update --init --recursive
```

### Secrets

`secrets.yaml` is gitignored and not part of the repo. Create it from the template:

```bash
cp secrets.yaml.example secrets.yaml
```

Then fill in your wifi credentials and location:

```yaml
wifi_ssid: "your-ssid"
wifi_password: "your-wifi-password"
ap_password: "your-fallback-ap-password"
latitude: 0.0000
longitude: 0.0000
```

## Update

Pull the parent repo, then update the submodule to whatever commit the parent now points at:

```bash
git pull
git submodule update --init --recursive
```

To move the submodule forward to the *latest* upstream commit (not just what the parent
currently points at) and record that as a change in this repo:

```bash
cd esphome-modular-lvgl-buttons
git pull origin main
cd ..
git add esphome-modular-lvgl-buttons
git commit -m "Update esphome-modular-lvgl-buttons submodule"
```

## Build / flash / config / logs

Requires [ESPHome](https://esphome.io/) 2026.7.0+ and, for SVG image support, `cairosvg`
(`pip install cairosvg`).

```bash
esphome run my-panel.yaml      # flash the real device
esphome logs my-panel.yaml     # see logs
# After first build, use OTA update afterwards
esphome compile my-panel.yaml                                        # build only
esphome upload  my-panel.yaml --device waveshare-p4-lcd-10-1.local   # push an existing build
esphome logs    my-panel.yaml --device waveshare-p4-lcd-10-1.local   # just watch logs
```

Simulator

```bash
esphome run sim.yaml           # run the SDL simulator locally
esphome config sim.yaml > /tmp/sim.txt  # test config
esphome run sim-weather-shot.yaml # weather SDL simulator page
curl http://localhost:8080/screenshot > shot.png
```

## Further docs

- [esphome-modular-lvgl-buttons/README.md](esphome-modular-lvgl-buttons/README.md) — UI
  component library usage
- [esphome-modular-lvgl-buttons/ARCHITECTURE.md](esphome-modular-lvgl-buttons/ARCHITECTURE.md) —
  design rationale for the component library
- [INSTALL.md](INSTALL.md) — from-scratch tool setup, hardware include, and first flash
