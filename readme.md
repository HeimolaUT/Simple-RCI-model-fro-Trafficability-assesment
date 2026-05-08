# Simple RCI-Based Terrain Trafficability Model

A pixel-level terrain trafficability assessment model combining freely available global remote sensing and soil datasets with empirical soil strength equations. The model produces GO / SLOW-GO / NO-GO rasters for a given vehicle.

> **Note:** This model is developed for scientific and educational purposes as part of a spatial analysis course at the University of Tartu (Geography MSc, 2026).

---

## Study Area

The model was tested over the Andorra / southern France / northern Spain region. This area was chosen for data availability and the absence of snow cover (excluding mountain) during the analysis date (13 January 2026).

---

## Model Overview

The pipeline consists of two parts:

1. **RCI model**: computes a pixel-level Rating Cone Index (RCI) raster in kPa from soil and terrain inputs
2. **VCI comparison**: computes vehicle-specific Vehicle Cone Index (VCI) thresholds and classifies each pixel as GO, SLOW-GO, or NO-GO

### Pipeline

```
NISAR soil moisture (h5)
        ↓ nisarConvert
Soil moisture GeoTIFF (200m, EPSG:4326)   ← reference grid for all alignment
        ↓
Ancillary inputs (all reprojected to EPSG:4326 and resampled to NISAR grid):
  - SoilGrids clay and sand content (g/kg, 15–30 cm)
  - EU-SoilHydroGrids saturated water content θs (15 cm, 30 cm)
  - EU-DEM (clipped and reprojected)
  - ISMN precipitation point data → IDW raster
  - CORINE land cover 2018 (clipped, reprojected)
        ↓
RCI model (pixel-level, kPa)
        ↓
CORINE open terrain mask
        ↓
RCI raster → compare with VCI thresholds (HMMWV M1152)
        ↓
GO / SLOW-GO / NO-GO classification rasters (VCI1 and VCI50)
```

---

## Input Datasets

| Dataset | Source | Description |
|---------|--------|-------------|
| Soil moisture | NISAR Level 3 | Volumetric soil moisture ~200 m resolution |
| Precipitation | ISMN network | Point measurements → IDW interpolated raster |
| Clay and sand | SoilGrids 15–30 cm | Soil texture fractions (g/kg) |
| Saturated water content (θs) | EU-SoilHydroGrids v1.0 | At 15 cm and 30 cm depth |
| DEM | EU-DEM (Copernicus) | Elevation, used to derive slope |
| Land cover | CORINE 2018 | Used to mask non-trafficable terrain |

All inputs are reprojected to EPSG:4326 and aligned to the NISAR soil moisture raster pixel grid.

---

## RCI Model

RCI is computed per pixel using a linear interpolation between dry and saturated soil strength, modulated by effective saturation, slope and rainfall:

```
Se  = clip(θ / θs, 0, 1)
RCI = RCI_dry × (1 − Se) + RCI_sat × Se
RCI = RCI − 8.0 × slope_degrees
RCI = RCI − 1.2 × clip(rainfall_mm, 0, 100)
RCI = clip(RCI, 0, 700)  [kPa]
```

### Soil Texture Classification

Each pixel is classified into one of three texture classes from SoilGrids sand and clay fractions:

| Class | Condition | RCI dry (kPa) | RCI saturated (kPa) |
|-------|-----------|--------------|-------------------|
| Sandy | sand > 70% | 600 | 200 |
| Other | default | 500 | 100 |
| Clayey | clay > 35% | 400 | 40 |

### θs Layer

θs is built from EU-SoilHydroGrids at 15 cm and 30 cm (averaged). Pixels outside the valid range (0.20–0.75) fall back to texture-class defaults: 0.43 (sandy), 0.46 (loamy), 0.51 (clayey).

### CORINE Land Cover Mask

Only open terrain classes are retained. Urban areas, forests, and water bodies are excluded. Open classes include agricultural land (211–244), natural grasslands and heathlands (321–324), sparse and bare terrain (331–334), and wetlands (411–412).

---

## VCI Calculation: HMMWV M1152A1

Vehicle Cone Index thresholds are computed from the J.D. Priddy and T. Ciobotaru formulas.

### Vehicle Specifications

| Parameter | Value | Source |
|-----------|-------|--------|
| GVW | 6,101 kg (13,450 lb) | AM General M1152 datasheet |
| Tire | 37×12.50R16.5 | Military tire guide |
| Tire width | 12.50 in | Military tire guide |
| Tire diameter | 37.0 in | Military tire guide |
| Rim diameter | 16.5 in | Military tire guide |
| Ground clearance | 17.4 in (441 mm) | AM General M1152 datasheet |
| Engine | 190 hp | AM General M1152 datasheet |
| Transmission | Automatic | AM General M1152 datasheet |

### Mobility Index Formula

From Priddy & Willoughby (2006) and Ciobotaru (2009):

```
MI = ((CPF × WF) / (TEF × GF) + WLF − CF) × EF × TF

CPF = w / (0.5 × n × d × b)          contact pressure factor [psi]
TEF = (10 + b) / 100                  traction element factor
WLF = w / 2000                        wheel load factor [short tons]
CF  = hc / 10                         clearance factor
GF  = 1 + 0.05 × c_GF                grouser factor (c_GF = 1 if chains)
EF  = 1 + 0.05 × c_EF                engine factor (c_EF = 1 if PWR < 10 hp/ton)
TF  = 1 + 0.05 × c_TF                transmission factor (c_TF = 1 if manual)
WF  = c_WF1 × (w/1000) + c_WF2      weight factor (piecewise linear)
```

Where `w` = weight per axle [lbf], `n` = tires per axle, `d` = tire diameter [in], `b` = tire width [in], `hc` = ground clearance [in].

All MI inputs are in US customary units (lbf, inches). Output MI is in psi.

### VCI Formulas

**VCI1** (minimum RCI for 1 pass) Priddy & Willoughby (2006):

```
DCF = (0.15 / (δ/h))^0.25

MI ≤ 115:  VCI1 = (11.48 + 0.2×MI − 39.2/(MI + 3.74)) × DCF
MI > 115:  VCI1 = 4.1 × MI^0.446 × DCF
```

Where `δ` = hard-surface tire deflection [in] (assumed 15% of section height h), `h` = tire section height [in] = (diameter − rim diameter) / 2.

**VCI50** (minimum RCI for 50 passes) Ciobotaru (2009), with DCF correction applied by analogy with Priddy & Willoughby VCI1 structure:

```
MI ≤ 115:  VCI50 = (28.23 + 0.43×MI − 92.67/(MI + 3.74)) × DCF
MI > 115:  VCI50 = 9.0 × MI^0.446 × DCF
```


All VCI values are computed in psi and converted to kPa for comparison with the RCI raster.

### Results (13 January 2026, Andorra / S. France / N. Spain)

| Threshold | Value | GO | SLOW-GO | NO-GO |
|-----------|-------|-----|---------|-------|
| VCI1 | 191.6 kPa | 45.6% | 27.1% | 27.3% |
| VCI50 | 435.8 kPa | 0.2% | 0.5% | 99.3% |

During the analysis date the region was nearly precipitation-free, so results are driven primarily by soil texture and moisture.

---

## Terrain Classification

Each pixel is classified based on its RCI relative to the VCI threshold with a ±20 kPa slow-go margin:

| Class | Condition | Value |
|-------|-----------|-------|
| NO-GO | RCI < VCI − 20 kPa | 0 |
| SLOW-GO | VCI − 20 kPa ≤ RCI < VCI + 20 kPa | 1 |
| GO | RCI ≥ VCI + 20 kPa | 2 |

---

## Repository Structure

```
├── RA_project.ipynb          main notebook: data processing and model
├── nisarConvert.py           NISAR h5: GeoTIFF conversion utility
└── README.md
```

---

## Dependencies

```
numpy
os
rasterio
contextly
pandas
geopandas
pathlib
datetime
rasterstats
scipy
rioxarray
matplotlib
h5py

```

---

## Limitations

- NISAR Level 3 soil moisture data used in this model is uncalibrated. This could have been validated with ISMN soil moisture data, but it is out of the scope of this work
- The slope penalty (8 kPa/degree) and rainfall softening (1.2 kPa/mm) coefficients are empirical assumptions not calibrated for this specific study area.
- The tire deflection parameter `δ` is assumed at 15% of section height. Actual values depend on inflation pressure from tire datasheets.
- No ground-truth RCI measurements were available for validation. Results are spatially plausible but not validated.
- VCI50 formula source (Ciobotaru 2009) contains differences relative to the J.D. Priddy formulas.

---

## References

Pundir, S.K., Grag, R.D. (2020). Development of rule based approach for assessment of off-road trafficability using remote sensing and ancillary data. *Quaternary International*, 575–576, 308–316. https://doi.org/10.1016/j.quaint.2020.07.017

Priddy, J.D., Willoughby, W.E. (2006). Clarification of vehicle cone index with reference to mean maximum pressure. *Journal of Terramechanics*, 43, 85–96. https://doi.org/10.1016/j.jterra.2004.10.001

Ciobotaru, T. (2009). Semi-Empiric Algorithm for Assessment of the Vehicle Mobility. *Leonardo Electronic Journal of Practices and Technologies*, 8. (CC BY 4.0, no DOI)

Wang, R., Wan, S., Chen, W., Qin, X., Zhang, G., Wang, L. (2024). A novel finer soil strength mapping framework based on machine learning and remote sensing images. *Computers & Geosciences*, 182, 105479. https://doi.org/10.1016/j.cageo.2023.105479

Military Tire Guides. (2026). https://aaa1surplus.com/guides.html (accessed 04.05.2026)

AM General. (2018). *M1100 Series HMMWV M1152*. https://amgeneral.com/wp-content/uploads/2019/12/M1152.pdf

Open Topo Data. EU-DEM.  https://www.opentopodata.org/datasets/eudem/ 
 
EU-SoilHydroFrids ver 1.0. https://eusoilhydrogrids.rissac.hu/250.php

SoilGrids. https://soilgrids.org/

CORINE Land Cover 2018 (vector/raster 100 m), Europe, 6-yearly. https://land.copernicus.eu/en/products/corine-land-cover/clc2018

International Soil Moisture Network. https://ismn.earth/en/
