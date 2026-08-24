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
| `photo-page.yaml` | Kids-photo screensaver page (auto-shows on idle, tap to dismiss) |
| `photo-server/` | Container that serves random panel-sized JPEGs from a photo folder |
| `esphome-modular-lvgl-buttons/` | Submodule: the UI component library (own repo/history) |
| `docker-compose.yml` | speech-to-text + photo services, `docker compose up -d` |

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

## Kids-photo screensaver

`photo-page.yaml` adds a photo-frame page: after 5 minutes without touch input the panel
fades into a slideshow of random photos (a new one every 20 s); tapping anywhere returns
to the main page. The page is skipped by swipe navigation — it only appears on idle.
Timings and the server URL are substitutions at the top of `my-panel.yaml`.

Photos come from the `kids-photos` service in `docker-compose.yml` — a tiny HTTP server
(`photo-server/`) that returns a random image from a folder, EXIF-rotated and resized to
fit the 1280x800 screen (HEIC/iPhone photos supported). Point its volume at your photo
library — a local `./photos` folder, an SMB/NFS mount of the NAS share, or run the
compose file on the NAS itself — then set `photo_server_url` in `my-panel.yaml` to that
machine's IP:

```bash
docker compose up -d kids-photos
curl http://localhost:8128/health   # → "N photos"
curl -o test.jpg http://localhost:8128/photo
```

### Mounting a NAS share at `./photos`

The compose volume is `./photos:/photos:ro`, so the simplest setup is to mount the NAS
share at that path. Both `cifs-utils` (SMB) and `nfs-common` (NFS) ship with Ubuntu.

For SMB, keep the password out of `/etc/fstab` with a credentials file:

```bash
sudo tee /etc/cifs-photos.cred >/dev/null <<'EOF'
username=YOUR_NAS_USER
password=YOUR_NAS_PASSWORD
EOF
sudo chmod 600 /etc/cifs-photos.cred
```

Test the mount by hand before making it permanent — `uid`/`gid` should be your own
(`id -u`), so the files come through readable:

```bash
mkdir -p photos
sudo mount -t cifs //10.0.0.133/photo /home/zzuse/code/esphome-config/photos \
  -o credentials=/etc/cifs-photos.cred,ro,uid=1000,gid=1000,iocharset=utf8
ls photos/
```

Then add it to `/etc/fstab` so it survives reboots (one line):

```
//10.0.0.133/photo  /home/zzuse/code/esphome-config/photos  cifs  credentials=/etc/cifs-photos.cred,ro,uid=1000,gid=1000,iocharset=utf8,_netdev,nofail,x-systemd.automount  0  0
```

`sudo systemctl daemon-reload && sudo mount -a` applies it. `ro` is deliberate: the panel
never needs to write, so a read-only mount keeps the originals safe. `_netdev,nofail`
stops boot from hanging when the NAS is asleep, and `x-systemd.automount` mounts the share
lazily on first access instead of at boot.

Notes on things that bite:

- **`mount.cifs: bad UNC`** — the source must be a UNC path with forward slashes,
  `//10.0.0.133/photo`, not the NFS-style `10.0.0.133:/photo`.
- **Don't pin `vers=`.** Modern kernels negotiate SMB 3.1.1 and fall back to 3.0/2.1 on
  their own, and never try SMB1 unless asked. Add `vers=3.0` only if negotiation fails.
- **Use the IP, not the NAS hostname.** With SMB1 disabled, NetBIOS name resolution is off,
  so `//DISKSTATION/photo` won't resolve unless DNS or mDNS publishes the name.
- **Mount before starting the container.** Docker binds `./photos` with private mount
  propagation, so a share mounted *after* the container started stays invisible inside it —
  the server reports 0 photos while `ls photos/` shows files. Fix with
  `docker compose up -d --force-recreate kids-photos`.
- **New files take up to `RESCAN_SECONDS`** (10 min by default) to appear in the rotation.

A subdirectory works as a mount source too (`//10.0.0.133/photo/Family`), which is handy
when only part of the library belongs on the panel. To see what the NAS offers:
`sudo apt install smbclient && smbclient -L //10.0.0.133 -U YOUR_NAS_USER -m SMB3`.

For NFS the equivalent is `showmount -e 10.0.0.133` to list exports, then:

```
10.0.0.133:/volume1/photo  /home/zzuse/code/esphome-config/photos  nfs  ro,_netdev,nofail,x-systemd.automount  0  0
```

## Further docs

- [esphome-modular-lvgl-buttons/README.md](esphome-modular-lvgl-buttons/README.md) — UI
  component library usage
- [esphome-modular-lvgl-buttons/ARCHITECTURE.md](esphome-modular-lvgl-buttons/ARCHITECTURE.md) —
  design rationale for the component library
- [INSTALL.md](INSTALL.md) — from-scratch tool setup, hardware include, and first flash
