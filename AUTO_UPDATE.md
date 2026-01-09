# Remote Update System für AIDE Slideshow

## Übersicht

Pull-basiertes Update-System mit:
- Version-Check gegen GitHub
- Manueller Download und Installation (User entscheidet immer)
- Automatischer Rollback bei Fehlstart (max. 2 Versuche)
- Erkennung wenn lokale Version neuer als Remote

## Architektur: `app/` Verzeichnis mit Symlink

Alle updatebaren Dateien liegen in `./app/`. Auf dem Pi wird `app/` per Symlink auf `/data/app/` verlinkt.

```
Repository & Dev-Umgebung:
aide-slideshow/
├── app/                      ← Updatebare Dateien
│   ├── slideshow.py
│   ├── imgPrepare.py
│   ├── static/
│   │   ├── index.html
│   │   ├── prepare.html
│   │   ├── about.html
│   │   └── update.html      ← NEU: Update-UI
│   ├── README.md
│   └── VERSION
├── img/                      ← Bilder (Dev: lokal)
├── config.json               ← Nutzerspezifisch, NICHT updatebar
├── slideshow.service
└── CHECKSUMS.sha256          ← Checksums für Update-Verifikation

Raspberry Pi (Production):
/home/pi/aide-slideshow/      ← Read-only (overlayroot)
├── app -> /data/app          ← Symlink!
├── img -> /data/img          ← Symlink (bereits vorhanden)
├── config.json               ← Bleibt hier (read-only aber selten geändert)
└── slideshow.service

/data/
├── app/                      ← Beschreibbar, Updates landen hier
│   ├── slideshow.py
│   ├── imgPrepare.py
│   ├── static/
│   ├── README.md
│   └── VERSION
├── img/                      ← Bilder
└── .update/                  ← Update-State
    ├── state.json
    ├── backup/
    └── staging/
```

**Einstiegspunkt:** `python app/slideshow.py` (oder `python3 app/slideshow.py`)

**Vorteile:**
- Gleiche Struktur in Dev und Production
- In Dev funktioniert alles ohne Symlinks
- Auf Pi: Nur `app/` und `img/` sind Symlinks
- config.json bleibt nutzerspezifisch und wird nicht überschrieben

## Versionierung

**VERSION Datei** (in `app/`):
```
1.2.0
```

**Vergleichslogik:**
```python
from packaging.version import Version

if Version(remote) > Version(local):
    "Update available: {local} → {remote}"
elif Version(remote) < Version(local):
    "Local version ahead of remote (development mode)"
else:
    "Up to date"
```

## Update-Flow

```
1. CHECK     User klickt "Check for Updates"
             → GET /api/update/check
             → Vergleiche VERSION mit GitHub
             → Zeige Ergebnis (neuer/gleich/älter)

2. DOWNLOAD  User klickt "Download Update" (nur wenn neuer)
             → POST /api/update/download
             → Lade Dateien nach /data/slideshow/.update/staging/
             → Verifiziere SHA256 Checksums

3. APPLY     User klickt "Install Update"
             → POST /api/update/apply
             → Backup aktuelle Version nach .update/backup/
             → Kopiere staging/ nach /data/slideshow/
             → Setze state.json: pending_verification = true
             → Restart slideshow.service (KEIN Reboot nötig)

4. VERIFY    Nach erfolgreichem Start (60s stabil)
             → Setze pending_verification = false
             → Lösche staging/
             → Log success

   ROLLBACK  Falls Start fehlschlägt:
             → consecutive_failures++
             → Wenn < 2: Restore von backup/, restart
             → Wenn >= 2: STOPP, Updates deaktivieren, Alert
```

## Rollback-Sicherheit

```json
// /data/slideshow/.update/state.json
{
  "current_version": "1.2.0",
  "pending_verification": false,
  "consecutive_failures": 0,
  "updates_disabled": false,
  "backup_version": "1.1.0",
  "last_check": "2026-01-09T10:00:00Z",
  "last_update": "2026-01-08T15:00:00Z"
}
```

**Endlosschleifen-Schutz:**
- Max 2 Rollback-Versuche
- Nach 2 Fehlern: `updates_disabled = true`
- User muss manuell eingreifen (SSH oder Web-UI zeigt Warnung)

## API Endpoints

| Endpoint | Method | Beschreibung |
|----------|--------|--------------|
| `/api/update/status` | GET | Aktueller Status, Versionen, ob Update verfügbar |
| `/api/update/check` | POST | Prüft GitHub auf neue Version |
| `/api/update/download` | POST | Lädt Update herunter und staged es |
| `/api/update/apply` | POST | Installiert gestagtes Update, Restart |
| `/api/update/rollback` | POST | Manueller Rollback zur Backup-Version |
| `/api/update/enable` | POST | Re-aktiviert Updates nach Fehlern |

## GitHub Integration

**Source:** Raw files von GitHub main branch, Unterverzeichnis `app/`

```python
GITHUB_RAW = "https://raw.githubusercontent.com/aide-examples/aide-slideshow/main/app"

files_to_update = [
    "VERSION",
    "slideshow.py",
    "imgPrepare.py",
    "README.md",
    "static/index.html",
    "static/prepare.html",
    "static/about.html",
    "static/update.html",
]
```

**Checksum-Datei** (`app/CHECKSUMS.sha256`):
```
a1b2c3d4...  slideshow.py
e5f6g7h8...  imgPrepare.py
i9j0k1l2...  README.md
```

## Dateien zu erstellen/ändern

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `app/VERSION` | Versionsnummer |
| `app/CHECKSUMS.sha256` | SHA256 Checksums aller Update-Dateien |
| `app/static/update.html` | Web-UI für Update-Management |

### Zu verschiebende Dateien

| Von | Nach |
|-----|------|
| `slideshow.py` | `app/slideshow.py` |
| `imgPrepare.py` | `app/imgPrepare.py` |
| `static/` | `app/static/` |
| `README.md` | `app/README.md` |
| `sample_images/` | `app/sample_images/` |

### Zu ändernde Dateien

| Datei | Änderung |
|-------|----------|
| `app/slideshow.py` | UpdateManager Klasse, API Endpoints, Health-Check, Pfad-Anpassungen |
| `slideshow.service` | ExecStart auf `app/slideshow.py` ändern |
| `app/static/index.html` | Version-Anzeige, Link zu Update-UI |
| `config.json` | Update-Konfiguration hinzufügen (bleibt im Root) |

## Config-Erweiterung

```json
{
  "update": {
    "enabled": true,
    "source": {
      "repo": "aide-examples/aide-slideshow",
      "branch": "main"
    },
    "auto_check_hours": 24,
    "auto_check": true,
    "auto_download": false,
    "auto_apply": false
  }
}
```

## Migrations-Script (auf dem Raspberry Pi)

Einmalig auszuführen nach dem Deployment um `app/` auf `/data/app/` zu verlinken:

```bash
#!/bin/bash
# setup-pi-symlinks.sh
# Auf dem Raspberry Pi ausführen (nach erstem Clone/Deployment)

SLIDESHOW_DIR="/home/pi/aide-slideshow"

# 1. Kopiere app/ nach /data/app (falls noch nicht vorhanden)
if [ ! -d "/data/app" ]; then
    sudo cp -r "$SLIDESHOW_DIR/app" /data/app
    sudo chown -R pi:pi /data/app
fi

# 2. Ersetze app/ durch Symlink
rm -rf "$SLIDESHOW_DIR/app"
ln -s /data/app "$SLIDESHOW_DIR/app"

# 3. Erstelle Update-Verzeichnis
mkdir -p /data/.update/{backup,staging}

# 4. img/ Symlink (falls noch nicht vorhanden)
if [ ! -L "$SLIDESHOW_DIR/img" ]; then
    mv "$SLIDESHOW_DIR/img" /data/img 2>/dev/null || true
    ln -s /data/img "$SLIDESHOW_DIR/img"
fi

# 5. Systemd Service neu laden
sudo systemctl daemon-reload
sudo systemctl restart slideshow

echo "Done! app/ -> /data/app, img/ -> /data/img"
```

## Implementierungs-Phasen

### Phase 0: Restrukturierung
- [ ] `app/` Verzeichnis erstellen
- [ ] Dateien verschieben: slideshow.py, imgPrepare.py, static/, README.md, sample_images/
- [ ] Pfade in slideshow.py anpassen (config.json, img/ relativ zu parent)
- [ ] slideshow.service anpassen: `ExecStart=python3 app/slideshow.py`
- [ ] Testen dass alles in Dev-Umgebung funktioniert

### Phase 1: Grundstruktur
- [ ] `app/VERSION` Datei erstellen (z.B. "1.0.0")
- [ ] UpdateManager Klasse in slideshow.py
- [ ] state.json Handling (unter `.update/` neben `app/`)
- [ ] `/api/update/status` Endpoint

### Phase 2: Version-Check
- [ ] GitHub Raw API Integration
- [ ] Versions-Vergleich (inkl. "ahead" Erkennung)
- [ ] `/api/update/check` Endpoint

### Phase 3: Download & Staging
- [ ] Datei-Download von GitHub Raw
- [ ] Checksum-Verifikation
- [ ] Staging nach `.update/staging/`
- [ ] `/api/update/download` Endpoint

### Phase 4: Apply & Rollback
- [ ] Backup-Mechanismus (nach `.update/backup/`)
- [ ] Atomic Apply (Dateien kopieren)
- [ ] Service-Restart (via subprocess)
- [ ] Health-Check nach Start (60s stabil)
- [ ] Automatischer Rollback bei Fehler
- [ ] Endlosschleifen-Schutz (max 2 Versuche)

### Phase 5: Web-UI
- [ ] `app/static/update.html` erstellen
- [ ] Version in index.html anzeigen
- [ ] Update-Benachrichtigung

### Phase 6: Dokumentation
- [ ] README.md Update-Sektion
- [ ] Pi-Setup Anleitung mit Symlinks

## Verifikation

Nach Implementation testen:

1. **Version-Check:** `curl http://pi:8080/api/update/status`
2. **Ahead-Erkennung:** Lokale VERSION auf höher setzen, check ausführen
3. **Download:** Update downloaden, staging/ prüfen
4. **Apply:** Update installieren, Service startet neu
5. **Rollback:** slideshow.py absichtlich kaputt machen, Apply, Rollback beobachten
6. **Endlosschleifen-Schutz:** 3x fehlschlagen lassen, updates_disabled prüfen
