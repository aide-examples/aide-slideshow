# Troubleshooting

Common issues and solutions.

## Display Issues

### Black Screen

```bash
# Check available GPU devices
ls /dev/dri/
# Typically shows: card0, card1, renderD128

# If you get a black screen, try switching between card0 and card1
# in the SDL video driver initialization
```

### Screen Not Refreshed

- Memory issue - check available RAM: `free -h`
- Try reducing `gpu_mem` in `/boot/config.txt`
- Ensure no desktop environment is running

### Wrong Resolution

```bash
# Check current display mode
tvservice -s

# List available modes
tvservice -m CEA
tvservice -m DMT
```

## Permission Issues

### GPIO Access Denied

```bash
# Add user to gpio group
sudo usermod -aG gpio pi

# Logout and login again
```

### IR Input Device Access Denied

```bash
# Add user to input group
sudo usermod -aG input pi

# Logout and login again
```

### CEC Access Denied

```bash
# Check if cec-utils is installed
which cec-client

# Test CEC manually
echo "scan" | cec-client -s -d 1
```

## Service Issues

### Check Service Status

```bash
sudo systemctl status slideshow
```

### View Logs

```bash
# Follow logs in real-time
journalctl -u slideshow -f

# View last 100 lines
journalctl -u slideshow -n 100

# View logs since last boot
journalctl -u slideshow -b
```

### Restart Service

```bash
sudo systemctl restart slideshow
```

### Service Won't Start

1. Check logs: `journalctl -u slideshow -n 50`
2. Try running manually: `python3 /home/pi/aide-slideshow/app/slideshow.py`
3. Check file permissions: `ls -la /home/pi/aide-slideshow/`
4. Check Python dependencies: `python3 -c "import pygame"`

## Network Issues

### Can't Access Web UI

```bash
# Check if service is running
sudo systemctl status slideshow

# Check if port is listening
netstat -tlnp | grep 8080

# Check firewall (if enabled)
sudo ufw status
```

### Alexa Can't Find Device

- Ensure Pi and Alexa are on same network/VLAN
- Check if SSDP port is listening: `netstat -ulnp | grep 1900`
- Try rediscovering: "Alexa, discover devices"

## CEC Issues

### CEC Not Working

```bash
# Scan for CEC devices
echo "scan" | cec-client -s -d 1

# If no devices found:
# - Check TV CEC is enabled (Samsung: "Anynet+")
# - Try different HDMI port
# - Some HDMI switches block CEC
```

### CEC Commands Ignored

```bash
# Test commands manually
echo "standby 0" | cec-client -s -d 1  # TV off
echo "on 0" | cec-client -s -d 1       # TV on

# Try different device IDs (0-15)
echo "standby 1" | cec-client -s -d 1
```

## IR Remote Issues

### No Events from Remote

1. Check wiring (VCC to 3.3V, not 5V for most receivers)
2. Verify kernel overlay: `dmesg | grep gpio_ir`
3. Check if overlay is in `/boot/config.txt`: `dtoverlay=gpio-ir,gpio_pin=18`
4. Reboot after making changes

### Testing IR Input

```bash
# Find IR input device
cat /proc/bus/input/devices | grep -A 5 "ir"

# Test key codes
ir-keytable -t -d /dev/input/event0

# Enable all protocols
ir-keytable -p all -d /dev/input/event0
```

## Memory Issues

### Out of Memory

```bash
# Check memory usage
free -h

# Check what's using memory
ps aux --sort=-%mem | head -10

# Reduce GPU memory in /boot/config.txt
gpu_mem=64
```

### Image Preparation Fails

- Large images use ~36MB each during processing
- Try processing fewer images at once
- Check available memory: `free -h`
- Restart slideshow to free memory

## Configuration Issues

### Config Not Loading

```bash
# Check JSON syntax
python3 -c "import json; json.load(open('config.json'))"

# Check file permissions
ls -la config.json
```

### Provider Not Found

- Check spelling in `config.json`
- Check if required library is installed
- Check logs for import errors

## Getting Help

If you can't resolve an issue:

1. Check logs: `journalctl -u slideshow -n 100`
2. Run with debug logging: `python3 slideshow.py --log-level DEBUG`
3. Report issue at: https://github.com/aide-examples/aide-slideshow/issues
