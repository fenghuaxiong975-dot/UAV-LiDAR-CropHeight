# UAV-LiDAR-CropHeight

A lightweight research codebase for **plot-level crop height extraction from low-altitude/UAV LiDAR point clouds**. The repository contains a Python batch pipeline and the source of a legacy C# WinForms desktop front end.

> **Publication status:** the code has been cleaned for repository use, but the open-source license is intentionally left pending. Keep the repository **Private** until the authorized rights holder confirms a license and any patent/public-disclosure constraints.

## 1. Pipeline

The Python program keeps the calculation workflow of the supplied research script:

```text
LAS/LAZ
  -> clip points by plot Shapefile
  -> split classification 2 (ground) / 1 (non-ground or vegetation, project convention)
  -> grid DEM P05 and DSM P99
  -> CHM = DSM - DEM
  -> plot CHM P100 / P99.5 / P99
  -> summary CSV
```

Default parameters:

- grid cell: `0.10 m`
- DTM/DEM percentile: `5`
- DSM percentile: `99`
- plot border shrink ratio: `0.20`
- reported CHM percentiles: `P100`, `P99.5`, `P99`
- output height unit: centimetres

The optional seven-digit filename decoder from the original project is retained. If a filename does not match that convention, its `Model/H/V/O/A` metadata fields remain empty and height calculation still proceeds.

## 2. Repository structure

```text
UAV-LiDAR-CropHeight/
├── python/
│   └── crop_height.py
├── desktop-app/
│   └── WindowsFormsApp1/
├── sample_data/
│   ├── las/.gitkeep
│   └── shp/.gitkeep
├── sample_output/.gitkeep
├── tests/
│   ├── test_crop_height.py
│   └── test_desktop_source.py
├── requirements.txt
├── environment.yml
├── .gitignore
├── LICENSE
└── README.md
```

Large/raw research data are intentionally excluded from Git.

## 3. Prepare test data

The repository ships with empty placeholders only. Put your own local data in the directories below, or pass absolute paths on the command line.

```text
sample_data/
├── las/
│   └── your_example.las
└── shp/
    ├── plots.shp
    ├── plots.shx
    ├── plots.dbf
    └── plots.prj
```

A Shapefile is a multi-file dataset: keep the matching `.shp`, `.shx`, `.dbf`, and preferably `.prj` together. The plot identifier field defaults to `Id`; change it with `--id-field` if your file uses another field name.

## 4. Python environment

### Conda

```bash
conda env create -f environment.yml
conda activate uav-lidar-cropheight
```

### pip

```bash
python -m pip install -r requirements.txt
```

`lazrs` is included so `laspy` can read/write LAZ where supported.

## 5. Run the Python pipeline

Process a directory:

```bash
python python/crop_height.py \
  --input ./sample_data/las \
  --shp ./sample_data/shp/plots.shp \
  --output ./sample_output/plot_heights.csv \
  --id-field Id
```

A single `.las`/`.laz` file is also accepted, which is useful for the desktop GUI:

```bash
python python/crop_height.py \
  --input ./sample_data/las/your_example.las \
  --shp ./sample_data/shp/plots.shp \
  --output ./sample_output/plot_heights.csv
```

See every option with:

```bash
python python/crop_height.py --help
```

Important options:

```text
--input PATH          LAS/LAZ file or directory
--shp PATH            plot Shapefile
--output PATH         output CSV
--id-field NAME       plot ID field (default: Id)
--cell FLOAT          grid size in m (default: 0.10)
--dtm-pct FLOAT       ground percentile (default: 5)
--dsm-pct FLOAT       canopy percentile (default: 99)
--border-ratio FLOAT  plot shrink ratio (default: 0.20)
--recursive           recursively find LAS/LAZ in a directory
```

During processing, plot-level files are written into a local `region/` directory next to the input LAS/LAZ file, with class-split files under `region/classification/`. These generated files are ignored by Git.

## 6. Output CSV

Each row represents one input point-cloud file × one plot. Typical columns include:

- `filename`
- `region_file`
- `plot_id`
- `cell_m`, `dtm_pct`, `dsm_pct`, `border_ratio`
- `H_CHM_P100_0`, `H_CHM_P99_5`, `H_CHM_P99_0` (centimetres)
- optional flight metadata: `Model`, `H`, `V`, `O`, `A`

## 7. C# WinForms desktop app

The legacy desktop source is under `desktop-app/WindowsFormsApp1/` and targets **.NET Framework 4.7.2**.

For the cleaned open-source build:

- embedded login credentials were removed;
- the application opens the main form directly;
- file dialogs start from the user's Documents folder rather than a developer-specific drive;
- the Python executable is configured by `PythonExe` in `App.config` (default: `python` from `PATH`);
- the app searches upward for `python/crop_height.py` in the cloned repository;
- standard output and standard error from Python are both displayed;
- the old two-script workflow is consolidated: **检查输入** validates the selected LAS/LAZ and SHP, while **计算株高** runs the unified Python pipeline.

To build on Windows, open `WindowsFormsApp1.sln` in Visual Studio, restore NuGet packages if prompted, and build the project. A Windows/.NET Framework build was **not executed in the current Linux preparation environment**, so no compilation-success claim is made here.

## 8. Tests and validation

Repository-level checks:

```bash
python -m py_compile python/crop_height.py
python python/crop_height.py --help
pytest -q
```

The automated tests cover CLI defaults/path validation, missing Shapefile ID handling, missing point classes, and static checks that the desktop source no longer contains the original machine-specific paths/signing-key reference.

Full scientific output validation still requires representative LAS/LAZ + Shapefile test data, which are intentionally not included in this repository.

## 9. Data and privacy

Do **not** commit raw research point clouds, Shapefiles, generated CSV results, signing certificates, local IDE caches, or machine-specific configuration. The provided `.gitignore` excludes these by default.

## 10. License

The license is currently **pending rights-holder confirmation**. Before making the GitHub repository Public, replace `LICENSE` with the approved open-source license and confirm that public disclosure does not conflict with patent, institutional, collaborative, or software-copyright obligations.
