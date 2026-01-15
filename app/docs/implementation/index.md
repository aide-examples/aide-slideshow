# Application Components

Overview of slideshow-specific modules and their responsibilities.

## Code Structure

```
app/
├── slideshow.py          # Main entry point, Slideshow class, pygame loop
├── imgPrepare.py         # Image preprocessing utilities
├── VERSION               # Current version number
│
├── aide_frame/           # Reusable application framework
│   ├── __init__.py
│   ├── log.py            # Centralized logging
│   ├── paths.py          # Path management with register()
│   ├── config.py         # Configuration loading
│   ├── platform_detect.py # Platform detection (raspi/wsl2/linux/etc.)
│   └── update.py         # GitHub-based remote updates
│
├── config/               # Application configuration
│   ├── __init__.py
│   └── app_config.py     # DEFAULT_CONFIG for slideshow
│
├── utils/                # Application-specific utilities
│   ├── __init__.py
│   └── helpers.py        # Welcome image, docs, path security
│
├── monitor/              # Monitor power control providers
├── motion/               # Motion detection providers
├── remote/               # Remote control input providers
├── static/               # Web UI files
├── docs/                 # Documentation files
└── sample_images/        # Demo images for first run
```

**Entry point:** `python3 app/slideshow.py`

## Module Dependencies

```mermaid
flowchart TB
    subgraph Framework["aide_frame/ (Reusable)"]
        log["log.py<br/><i>Logging</i>"]
        paths["paths.py<br/><i>Path management</i>"]
        config["config.py<br/><i>Config loading</i>"]
        platform["platform_detect.py<br/><i>Platform detection</i>"]
        update["update.py<br/><i>UpdateManager</i>"]
    end

    subgraph AppConfig["config/ (Configuration)"]
        app_config["app_config.py<br/><i>DEFAULT_CONFIG</i>"]
    end

    subgraph AppUtils["utils/ (Utilities)"]
        helpers["helpers.py<br/><i>Welcome image, docs</i>"]
    end

    subgraph Providers["Provider Packages"]
        monitor["monitor/<br/><i>MonitorControlProvider</i>"]
        motion["motion/<br/><i>MotionSensorProvider</i>"]
        remote["remote/<br/><i>RemoteControlProvider</i>"]
    end

    subgraph Main["Entry Point"]
        slideshow["slideshow.py<br/><i>Slideshow class, main()</i>"]
    end

    %% Framework internal
    update --> paths

    %% App utils depend on framework
    helpers --> log
    helpers --> paths

    %% Providers depend on framework
    monitor --> log
    motion --> log
    remote --> log
    remote --> paths
    remote --> helpers

    %% Main imports everything
    slideshow --> log
    slideshow --> paths
    slideshow --> config
    slideshow --> platform
    slideshow --> update
    slideshow --> app_config
    slideshow --> helpers
    slideshow --> monitor
    slideshow --> motion
    slideshow --> remote
```

**Dependency rules:**
- `aide_frame/` modules are self-contained and reusable across projects
- `utils/` contains application-specific code that depends on `aide_frame/`
- Provider packages depend only on `aide_frame.log` (and `paths`/`helpers` for http_api)
- `slideshow.py` is the composition root - it wires everything together

## Key Design Principles

| Principle | Description |
|-----------|-------------|
| **Framework Separation** | Generic infrastructure (`aide_frame/`) is separated from app-specific code (`utils/`) |
| **Plugin Architecture** | Each concern (monitor, motion, remote) has an abstract base class with multiple provider implementations |
| **Lazy Loading** | Heavy dependencies (PIL, fauxmo, etc.) are only imported when needed |
| **Platform Abstraction** | Hardware-specific code gracefully falls back to no-ops on unsupported platforms |
| **Centralized Logging** | All modules use `from aide_frame.log import logger` for consistent output |
