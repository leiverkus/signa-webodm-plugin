# Find-GCP → WebODM Workflow

Automatisierter Workflow zur Bearbeitung archäologischer Drohnenbefliegungen:
ArUco-GCP-Detektion mit [Find-GCP](https://github.com/zsiki/Find-GCP),
Aufbereitung für [WebODM](https://docs.webodm.org) (Engine: ODX) und Integration
in den Solearis-Stack (PostGIS / GeoDjango / QFieldCloud). Entwickelt für
Südlevante-Sites (Israel / Jordanien / Westbank), u. a. Tall Zira'a.

Das Herzstück ist ein einziges Bash-Skript, [`findgcp-webodm.sh`](findgcp-webodm.sh),
das die folgende Pipeline kapselt:

1. **Detektion** — ArUco-Marker in den Bildern finden (`gcp_find.py`)
2. **Report** — Sanity-Check: welche GCP auf wie vielen Bildern, Warnungen
3. **Check** *(optional)* — visuelle Prüfung via `gcp_check.py`
4. **Prep** *(optional)* — WebODM-bereite Ordnerstruktur (Bilder als Symlinks)
5. **Upload** *(optional)* — direkter Task-Upload via WebODM-API

## Voraussetzungen

- **Bash** 4+
- **Python** 3.10+ mit OpenCV inkl. ArUco-Contrib:
  ```bash
  pip install opencv-python opencv-contrib-python
  ```
- **Find-GCP** lokal ausgecheckt (Default-Pfad: `~/src/Find-GCP`):
  ```bash
  git clone https://github.com/zsiki/Find-GCP ~/src/Find-GCP
  ```
- `jq` und `curl` — nur für den optionalen `--upload`-Schritt

## Schnellstart

```bash
# Einfacher Run mit Levante-Default (EPSG:28191, 4x4-Marker)
./findgcp-webodm.sh \
  -i ~/fieldwork/zira2026/raw \
  -c gcp_coords.txt \
  -o ~/fieldwork/zira2026/processed
```

Die GCP-Koordinatendatei hat das Format `id easting northing elevation` und
muss **bereits im Ziel-CRS** vorliegen — WebODM rechnet nichts um (siehe unten).

## Optionen

| Flag | Beschreibung | Default |
|------|--------------|---------|
| `-i, --images DIR` | Verzeichnis mit Drohnenbildern *(Pflicht)* | — |
| `-c, --coords FILE` | GCP-Koordinatendatei *(Pflicht)* | — |
| `-o, --output DIR` | Output-Verzeichnis *(Pflicht)* | — |
| `-e, --epsg CODE` | EPSG-Code der GCP-Koordinaten | `28191` |
| `-d, --dict ID` | ArUco-Dictionary (1 = 4x4_100, 99 = 3x3 custom) | `1` |
| `-p, --pattern GLOB` | Bilddatei-Glob | `*.JPG` |
| `--minrate VAL` | min. relative Markergröße | `0.01` |
| `--ignore VAL` | Pixel-Ignore-Rate (Burnt-in-Schutz) | `0.33` |
| `--no-adjust` | Color-Adjustment deaktivieren | aktiv |
| `--findgcp-dir DIR` | Pfad zur Find-GCP-Installation | `~/src/Find-GCP` |
| `--check` | `gcp_check.py`-GUI nach der Detektion | aus |
| `--prep` | WebODM-bereite Ordnerstruktur erzeugen | aus |
| `--upload` | via WebODM-API hochladen | aus |
| `--webodm-url / --webodm-user / --webodm-pass / --project` | Upload-Parameter | — |

Vollständige Hilfe: `./findgcp-webodm.sh --help`.

### Beispiele

```bash
# 3x3-Custom-Marker, kleinere Mindestgröße
./findgcp-webodm.sh -i ./bilder -c gcps.txt -o ./out -d 99 --minrate 0.01

# ITM (israelisches Standard-CRS) statt Palestine Belt
./findgcp-webodm.sh -i ./bilder -c gcps.txt -o ./out -e 2039

# Komplette Pipeline inkl. Upload
WEBODM_PASS=geheim ./findgcp-webodm.sh -i ./bilder -c gcps.txt -o ./out \
  --prep --upload --webodm-url http://192.168.1.10:8000 \
  --webodm-user patrick --project "TallZiraa-Area3-2026"
```

## Koordinatensysteme

GCP-Koordinaten **immer** im Ziel-CRS einmessen oder vorab transformieren — nie
WebODM die Umrechnung machen lassen. Bilder-EXIF (WGS84) und GCP-CRS dürfen
verschieden sein, ODX rechnet das EXIF intern um.

| EPSG | Name | Wann? |
|------|------|-------|
| `28191` | Palestine 1923 / Palestine Belt | Solearis-Default, Westbank, Jerusalem |
| `2039`  | Israeli Transverse Mercator (ITM) | modernes IL-Standard-CRS |
| `32636` | UTM Zone 36N | generisch Israel |
| `32637` | UTM Zone 37N | Jordanien (Tall Zira'a, Khirbet Hamra Ifdan, Amman) |
| `4326`  | WGS84 geographisch | nur als Eingabe-CRS aus EXIF-GPS |

## Output-Struktur

```
<output>/
├── gcp_list.txt              # ODM-kompatibles GCP-File (Find-GCP-Output)
├── gcp_report.txt            # Sanity-Report
├── findgcp_<timestamp>.log
└── webodm_ready/             # nur bei --prep
    ├── images/               # Symlinks (spart Platz bei 1000+ Bildern)
    ├── gcp_list.txt
    └── README_webodm.md      # empfohlene WebODM-Task-Optionen
```

## Bekannte Stolperstellen

- **Levante-Sonne**: Default `--ignore 0.33` ist auf starkes Sommerlicht
  ausgelegt; ggf. graue statt weiße Marker drucken.
- **DJI-EXIF-Höhen** sind relativ zum Take-off, nicht absolut — für den
  Bündelblock okay, aber nicht für direkte DEM-Validierung gegen GCP-Höhen.
- **`gcp_check.py` braucht X11/Display** — auf headless Servern via `ssh -X`
  oder `--check` weglassen.
- **WebODM ODX ≠ ODM**: seit 04/2026 entkoppelt; es werden die
  `webodm/odx`-Container genutzt, nicht `opendronemap/*`.

## Entwicklung

```bash
bash -n findgcp-webodm.sh   # Syntax-Check
shellcheck findgcp-webodm.sh
```

CI führt `shellcheck` automatisch aus (siehe
[`.github/workflows/shellcheck.yml`](.github/workflows/shellcheck.yml)).

## Lizenz

[MIT](LICENSE) © 2026 Patrick Leiverkus

## Referenzen

- Find-GCP: <https://github.com/zsiki/Find-GCP>
- WebODM Docs: <https://docs.webodm.org>
- ArUco-Detektor-Parameter: <https://docs.opencv.org/trunk/d5/dae/tutorial_aruco_detection.html>
- Siki 2021, *Baltic Journal of Modern Computing*:
  <https://www.bjmc.lu.lv/fileadmin/user_upload/lu_portal/projekti/bjmc/Contents/9_1_06_Siki.pdf>
