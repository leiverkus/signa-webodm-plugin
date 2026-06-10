# CLAUDE.md

Kontextdatei für Claude Code. Liegt im Wurzelverzeichnis des Find-GCP/WebODM-Workflow-Projekts und wird von Claude Code automatisch beim Start gelesen.

## Projektzweck

Automatisierter Workflow zur Bearbeitung archäologischer Drohnenbefliegungen im Südlevante-Kontext: ArUco-GCP-Detektion mit [Find-GCP](https://github.com/zsiki/Find-GCP), Aufbereitung für WebODM (Engine: ODX), Integration in den Solearis-Stack (PostGIS/GeoDjango/QFieldCloud).

Eingaben:
- Drohnenbilder (DJI Phantom 4 Pro, Mavic 3E o.ä.)
- ArUco-Marker, GNSS-eingemessen oder via DISTO/Totalstation
- GCP-Koordinatendatei (Format: `id easting northing elevation`)

Ausgaben:
- `gcp_list.txt` (ODM-kompatibles GCP-File)
- WebODM-bereite Ordnerstruktur
- Optional: direkter API-Upload zu WebODM

## Tech Stack & Konventionen

- **Shell**: Bash 4+, `set -euo pipefail`, `IFS=$'\n\t'`
- **Python**: 3.10+, OpenCV mit aruco-contrib (`opencv-python` + `opencv-contrib-python`)
- **GIS**: QGIS 3.34+ LTR, GDAL/OGR CLI, PROJ
- **Photogrammetrie**: WebODM mit ODX-Engine (nicht ODM), NodeODX
- **Tests**: `bash -n` für Syntax, `shellcheck` für Lints

Code-Style:
- Bash-Skripte mit Hilfsfunktionen `log()`, `warn()`, `err()` für konsistentes Logging
- Argument-Parsing als langer `case`-Block, lange + kurze Flags
- Defaults am Skriptanfang als grossgeschriebene Variablen, env-überschreibbar
- Pfade: `$IMAGES`, `$OUTPUT` – nie hardcoded
- README/Reports: deutschsprachig, Code-Kommentare englisch

## Koordinatensysteme (kritisch — bitte nie raten)

Standard-CRS-Tabelle für regionale Sites:

| EPSG     | Name                         | Wann?                                  |
|----------|------------------------------|----------------------------------------|
| **28191**| Palestine 1923 / Palestine Belt | Solearis-Default, Westbank, Jerusalem |
| **2039** | Israeli Transverse Mercator (ITM) | modernes IL-Standard-CRS              |
| **32636**| UTM Zone 36N                 | generisch Israel                       |
| **32637**| UTM Zone 37N                 | Jordanien (Tall Zira'a, Khirbet Hamra Ifdan, Amman, Irbid) |
| **4326** | WGS84 geographisch           | nur als Eingabe-CRS aus EXIF-GPS       |

CRS-Regeln:
1. GCP-Koordinaten **immer** im Ziel-CRS einmessen oder vorab transformieren — nie WebODM die Umrechnung machen lassen.
2. Bilder-EXIF (WGS84) und GCP-CRS dürfen verschieden sein, ODX rechnet das EXIF intern um.
3. Vor jedem Run: `head -1 gcp_coords.txt` und `--epsg`-Flag gegenchecken.
4. Bei neuen Sites in dieser Tabelle ergänzen, nicht ad hoc.

## Datei- & Ordnerstruktur

```
fieldwork/
├── <site>-<jahr>/                    # z.B. zira2026, hamra-ifdan-2026
│   ├── raw/                          # Original-Drohnenbilder (read-only behandeln)
│   ├── gcp_coords.txt                # einmalig per Site, GNSS/DISTO-eingemessen
│   ├── processed/
│   │   ├── gcp_list.txt              # Find-GCP-Output
│   │   ├── gcp_report.txt            # Sanity-Report
│   │   ├── findgcp_<timestamp>.log
│   │   └── webodm_ready/             # bei --prep
│   │       ├── images/               # Symlinks!
│   │       ├── gcp_list.txt
│   │       └── README_webodm.md
│   └── notes.md                      # site-spezifische Notizen
└── findgcp-webodm.sh                 # Hauptskript
```

Symlinks statt Copy: bei 1000+ Bildern × 20–60 MB sparen wir TB-Platz und I/O.

## Häufige Aufgaben für Claude Code

### Neuen Site-Workflow anlegen

Wenn ich sage „neuer Site `<name>`":
1. Ordnerstruktur unter `fieldwork/<name>-<jahr>/` anlegen
2. Leere `gcp_coords.txt` mit Header-Kommentar (CRS-Hinweis) erzeugen
3. `notes.md` mit Site-Metadaten-Template anlegen
4. CRS aus der Tabelle oben wählen, nicht raten — bei Unklarheit nachfragen

### Find-GCP Parameter tunen

Wenn die Detektion zu wenige Marker findet:
- `--minrate` schrittweise senken (0.01 → 0.008 → 0.005), nie unter 0.005
- `--ignore` zwischen 0.13 (default) und 0.33 (starkes Sonnenlicht)
- Bei 3×3-Custom-Markern `-d 99`, sonst `-d 1` (4×4) als Default
- Vor Parameter-Tuning: prüfen ob Markergröße im Bild physisch ausreicht (Faustregel: min. 20×20 px Seitenlänge)

Wenn zu viele False Positives:
- `--minrate` erhöhen
- Auf 4×4 oder grösser wechseln (3×3 hat mehr False Positives)
- Mit `gcp_check.py` visuell verifizieren und falsche Zeilen aus `gcp_list.txt` entfernen

### WebODM-Task-Optionen

Default-Profil (archäologisches Ortho + DEM, ausreichend RAM):
```yaml
feature-quality: high
pc-quality: high
matcher-neighbors: 16
mesh-octree-depth: 11
dem-resolution: 2.0
orthophoto-resolution: 1.5
crop: 3
optimize-disk-space: true
use-3dmesh: false
```

RAM-knapp-Profil (>500 Bilder, <16 GB):
```yaml
split: 200
split-overlap: 50
feature-quality: medium
pc-quality: medium
max-concurrency: 4
```

3D-Modell für Architektur/Tells:
```yaml
use-3dmesh: true
mesh-octree-depth: 12
texturing-data-term: gmi
```

### Solearis-Integration

Outputs aus WebODM in den Solearis-Stack einspielen:
- Orthomosaik: `gdalwarp -t_srs EPSG:28191 -of COG ...` für PostGIS-tauglichen COG
- DEM: gleiches Pattern, mit `-r bilinear`
- GCP-Reports: in PostGIS als Punktlayer für QField laden
- Tile-Generation: `gdal_translate -of MBTILES` für QField-Offline

### DistoField-Brücke

Wenn ich an DistoField (Flutter/Dart, Leica DISTO S910) anbinden will:
- Export-Format: `gcp_coords.txt` mit Komma- oder Whitespace-Separator
- Helmert-Transformation in DistoField hat Vorrang vor manueller Berechnung
- IDs in DistoField müssen mit gedruckten ArUco-IDs übereinstimmen — kein Auto-ID

## Was Claude Code NICHT tun soll

- **Keine Drittlibs hinzufügen** ohne Rückfrage. Wir bleiben bei OpenCV + Standard-Bash. Kein NumPy/Pandas im Skript-Layer.
- **Keine destructive Operations auf `raw/`** — niemals `rm`, `mv` oder Inplace-Bearbeitung der Originalbilder. EXIF nicht modifizieren.
- **Keine CRS-Transformation auf den Drohnenbildern** — die EXIF-GPS-Tags bleiben WGS84.
- **Keine Cloud-Uploads** zu Diensten ausserhalb der eigenen Infrastruktur (nicht zu LGT/WebODM Lightning, nicht zu Google Drive). Die Daten von Tall Zira'a u.a. bleiben lokal/auf Hetzner.
- **Keine Modifikation der Find-GCP-Sources** — wir nutzen das Repo als Submodule oder externe Installation, kein Patching.
- **Keine `latest`-Tags in Docker-Compose** — immer pinned Versionen für Reproduzierbarkeit.

## Bekannte Stolperstellen

1. **Burnt-in unter Levante-Sonne**: Default `--ignore 0.13` reicht im Sommer in Israel/Jordanien nicht. Auf 0.33 setzen, ggf. graue statt weisse Marker drucken (`aruco_make.py --gray`).

2. **DJI EXIF-Höhen**: relativ zum Take-off, nicht absolut. Das ist für ODX okay (Bündelblock korrigiert), aber nicht für direkte DEM-Validierung gegen GCP-Höhen.

3. **`gcp_check.py` braucht X11/Display**: auf headless Hetzner-Servern via X-Forwarding (`ssh -X`) oder VNC, oder per `--no-check` skippen.

4. **Marker auf Tells**: Reflexionen von Steinen mit ähnlicher Form lösen False Positives aus. Marker mind. 50 cm Abstand zu hellen Steinen, mit Ziegel/Pflöcken fixiert (nicht aufgelegt — wegklappen verfälscht Z).

5. **WebODM ODX vs. ODM**: seit April 2026 ist WebODM von OpenDroneMap entkoppelt. Wir nutzen `webodm/odx` und `webodm/nodeodx` Container, nicht `opendronemap/*`.

6. **Image-Glob case-sensitivity**: DJI schreibt `.JPG` (gross), Mavic 3E auch `.JPG`, Sony manchmal `.jpg`. Skript nutzt `nocaseglob`, aber bei manueller `find`-Verwendung dran denken.

## Offene Punkte / TODOs

- [ ] DistoField → `gcp_coords.txt` Export-Endpoint
- [ ] Helmert-2D-Validierung in einem separaten Validierungsskript (Vergleich GCP-Soll vs. WebODM-Ist nach Run)
- [ ] Multi-Site-Batch-Mode (alle Sites im `fieldwork/`-Tree sequenziell)
- [ ] CI mit `shellcheck` auf GitLab CI / GitHub Actions
- [ ] Unit-Tests für CRS-Validation-Funktion

## Referenzen

- Find-GCP: https://github.com/zsiki/Find-GCP
- WebODM Docs: https://docs.webodm.org
- WebODM Decoupling-Announcement (04/2026): https://webodm.org/blog/announcement
- ODX Engine: https://github.com/WebODM/ODX
- ArUco-Detektor-Parameter: https://docs.opencv.org/trunk/d5/dae/tutorial_aruco_detection.html
- GeoForAll Lab Paper (Sikí 2021, Baltic Journal of Modern Computing): https://www.bjmc.lu.lv/fileadmin/user_upload/lu_portal/projekti/bjmc/Contents/9_1_06_Siki.pdf
