# Hardware

Raspberry Pi specifics and GPIO pinout.

## Raspberry Pi Zero 2 WH

The target platform is the Raspberry Pi Zero 2 WH:

| Specification | Value |
|---------------|-------|
| **CPU** | Quad-core ARM Cortex-A53 @ 1GHz |
| **RAM** | 512 MB |
| **Video** | Mini HDMI |
| **GPIO** | 40-pin header (pre-soldered on WH model) |
| **Connectivity** | WiFi 802.11 b/g/n, Bluetooth 4.2 |
| **Storage** | MicroSD card |

### Memory Considerations

With only 512 MB RAM, memory management is critical:

- **GPU Memory Split**: Configure in `/boot/config.txt` with `gpu_mem=48` or similar
- **No Desktop Environment**: Run headless with pygame in kmsdrm mode
- **Image Loading**: Images are loaded one at a time, previous image is released before loading next
- **Lazy Imports**: Heavy libraries (PIL, fauxmo) are only imported when needed

## Display Connection

### Video Driver

The slideshow uses pygame with the `kmsdrm` video driver on Raspberry Pi:

```bash
# Verify DRM devices
ls /dev/dri/
# Typically: card0, card1, renderD128
```

If you get a black screen, try switching between `card0` and `card1` in the pygame initialization.

### HDMI-CEC

HDMI-CEC allows controlling the TV via the HDMI cable:

```bash
# Install CEC utilities
sudo apt install cec-utils

# Scan for devices
echo "scan" | cec-client -s -d 1

# Test commands
echo "standby 0" | cec-client -s -d 1  # TV off
echo "on 0" | cec-client -s -d 1       # TV on
```

See [Monitor Control](../implementation/slideshow/monitor-control.md) for configuration.

## GPIO Connections

### PIR Motion Sensor (HC-SR501)

| PIR Module | Raspberry Pi |
|------------|--------------|
| VCC | 5V (Pin 2) |
| GND | GND (Pin 6) |
| OUT | GPIO 17 (Pin 11) |

### IR Receiver (VS1838B)

| VS1838B | Raspberry Pi |
|---------|--------------|
| VCC | 3.3V (Pin 1) |
| GND | GND (Pin 6) |
| OUT | GPIO 18 (Pin 12) |

Requires kernel overlay in `/boot/config.txt`:
```
dtoverlay=gpio-ir,gpio_pin=18
```

### GPIO Relay Module

| Relay | Raspberry Pi |
|-------|--------------|
| VCC | 5V (Pin 2) |
| GND | GND (Pin 9) |
| IN | GPIO 27 (Pin 13) |

## GPIO Pinout Reference

```
                    3V3  (1) (2)  5V
          I2C SDA - GPIO2  (3) (4)  5V
          I2C SCL - GPIO3  (5) (6)  GND
                    GPIO4  (7) (8)  GPIO14 - UART TX
                      GND  (9) (10) GPIO15 - UART RX
   PIR Sensor OUT - GPIO17 (11) (12) GPIO18 - IR Receiver
                   GPIO27 (13) (14) GND     - Relay IN
                   GPIO22 (15) (16) GPIO23
                      3V3 (17) (18) GPIO24
         SPI MOSI - GPIO10 (19) (20) GND
         SPI MISO - GPIO9  (21) (22) GPIO25
         SPI SCLK - GPIO11 (23) (24) GPIO8  - SPI CE0
                      GND (25) (26) GPIO7  - SPI CE1
                   GPIO0  (27) (28) GPIO1
                   GPIO5  (29) (30) GND
                   GPIO6  (31) (32) GPIO12
                   GPIO13 (33) (34) GND
                   GPIO19 (35) (36) GPIO16
                   GPIO26 (37) (38) GPIO20
                      GND (39) (40) GPIO21
```

## Permissions

```bash
# For GPIO access
sudo usermod -aG gpio pi

# For IR input device
sudo usermod -aG input pi

# Logout and login again for changes to take effect
```
