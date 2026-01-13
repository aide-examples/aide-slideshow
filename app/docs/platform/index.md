# Platform

Hardware selection, task distribution, and dependencies.

## Target Device Selection

We are looking for a cheap platform which can store a lot of images and display them via HDMI. It must be strong enough to host a small web server, so that we conveniently can upload images and control the device via a mobile phone. Furthermore the device should be small and energy efficient. It must allow to connect sensors for motion and darkness because we want to switch the system off when no human is around. Ideally we want to adapt brightness depending on ambient light. Maybe we also want to power on/off the display to save energy.

An ESP32 based system would be too weak, even if we had a storage card connected. So the natural choice is a Raspberry Pi. We aim to use the **Raspberry Pi Zero 2 WH** because it has everything we need:
- A multitasking OS
- HDMI output and USB ports
- GPIOs (to connect a motion sensor)
- An SD card which will be able to store thousands of images

However, there is not much memory (512 MB RAM).

### Why Not a Browser-Based Solution?

The original idea was to run a Chromium browser page in kiosk mode. Hardware access might be somewhat problematic, however, and we would need to install the full desktop OS to run the browser. Tests showed that it could work on an old Raspberry Pi 3B (similar processor as Zero 2 WH but 1024 MB of memory) but sometimes the screen was not refreshed properly, most probably due to memory bottlenecks.

So the choice went for a **Python script** which draws directly into the graphical memory using pygame and a suitable driver (`vc4-kms-v3d`). If we carefully set the limits for the GPU we will have sufficient memory for the Python process - which must not only read images but shall also handle a Web API and optionally be able to take commands from a classical infrared remote control.

### Development Environment

As is often the case with developing systems for tiny target hardware, we aim at being able to test the application within the development environment (Windows/WSL Ubuntu). Therefore we added hardware detection and bypassing for the Raspberry Pi-specific libraries. Hardware sensors are replaced by stubs.

## Task Assignment

We see the following tasks and plan to assign them to the platforms as follows:

| Task | Production | Development |
|------|------------|-------------|
| **Sliding images, controlling HDMI** | Python script on RPi Zero 2 WH | WSL/Ubuntu |
| **UI to control the slider** | Python script serves `index.html` on port 8080 | Same |
| **Display architecture documentation** | Python script serves `about.html` and docs | Same |
| **Image administration** | Filebrowser executable on port 8081 | Native file explorer |
| **Image preparation** | Integrated into slideshow (port 8080) | Same |

### Web UI Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  User's Device (Browser)                                     │
│  - Control UI (from :8080)                                   │
│  - File Browser (from :8081)                                 │
│  - Documentation viewer (from :8080/about)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Raspberry Pi                                                │
│  ┌──────────────────────┐  ┌──────────────────────┐         │
│  │  slideshow.py :8080  │  │  filebrowser :8081   │         │
│  │  - Web Control UI    │  │  - File Management   │         │
│  │  - Image Preparation │  │  - Upload/Download   │         │
│  │  - Documentation     │  └──────────────────────┘         │
│  │  - REST API          │                                    │
│  └──────────────────────┘                                    │
└─────────────────────────────────────────────────────────────┘
```

## Related Documentation

- [Hardware Details](hardware.md) - Raspberry Pi specifics, GPIO, display
- [Dependencies](dependencies.md) - Python packages, system libraries
