# ML Modul (Sign-to-Text)

Dieses Modul enthaelt:
- Sequenzmodell: `sign2text/model.py`
- Predictor-API: `sign2text/inference.py`
- Datensatz-Loader: `sign2text/dataset.py`
- Keypoint-Extraktion: `extract_keypoints.py`
- Training: `train.py`

## Schritt 1: Keypoints aus Rohvideos extrahieren

Erwartete Rohdaten-Struktur:

```text
ml/data/raw/
  hallo/
    clip_001.mp4
    clip_002.mp4
  danke/
    clip_001.mp4
```

Extraktion:

```bash
cd ml
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-extract.txt
python extract_keypoints.py --input-dir data/raw --output-dir data/keypoints --frame-step 2
```

Ergebnis:
- `.npy` Sequenzen unter `data/keypoints/<label>/`
- `data/keypoints/manifest.json` mit Status pro Video

## Datenformat fuer Training

Verzeichnisstruktur:

```text
ml/data/keypoints/
  hallo/
    sample_001.npy
    sample_002.npy
  danke/
    sample_001.npy
```

Jede `.npy` Datei ist ein `float32` Array mit Shape `[T, F]`:
- `T`: Anzahl Frames
- `F`: Feature-Dimension (z. B. 225)

## Training

```bash
cd ml
pip install -r requirements-train.txt
python train.py --data-dir data/keypoints --output artifacts/sign_model.pt
```

Ergebnis:
- Modell: `artifacts/sign_model.pt`
- Metriken: `artifacts/sign_model.metrics.json`

## Inference Provider

- `stub`: Demo-Ausgaben ohne trainiertes Modell
- `trained`: laedt Checkpoint mit Label-Mapping
