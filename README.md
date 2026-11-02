# Dolores River & McPhee

An unofficial, live dashboard for the Dolores River basin in southwest Colorado: snowpack, headwater gauges, McPhee Reservoir storage and spill odds, irrigation diversions, and the lower river from Slick Rock to Cisco.

## How it works

- `index.html` is the whole app. When someone opens it, their browser pulls current readings straight from public government feeds: USGS, NOAA's National Water Prediction Service, Colorado DWR, and NRCS SNOTEL. No server or API keys.
- `snapshot.json` is a backup copy of the same data. The page uses it only if the live feeds can't be reached.
- `.github/workflows/refresh-snapshot.yml` rebuilds the snapshot every 3 hours using `tools/build_snapshot.py`.

## Data caveats

River and reservoir readings are provisional. The spill estimate is a rough personal model, not a forecast from DWCD or Reclamation. For flood safety, follow the National Weather Service in Grand Junction.
