# Dolores River & McPhee

An unofficial, live dashboard for the Dolores River basin in southwest Colorado: snowpack, headwater gauges, McPhee Reservoir storage and spill odds, irrigation diversions, and the lower river from Slick Rock to Cisco.

Live at **https://matthewsclark.github.io/Dolores/**

## How it works

- `index.html` is the whole app. When someone opens it, their browser pulls current readings straight from public government feeds (USGS, NOAA's National Water Prediction Service, Colorado DWR, NRCS SNOTEL). There's no server and no API key.
- `snapshot.json` is a saved copy of the same data, rebuilt every 3 hours by `.github/workflows/refresh-snapshot.yml` running `tools/build_snapshot.py`. The page uses it when the live feeds can't be reached, and for the water-year peak at Dolores, which needs more history than the page fetches.
- `og.png` is the preview image for shared links.

## Data sources

| What | Source |
|---|---|
| River flows, water levels, peak record | USGS: 09165000 Rico, 09166500 Dolores, 09166950 Lost Canyon, 09168730 Slick Rock, 09171100 Bedrock, 09179450 Gateway, 09180000 Cisco |
| Flood categories, 7-day forecasts, Lost Canyon rating | NOAA NWPS |
| McPhee storage and elevation, dam release, canals | Colorado DWR: MCPRESCO, DOLBMCCO, DOLTUNCO, DOVCANCO, MVIDIVCO, UCANALCO, TOWCANCO |
| Snow | NRCS: Black Mesa, Sharkstooth, El Diente Peak, Lizard Head Pass, Lone Cone, Scotch Creek SNOTEL; Groundhog snow course |
| History: normal storage, spill record | Reclamation RISE, McPhee daily storage, inflow and release, 1984–present |
| Capacity, pools, average inflow | DWCD FAQ |

## The numbers baked into the page

Some reference data is fixed in `index.html` because it changes at most once a year:

- **Storage terms.** Total capacity 381,000 af at 6,924 ft; inactive pool 152,000 af; usable (active) capacity 229,000 af (DWCD).
- **Normal storage.** Median total storage for each day of the year, 1991–2020, from Reclamation's daily record.
- **Peak record.** The ten largest annual peaks at Dolores, from the USGS annual peak file (1896–2025).
- **Spill history and model.** For every spring from 1988 to 2026: April 1 storage, April–July inflow, the volume released above 150 cfs, and days with releases of 800 cfs or more. A hinge fit to those 39 springs gives:

  > spill ≈ 0.92 × max(0, April 1 storage + April–July inflow − 486,000 af)

  Its typical miss is about 11,000 af. Each day above 800 cfs takes about 3,500 af of spill. The April–July average used for the slider is the 1991–2020 mean, 255,000 af.
- **Winter, Nov 10 to Apr 1.** April 1 storage = projected storage after the current forecast + winter inflow − dam release − canal diversions − evaporation. Winter inflow comes from the 1988–2026 record: 12,200 af in a dry winter (10th percentile), 27,300 typical, 59,700 wet (90th). Release (default 15 cfs) and diversions (default 9,500 af, the median of the last 14 winters) are editable on the page. They aren't taken from history because big winter releases, 40–65 cfs, only happen after full years. Last winter, DWR recorded 4,700 af released and 19,300 af diverted, almost all of it through MVIC's Lone Pine Canal in February and March.

## Caveats

River and reservoir readings are provisional and can be revised. The Lost Canyon flow is an estimate from water level, using NOAA's rating, because USGS isn't publishing flow for that gauge. The spill estimate is a rough model from history, not a forecast from DWCD or Reclamation. For flood safety, follow the National Weather Service in Grand Junction; for release schedules, follow DWCD.

To refresh the history (once a year, after July): download Reclamation RISE items 569 (storage), 570 (inflow) and 4342 (release) for McPhee and recompute `HIST` and `NORM`.
