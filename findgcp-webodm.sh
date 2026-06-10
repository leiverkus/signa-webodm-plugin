#!/usr/bin/env bash
#
# findgcp-webodm.sh
# -----------------
# Automatisiert den Find-GCP → WebODM Workflow für archäologische
# Drohnenbefliegungen mit ArUco-Markern.
#
# Pipeline:
#   1. ArUco-Marker in Bildern detektieren (Find-GCP / gcp_find.py)
#   2. Statistik & Sanity-Check (welche GCPs auf wie vielen Bildern?)
#   3. Optionale visuelle Prüfung via gcp_check.py
#   4. Aufbereitung einer WebODM-bereiten Ordnerstruktur
#   5. Optionaler Upload via WebODM-API (NodeODX-Endpoint)
#
# Autor: für Patricks Solearis/TRACE-Workflow (Levante-Kontext)
# Lizenz: MIT

set -euo pipefail
IFS=$'\n\t'

# ---------- Defaults ----------
FINDGCP_DIR="${FINDGCP_DIR:-$HOME/src/Find-GCP}"
EPSG="28191"               # Palestine 1923 / Palestine Belt - dein Solearis-CRS
ARUCO_DICT="1"             # 1 = DICT_4X4_100, 99 = custom 3x3
MINRATE="0.01"             # rel. Mindestgröße der Marker
IGNORE="0.33"              # Burnt-in-Schutz für starkes Sonnenlicht
ADJUST="--adjust"          # Color-LUT gegen Überbelichtung (leer setzen zum Deaktivieren)
IMAGE_PATTERN="*.JPG"
DO_CHECK="false"
DO_PREP="false"
DO_UPLOAD="false"
WEBODM_URL=""
WEBODM_USER=""
WEBODM_PASS=""
PROJECT_NAME=""

# ---------- Hilfsfunktionen ----------
log()  { printf "\033[1;34m[%s]\033[0m %s\n" "$(date +%H:%M:%S)" "$*"; }
warn() { printf "\033[1;33m[WARN]\033[0m %s\n" "$*" >&2; }
err()  { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*" >&2; exit 1; }

usage() {
  cat <<EOF
findgcp-webodm.sh - Find-GCP → WebODM Workflow

USAGE:
  $0 -i <image_dir> -c <gcp_coords.txt> -o <output_dir> [OPTIONS]

REQUIRED:
  -i, --images DIR        Verzeichnis mit Drohnenbildern
  -c, --coords FILE       GCP-Koordinatendatei (id easting northing elevation)
  -o, --output DIR        Output-Verzeichnis für gcp_list.txt + Reports

OPTIONAL:
  -e, --epsg CODE         EPSG-Code der GCP-Koordinaten (default: $EPSG)
  -d, --dict ID           ArUco-Dictionary-ID (default: $ARUCO_DICT, 99 für 3x3 custom)
  -p, --pattern GLOB      Bilddatei-Glob (default: $IMAGE_PATTERN)
  --minrate VAL           min. relative Markergröße (default: $MINRATE)
  --ignore VAL            Pixel-Ignore-Rate für Burnt-in (default: $IGNORE)
  --no-adjust             Color-Adjustment deaktivieren
  --findgcp-dir DIR       Pfad zur Find-GCP-Installation (default: $FINDGCP_DIR)

WORKFLOW-OPTIONEN:
  --check                 nach der Detektion gcp_check.py GUI starten
  --prep                  WebODM-bereite Ordnerstruktur erzeugen
  --upload                via NodeODX-API zu WebODM-Server hochladen
  --webodm-url URL        z.B. http://webodm.example.org:8000
  --webodm-user USER      WebODM-Benutzername
  --webodm-pass PASS      WebODM-Passwort (oder via WEBODM_PASS env)
  --project NAME          Projektname in WebODM

  -h, --help              diese Hilfe

BEISPIELE:

  # Einfacher Run mit deinem Levante-Default (EPSG:28191, 4x4-Marker):
  $0 -i ~/fieldwork/zira2025/raw -c gcps.txt -o ~/fieldwork/zira2025/processed

  # 3x3 Custom-Marker, kleinere Mindestgröße:
  $0 -i ./bilder -c gcps.txt -o ./out -d 99 --minrate 0.01

  # ITM (israelisches Standard-CRS) statt Palestine Belt:
  $0 -i ./bilder -c gcps.txt -o ./out -e 2039

  # Mit visuellem Check:
  $0 -i ./bilder -c gcps.txt -o ./out --check

  # Komplette Pipeline inkl. Upload:
  $0 -i ./bilder -c gcps.txt -o ./out --prep --upload \\
     --webodm-url http://192.168.1.10:8000 --webodm-user patrick \\
     --project "TallZiraa-Area3-2026"

EOF
  exit 0
}

# ---------- Argument Parsing ----------
IMAGES=""
COORDS=""
OUTPUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -i|--images)        IMAGES="$2"; shift 2 ;;
    -c|--coords)        COORDS="$2"; shift 2 ;;
    -o|--output)        OUTPUT="$2"; shift 2 ;;
    -e|--epsg)          EPSG="$2"; shift 2 ;;
    -d|--dict)          ARUCO_DICT="$2"; shift 2 ;;
    -p|--pattern)       IMAGE_PATTERN="$2"; shift 2 ;;
    --minrate)          MINRATE="$2"; shift 2 ;;
    --ignore)           IGNORE="$2"; shift 2 ;;
    --no-adjust)        ADJUST=""; shift ;;
    --findgcp-dir)      FINDGCP_DIR="$2"; shift 2 ;;
    --check)            DO_CHECK="true"; shift ;;
    --prep)             DO_PREP="true"; shift ;;
    --upload)           DO_UPLOAD="true"; shift ;;
    --webodm-url)       WEBODM_URL="$2"; shift 2 ;;
    --webodm-user)      WEBODM_USER="$2"; shift 2 ;;
    --webodm-pass)      WEBODM_PASS="$2"; shift 2 ;;
    --project)          PROJECT_NAME="$2"; shift 2 ;;
    -h|--help)          usage ;;
    *)                  err "Unbekanntes Argument: $1 (siehe -h)" ;;
  esac
done

# ---------- Validierung ----------
[[ -z "$IMAGES" ]] && err "Fehlend: -i / --images"
[[ -z "$COORDS" ]] && err "Fehlend: -c / --coords"
[[ -z "$OUTPUT" ]] && err "Fehlend: -o / --output"
[[ ! -d "$IMAGES" ]] && err "Bilderverzeichnis existiert nicht: $IMAGES"
[[ ! -f "$COORDS" ]] && err "Koordinatendatei existiert nicht: $COORDS"

GCP_FIND="$FINDGCP_DIR/gcp_find.py"
GCP_CHECK="$FINDGCP_DIR/gcp_check.py"
[[ ! -f "$GCP_FIND" ]] && err "gcp_find.py nicht gefunden in $FINDGCP_DIR (setze --findgcp-dir oder FINDGCP_DIR)"

# Python-Dependencies prüfen
python3 -c "import cv2" 2>/dev/null || err "OpenCV (cv2) fehlt. Installiere mit: pip install opencv-python opencv-contrib-python"
python3 -c "import cv2.aruco" 2>/dev/null || err "OpenCV-Contrib fehlt. Installiere: pip install opencv-contrib-python"

mkdir -p "$OUTPUT"
GCP_LIST="$OUTPUT/gcp_list.txt"
LOG_FILE="$OUTPUT/findgcp_$(date +%Y%m%d_%H%M%S).log"
REPORT_FILE="$OUTPUT/gcp_report.txt"

# ---------- 1. GCP-Detektion ----------
log "=== Find-GCP Detection ==="
log "Bilder:    $IMAGES ($IMAGE_PATTERN)"
log "Koords:    $COORDS"
log "EPSG:      $EPSG"
log "Dict:      $ARUCO_DICT (1=4x4_100, 99=custom 3x3)"
log "Minrate:   $MINRATE"
log "Ignore:    $IGNORE"
log "Output:    $GCP_LIST"

# Bilder zählen
shopt -s nullglob nocaseglob
IMG_FILES=("$IMAGES"/$IMAGE_PATTERN)
shopt -u nullglob nocaseglob
IMG_COUNT=${#IMG_FILES[@]}
[[ $IMG_COUNT -eq 0 ]] && err "Keine Bilder gefunden mit Pattern '$IMAGE_PATTERN' in $IMAGES"
log "Gefunden: $IMG_COUNT Bilder"

# Find-GCP ausführen
log "Starte Marker-Detektion ..."
python3 "$GCP_FIND" \
  -v \
  -t ODM \
  -i "$COORDS" \
  --epsg "$EPSG" \
  -o "$GCP_LIST" \
  --minrate "$MINRATE" \
  --ignore "$IGNORE" \
  -d "$ARUCO_DICT" \
  $ADJUST \
  "${IMG_FILES[@]}" 2>&1 | tee "$LOG_FILE"

[[ ! -s "$GCP_LIST" ]] && err "gcp_list.txt ist leer - keine Marker erkannt. Prüfe --minrate, --dict und Bildqualität."

# ---------- 2. Report ----------
log "=== Sanity-Check / Report ==="
{
  echo "Find-GCP Report - $(date -Iseconds)"
  echo "==========================================="
  echo "Bilderverzeichnis: $IMAGES"
  echo "Bilder gesamt:     $IMG_COUNT"
  echo "EPSG:              $EPSG"
  echo "ArUco-Dict:        $ARUCO_DICT"
  echo
  echo "GCP-Eintraege (ohne Header): $(($(wc -l < "$GCP_LIST") - 1))"
  echo
  echo "GCPs pro Marker-ID:"
  echo "-------------------"
  # Spalte 7 = marker id (nach EPSG-Header)
  tail -n +2 "$GCP_LIST" | awk '{print $NF}' | sort | uniq -c | sort -rn
  echo
  echo "GCPs pro Bild (Top 20):"
  echo "-----------------------"
  tail -n +2 "$GCP_LIST" | awk '{print $6}' | sort | uniq -c | sort -rn | head -20
  echo
  echo "Bilder ohne GCP:"
  echo "----------------"
  comm -23 \
    <(printf '%s\n' "${IMG_FILES[@]##*/}" | sort -u) \
    <(tail -n +2 "$GCP_LIST" | awk '{print $6}' | sort -u) \
    | head -20
  echo
  echo "QUALITAETS-CHECKS:"
  echo "------------------"
  UNIQUE_MARKERS=$(tail -n +2 "$GCP_LIST" | awk '{print $NF}' | sort -u | wc -l)
  echo "  Eindeutige Marker erkannt: $UNIQUE_MARKERS"
  if [[ $UNIQUE_MARKERS -lt 5 ]]; then
    echo "  ⚠  WARNUNG: <5 Marker. Fuer robuste Buendelblockausgleichung sind 5-10+ empfohlen."
  fi
  # Prüfe ob Marker auf <3 Bildern
  WEAK=$(tail -n +2 "$GCP_LIST" | awk '{print $NF}' | sort | uniq -c | awk '$1 < 3 {print $2}' | tr '\n' ' ')
  if [[ -n "$WEAK" ]]; then
    echo "  ⚠  Marker auf <3 Bildern (sollten min. 3, besser 5+ sein): $WEAK"
  fi
} | tee "$REPORT_FILE"

log "Report gespeichert: $REPORT_FILE"
log "GCP-Liste:          $GCP_LIST"

# ---------- 3. Optional: GUI-Check ----------
if [[ "$DO_CHECK" == "true" ]]; then
  log "=== Visueller Check (gcp_check.py) ==="
  [[ ! -f "$GCP_CHECK" ]] && warn "gcp_check.py nicht gefunden, ueberspringe" || \
    python3 "$GCP_CHECK" --path "$IMAGES" "$GCP_LIST"
fi

# ---------- 4. Optional: WebODM-Prep ----------
if [[ "$DO_PREP" == "true" ]]; then
  log "=== WebODM-Ordnerstruktur erzeugen ==="
  PREP_DIR="$OUTPUT/webodm_ready"
  mkdir -p "$PREP_DIR/images"

  # Symlinks statt Copy - spart Platz bei grossen Datasets
  log "Erstelle Symlinks zu Bildern in $PREP_DIR/images ..."
  for img in "${IMG_FILES[@]}"; do
    ln -sf "$(realpath "$img")" "$PREP_DIR/images/$(basename "$img")"
  done

  cp "$GCP_LIST" "$PREP_DIR/gcp_list.txt"

  # README mit den Task-Optionen, die du in WebODM setzen solltest
  cat > "$PREP_DIR/README_webodm.md" <<MDEOF
# WebODM Task-Setup

Datensatz: $(basename "$OUTPUT")
Erstellt:  $(date -Iseconds)
Bilder:    $IMG_COUNT
EPSG:      $EPSG

## Upload nach WebODM

1. Neue Task in WebODM anlegen
2. Alle Dateien aus \`images/\` hochladen
3. \`gcp_list.txt\` über den GCP-Upload-Button hinzufügen
4. Empfohlene Task-Optionen (Levante-Befliegung, archäologisches Ortho/DEM):

\`\`\`
feature-quality: high
pc-quality: high
matcher-neighbors: 16
mesh-octree-depth: 11
dem-resolution: 2.0
orthophoto-resolution: 1.5
crop: 3
optimize-disk-space: true
use-3dmesh: false              # auf true wenn 3D-Modell gewuenscht
\`\`\`

Bei Speicherproblemen (>500 Bilder, <16GB RAM):
\`\`\`
split: 200
split-overlap: 50
feature-quality: medium
pc-quality: medium
\`\`\`
MDEOF

  log "WebODM-Setup bereit: $PREP_DIR"
fi

# ---------- 5. Optional: Upload ----------
if [[ "$DO_UPLOAD" == "true" ]]; then
  log "=== Upload zu WebODM via API ==="
  [[ -z "$WEBODM_URL" ]]  && err "--webodm-url fehlt"
  [[ -z "$WEBODM_USER" ]] && err "--webodm-user fehlt"
  [[ -z "$WEBODM_PASS" ]] && err "--webodm-pass oder env WEBODM_PASS fehlt"
  [[ -z "$PROJECT_NAME" ]] && PROJECT_NAME="findgcp-$(date +%Y%m%d-%H%M)"

  command -v jq >/dev/null || err "jq fehlt (apt install jq / brew install jq)"

  # Token holen
  log "Auth gegen $WEBODM_URL ..."
  TOKEN=$(curl -sf -X POST "$WEBODM_URL/api/token-auth/" \
    -d "username=$WEBODM_USER&password=$WEBODM_PASS" | jq -r .token)
  [[ -z "$TOKEN" || "$TOKEN" == "null" ]] && err "Auth fehlgeschlagen"
  log "Token erhalten"

  # Projekt anlegen
  log "Lege Projekt '$PROJECT_NAME' an ..."
  PROJECT_ID=$(curl -sf -X POST "$WEBODM_URL/api/projects/" \
    -H "Authorization: JWT $TOKEN" \
    -d "name=$PROJECT_NAME" | jq -r .id)
  [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "null" ]] && err "Projekt-Anlage fehlgeschlagen"
  log "Projekt-ID: $PROJECT_ID"

  # Task mit Bildern + GCP-Liste
  log "Erstelle Task & lade Bilder hoch (kann dauern) ..."
  CURL_FILES=()
  for img in "${IMG_FILES[@]}"; do
    CURL_FILES+=(-F "images=@$img")
  done
  CURL_FILES+=(-F "images=@$GCP_LIST;filename=gcp_list.txt")

  TASK_ID=$(curl -sf -X POST "$WEBODM_URL/api/projects/$PROJECT_ID/tasks/" \
    -H "Authorization: JWT $TOKEN" \
    "${CURL_FILES[@]}" | jq -r .id)

  [[ -z "$TASK_ID" || "$TASK_ID" == "null" ]] && err "Task-Anlage fehlgeschlagen"
  log "Task-ID: $TASK_ID"
  log "→ $WEBODM_URL/dashboard/?project_task_open=$TASK_ID"
fi

log "=== Fertig ==="
