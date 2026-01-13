# Remote Update System

Downloading and applying updates from GitHub Releases.

## Features

- **Version checking** against GitHub Releases API
- **Tarball-based updates** - downloads complete release packages
- **Embedded aide_frame** - framework is included in updates
- **Manual download and installation** (user decides when to update)
- **Automatic rollback** on failure (max 2 attempts before disabling updates)
- **Development mode detection** (when local version is ahead of remote)
- **Web UI** at `/update` for easy management

## Architecture

Das Update-System nutzt GitHub Releases mit Build-Tarballs:

```
GitHub Release v1.3.0
├── Source code (zip)         ← Automatisch von GitHub (NICHT verwenden)
├── Source code (tar.gz)      ← Automatisch von GitHub (NICHT verwenden)
└── aide-slideshow-1.3.0.tar.gz  ← Build-Tarball (VERWENDEN)
```

Das Build-Tarball enthält `aide_frame/` eingebettet und wird mit `./build.sh --tarball` erstellt.

Siehe [aide_frame Architecture](../../aide_frame/docs/architecture.md) für Details zum Build- und Release-Prozess.

## Deployment Modes

Das Update-System funktioniert in beiden Szenarien:

### Simple Installation (ohne /data Partition)

```
/home/pi/
├── app/                    ← Updatebare Dateien (direkt beschreibbar)
│   ├── aide_frame/         ← Eingebettetes Framework
│   ├── slideshow.py
│   ├── VERSION
│   └── ...
├── .update/                ← Update-State und Backups
│   ├── state.json
│   ├── staging/
│   └── backup/
├── img/                    ← Bilder
└── config.json             ← User-Config (wird nicht updated)
```

### Production Installation (mit /data Partition und read-only root)

```
/home/pi/                   ← Read-only (overlayroot)
├── app -> /data/app        ← Symlink zu beschreibbarer Partition
├── img -> /data/img        ← Symlink zu beschreibbarer Partition
└── config.json

/data/                      ← Beschreibbare Partition
├── app/                    ← Updatebare Dateien
├── img/                    ← Bilder
└── .update/                ← Update-State und Backups
```

## Web UI

Zugang zur Update-Verwaltung unter `http://raspberrypi:8080/update`

Die UI zeigt:
- Aktuelle und verfügbare Version
- Update-Status (checking, downloading, staged, etc.)
- Buttons für Check, Download, Install, Rollback
- Re-enable Button falls Updates wegen Fehlern deaktiviert wurden

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/update/status` | GET | Aktueller Update-Status |
| `/api/update/check` | POST | Prüft GitHub auf neue Version |
| `/api/update/download` | POST | Lädt Update herunter und stagt es |
| `/api/update/apply` | POST | Wendet gestagtes Update an und startet neu |
| `/api/update/rollback` | POST | Rollback zur Backup-Version |
| `/api/update/enable` | POST | Reaktiviert Updates nach Fehlern |

## Configuration

In `config.json`:

```json
{
    "remote_update": {
        "source": {
            "repo": "aide-examples/aide-slideshow"
        }
    }
}
```

Optionale Einstellungen:

```json
{
    "remote_update": {
        "source": {
            "repo": "aide-examples/aide-slideshow",
            "use_releases": true
        },
        "service_name": "slideshow",
        "auto_check": true,
        "auto_check_hours": 24,
        "auto_download": false,
        "auto_apply": false
    }
}
```

| Setting | Description | Default |
|---------|-------------|---------|
| `source.repo` | GitHub Repository (owner/repo) | - |
| `source.use_releases` | GitHub Releases nutzen | `true` |
| `service_name` | Systemd Service Name für Restart | - |
| `auto_check` | Periodisch nach Updates prüfen | `true` |
| `auto_check_hours` | Stunden zwischen Auto-Checks | `24` |
| `auto_download` | Updates automatisch herunterladen | `false` |
| `auto_apply` | Updates automatisch installieren | `false` |

## Update Flow

```
1. CHECK     User klickt "Check for Updates"
             → Prüft GitHub Releases API
             → Vergleicht lokale VERSION mit Release-Tag

2. DOWNLOAD  User klickt "Download Update"
             → Lädt Release-Asset (aide-slideshow-X.Y.Z.tar.gz)
             → Extrahiert nach .update/staging/
             → Verifiziert erforderliche Dateien

3. APPLY     User klickt "Install Update"
             → Backup aktueller Dateien nach .update/backup/
             → Kopiert staging/ nach app/
             → Startet Slideshow-Service neu

4. VERIFY    Nach 60s stabilem Betrieb
             → Löscht pending_verification Flag
             → Räumt staging/ auf

   ROLLBACK  Bei Service-Fehler:
             → Stellt aus backup/ wieder her
             → Nach 2 Fehlern: deaktiviert Updates
```

## Rollback Safety

Das System enthält automatischen Rollback-Schutz:

- Vor dem Anwenden werden aktuelle Dateien nach `.update/backup/` gesichert
- Nach Neustart läuft ein 60-Sekunden Timer zur Stabilitätsprüfung
- Bei Service-Crash vor Verifizierung wird automatisch zurückgerollt
- Nach 2 aufeinanderfolgenden Fehlern werden Updates deaktiviert

## Neues Release erstellen

Kurz-Anleitung (Details in [aide_frame Architecture](../../aide_frame/docs/architecture.md)):

```bash
# 1. Version erhöhen
echo "1.3.1" > app/VERSION

# 2. Committen
git add -A && git commit -m "Bump to 1.3.1" && git push

# 3. Build
./build.sh --tarball

# 4. Tag
git tag v1.3.1 && git push origin v1.3.1

# 5. GitHub Release erstellen und Tarball hochladen
#    releases/aide-slideshow-1.3.1.tar.gz als Asset hochladen
```
