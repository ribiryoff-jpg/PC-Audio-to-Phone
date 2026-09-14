# PC-Phone-Audio

Hear your PC on the Bluetooth earphones paired with your phone — over your
local Wi-Fi only. No Bluetooth needed on the PC, no account, no cloud.

```
PC (captures its own audio) --Wi-Fi--> Phone (browser) --> Bluetooth earphones
```

## Goal

Many desktop PCs have no Bluetooth, while everyone's earphones are already
paired with their phone. This project bridges that gap with a tiny local
server: the PC streams what it plays, the phone plays it on the Bluetooth
earphones. Everything stays inside your home network.

## Features

- **Two listening modes**: Instant (~0.1s delay, screen-on) and Background
  (MP3 stream that keeps playing with the screen locked, 2–5s delay)
- **Private by design**: LAN-only, fresh 6-digit PIN every run, temporary ban
  after repeated wrong attempts
- **Monochrome UI**: black/gray/white only, with dark and light themes
- **4 languages**: Arabic (RTL), English, Français, Español — with a
  first-run language picker on the desktop app and browser-language
  auto-detect on the phone page
- **Zero-install desktop app**: single `PC-Phone-Audio.exe` (~35MB),
  no Python required
- **No Bluetooth permissions needed** in the browser — pairing the earphones
  in the phone settings is enough

## Quick start (Windows app)

1. Download and run `PC-Phone-Audio.exe`.
2. On first launch, pick your language.
3. On the Windows firewall prompt, allow **private networks** only.
4. The window shows a **6-digit PIN**, a phone link and a QR code.
5. On your phone (same Wi-Fi): scan the QR or open the link, enter the PIN,
   choose a mode and press **Play**.
6. Play anything on the PC — you will hear it on the Bluetooth earphones.

Turn up three volumes together: the PC, the phone, and the page slider.

## Requirements

| PC | Phone |
|---|---|
| Windows 10/11, 64-bit | Same Wi-Fi network as the PC |
| ~40MB disk space | Modern browser (Chrome on Android, Safari on iOS) |
| A working default playback device | Bluetooth earphones paired with the phone |

No Python, no internet access, and no admin rights required for the `.exe`.
Closing the app window stops the server.

## Run from source

```bat
pip install -r requirements.txt
python app.py        :: desktop GUI
python server.py     :: CLI server (opens the dashboard in your browser)
start.bat            :: one-click: install deps + run CLI server
```

Options: `python server.py --test` (network test tone), `--mono`
(mono audio for weak networks), `--pin 123456`,
`--http-port 8000 --ws-port 8001`.

## How it works

- The server captures the default playback device via WASAPI loopback
  (`pyaudiowpatch`) in 10ms chunks.
- **Instant mode**: raw PCM over WebSocket, scheduled with the Web Audio API
  for minimal delay.
- **Background mode**: the same audio is encoded to MP3 (`lameenc`) and
  served as a radio-style HTTP stream that a native `<audio>` element plays —
  which is why it survives screen lock, with lock-screen controls.
- The phone page also requests a Wake Lock so the screen stays on in
  Instant mode.

## Security & privacy

- Binds to the LAN only. Do not forward the ports on your router and do not
  share the PIN outside your home.
- Use your private, password-protected home Wi-Fi — not an open public one.
- 8 wrong PINs from one address = 1-minute block. The `/info` endpoint
  (which reveals the PIN) answers to `127.0.0.1` only.

## Troubleshooting

| Problem | Fix |
|---|---|
| No sound on the phone | Same Wi-Fi on both; VPN off; press Play; nothing muted; try Chrome |
| Page won't open on the phone | Same Wi-Fi; allow Python/app in the firewall (private); disable VPN |
| Stuttering | Move closer to the router; close downloads; try `--mono` |
| 0.1–0.2s delay | Normal for network audio; fine for films/music, not for competitive games |
| Stops on screen lock | Use **Background** mode before locking |
| Aggressive battery saver kills it | Exempt Chrome from battery optimization |
| `pyaudiowpatch` install fails | `pip install pyaudiowpatch` manually, or `--test` to check the network |

## Project structure

```
app.py            Desktop GUI (tkinter): PIN, QR, links, start/stop
server.py         Audio capture + HTTP/WS/MP3 server + phone web page
requirements.txt  Python dependencies
start.bat         One-click source runner (Windows)
tools/            Dev utilities (icon generator)
icon.ico          App icon (build input)
PRODUCT.md        Product strategy (register, users, principles)
DESIGN.md         Visual system (monochrome tokens, components)
```

Build the `.exe` yourself:

```bat
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name PC-Phone-Audio --icon icon.ico --collect-all pyaudiowpatch app.py
```

## License

MIT — see [LICENSE](LICENSE).

## Author

Built and open-sourced by **[zexetdev](https://github.com/zexetdev)**.
