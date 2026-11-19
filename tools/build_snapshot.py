"""Build snapshot.json from public APIs: USGS, NOAA NWPS, Colorado DWR, NRCS AWDB.

The page reads these feeds live in the visitor's browser. This snapshot is the
fallback when a feed is down, and the source of one slow-changing extra: the
water-year peak at Dolores, which needs more history than the page fetches.
The shape matches what the page's live loader builds.
"""
import datetime as dt
import json
import sys
import time
import urllib.request

UA = {"User-Agent": "dolores-river-dashboard (github.com/matthewsclark/Dolores)"}


def get(url, tries=3):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return json.load(r)
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))


def ms(iso):
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


now = dt.datetime.now(dt.timezone.utc)
mdy = lambda d: f"{d.month}/{d.day}/{d.year}"
season_start = mdy(now - dt.timedelta(days=124))
raw_start = mdy(now - dt.timedelta(days=3))
wy_start = dt.date(now.year if now.month >= 10 else now.year - 1, 10, 1)
snow_hourly_begin = (now - dt.timedelta(days=2)).strftime("%Y-%m-%d")

GAUGES = [  # id, name, USGS site, NWS id, reach
    ("rico", "Dolores below Rico", "09165000", "DRRC2", "upper"),
    ("westfork", "West Fork near Stoner", "09166000", None, "upper"),
    ("dolores", "Dolores at Dolores", "09166500", "DOLC2", "upper"),
    ("lostcanyon", "Lost Canyon Creek", "09166950", "LCCC2", "upper"),
    ("belowdam", "Below McPhee Dam", None, "DRMC2", "lower"),
    ("slickrock", "Slick Rock", "09168730", "SLIC2", "lower"),
    ("bedrock", "Near Bedrock", "09171100", "DBDC2", "lower"),
    ("sanmiguel", "San Miguel at Uravan", None, "SMUC2", "lower"),
    ("gateway", "Near Gateway", "09179450", "DGAC2", "lower"),
    ("cisco", "Near Cisco, UT", "09180000", "DOLU1", "lower"),
]
SNOW = [
    ("1185:CO:SNTL", "Black Mesa", 11580),
    ("1060:CO:SNTL", "Sharkstooth", 10730),
    ("465:CO:SNTL", "El Diente Peak", 10210),
    ("586:CO:SNTL", "Lizard Head Pass", 10190),
    ("589:CO:SNTL", "Lone Cone", 9730),
    ("739:CO:SNTL", "Scotch Creek", 9160),
    ("08M03:CO:SNOW", "Groundhog", 8970),
]
DWR = "https://dwr.state.co.us/Rest/GET/api/v2/telemetrystations"
AWDB = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"

out = {"generated": now.isoformat(), "mode": "snapshot", "gauges": {}, "mcphee": {}, "diversions": [], "snow": [], "extras": {}}


def usgs_iv(sites, param, period=None, start=None):
    q = f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={sites}&parameterCd={param}"
    q += f"&period={period}" if period else f"&startDT={start}"
    series = {}
    for ts in get(q)["value"]["timeSeries"]:
        sid = ts["sourceInfo"]["siteCode"][0]["value"]
        vals = [(ms(x["dateTime"]), float(x["value"])) for x in ts["values"][0]["value"] if float(x["value"]) > -999]
        series[sid] = vals
    return series


# --- USGS flows (15 days, kept hourly) and the latest 15-minute reading
flows = usgs_iv(",".join(g[2] for g in GAUGES if g[2]), "00060", period="P15D")
lc_stage = usgs_iv("09166950", "00065", period="P15D").get("09166950", [])

for gid, name, usid, lid, reach in GAUGES:
    g = {"name": name, "usgs": usid, "lid": lid, "reach": reach, "series": [], "latest": None, "forecast": [], "flood": None, "stage": None}
    vals = flows.get(usid or "", [])
    if vals:
        g["series"] = [[t, v] for t, v in vals if t % 3600000 == 0]
        g["latest"] = list(vals[-1])
    if lid:
        try:
            meta = get(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}")
            ob = meta.get("status", {}).get("observed", {})
            g["flood"], g["stage"] = ob.get("floodCategory"), ob.get("primary")
            sf = get(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow")
            fdata = (sf.get("forecast") or {}).get("data", [])
            g["forecast"] = [[ms(p["validTime"]), p["secondary"] * 1000] for p in fdata if p.get("secondary", -999) > -999]
            g["rating"] = sorted({round(p["primary"], 2): round(p["secondary"] * 1000) for p in fdata
                                  if p.get("secondary", -999) > 0 and p.get("primary", -999) > -999}.items())
            cutoff = (now - dt.timedelta(days=15)).timestamp() * 1000
            obs = [[ms(p["validTime"]), p["secondary"] * 1000] for p in (sf.get("observed") or {}).get("data", [])
                   if p.get("secondary", -999) > -999 and ms(p["validTime"]) >= cutoff]
            if not g["series"] and obs:
                g["series"] = [p for p in obs if p[0] % 3600000 == 0] or obs
                g["latest"] = obs[-1]
        except Exception as e:  # one NWS gauge failing shouldn't sink the snapshot
            print("nwps", lid, e, file=sys.stderr)
    if gid == "lostcanyon":
        g["stageSeries"] = [list(p) for p in lc_stage]
    out["gauges"][gid] = g

# --- Water-year peak at Dolores (provisional, 15-minute data since Oct 1)
wy_both = usgs_iv("09166500,09165000", "00060", start=wy_start.isoformat())
wy = wy_both.get("09166500", [])
# Hourly flow since Oct 1 at Dolores and Rico, so the page can show earlier storms than its own 15-day fetch covers
out["extras"]["upper"] = {"since": wy_start.isoformat(),
                          "dolores": [[t, v] for t, v in wy if t % 3600000 == 0],
                          "rico": [[t, v] for t, v in wy_both.get("09165000", []) if t % 3600000 == 0]}
if wy:
    t, v = max(wy, key=lambda p: p[1])
    out["extras"]["wyPeak"] = {"site": "09166500", "t": t, "cfs": v, "since": wy_start.isoformat()}

# --- McPhee: daily storage, hourly storage and elevation, release, canals
day = lambda abbrev, param, start: get(f"{DWR}/telemetrytimeseriesday/?abbrev={abbrev}&parameter={param}&startDate={start}&format=json")["ResultList"]
raw = lambda abbrev, param, start: get(f"{DWR}/telemetrytimeseriesraw/?abbrev={abbrev}&parameter={param}&startDate={start}&format=json")["ResultList"]
out["mcphee"]["storage"] = [[x["measDate"][:10], round(x["measValue"])] for x in day("MCPRESCO", "STORAGE", season_start)]
out["mcphee"]["release"] = [[x["measDate"][:10], round(x["measValue"], 1)] for x in day("DOLBMCCO", "DISCHRG", season_start)]
out["mcphee"]["raw"] = [[ms(x["measDateTime"]), x["measValue"]] for x in raw("MCPRESCO", "STORAGE", raw_start) if x["measValue"] is not None]
out["mcphee"]["elev"] = [[ms(x["measDateTime"]), x["measValue"]] for x in raw("MCPRESCO", "ELEV", raw_start) if x["measValue"] is not None]
for abbrev, label in [("MCPRESCO", "McPhee storage"), ("DOLBMCCO", "Release below dam"), ("DOLTUNCO", "Dolores Tunnel"),
                      ("DOVCANCO", "Dove Creek Canal"), ("MVIDIVCO", "Lone Pine Canal (MVIC)"), ("UCANALCO", "U Lateral (MVIC)"),
                      ("TOWCANCO", "Towaoc Canal")]:
    s = get(f"{DWR}/telemetrystation/?abbrev={abbrev}&format=json")["ResultList"][0]
    rec = {"id": abbrev, "name": label, "value": s.get("measValue"), "unit": s.get("units"), "t": s.get("measDateTime")}
    if abbrev == "MCPRESCO":
        out["mcphee"]["latest"] = rec
    elif abbrev == "DOLBMCCO":
        out["mcphee"]["releaseNow"] = rec
    else:
        out["diversions"].append(rec)

# --- Snow: daily with medians since Oct 1, plus the latest hourly reading per sensor
trips = ",".join(s[0] for s in SNOW)
daily = {s["stationTriplet"]: s for s in get(f"{AWDB}?stationTriplets={trips}&elements=WTEQ,SNWD,PREC&duration=DAILY"
                                                 f"&beginDate={wy_start}&endDate={now:%Y-%m-%d}&centralTendencyType=MEDIAN")}
hourly = {s["stationTriplet"]: s for s in get(f"{AWDB}?stationTriplets={trips}&elements=WTEQ,SNWD,PREC&duration=HOURLY"
                                                  f"&beginDate={snow_hourly_begin}&endDate={now + dt.timedelta(days=1):%Y-%m-%d}")}
for trip, name, elev in SNOW:
    rec = {"id": trip, "name": name, "elev": elev, "manual": trip.endswith("SNOW"), "hourly": {}}
    for e in daily.get(trip, {}).get("data", []):
        rec[e["stationElement"]["elementCode"]] = [[v["date"], v.get("value"), v.get("median")] for v in e["values"]]
    for e in hourly.get(trip, {}).get("data", []):
        vals = [[v["date"], v["value"]] for v in e["values"] if v.get("value") is not None]
        if vals:
            rec["hourly"][e["stationElement"]["elementCode"]] = vals[-1]
    out["snow"].append(rec)

# --- CBRFC April-July inflow forecast for McPhee (MPHC2). The site doesn't allow browsers to read it directly,
# so the page gets it from this snapshot. Daily model runs (ESP) start mid-December; official forecasts are issued monthly.
def cbrfc():
    fy = now.year + 1 if now.month >= 10 else now.year
    req = urllib.request.Request(f"https://www.cbrfc.noaa.gov/wsup/graph/esptxt.py?id=MPHC2&year={fy}&csv=1", headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        text = r.read().decode("utf-8", "replace")
    esp = official = None
    for line in text.splitlines():
        c = line.replace("</pre>", "").strip().split(",")
        if len(c) < 13 or len(c[0]) != 10 or c[0][4] != "-":
            continue
        def num(x):
            try:
                return float(x)
            except ValueError:
                return None
        e = [num(x) for x in c[1:8]]
        o = [v for v in (num(x) for x in c[8:13]) if v is not None]
        if e[3] is not None:
            esp = {"date": c[0], "q": {"10": e[1], "30": e[2], "50": e[3], "70": e[4], "90": e[5]}}
        if len(o) == 5:
            official = {"date": c[0], "q": dict(zip(["10", "30", "50", "70", "90"], o))}
        elif len(o) == 3:
            official = {"date": c[0], "q": dict(zip(["10", "50", "90"], o))}
    return {"year": fy, "esp": esp, "official": official}


try:
    out["extras"]["cbrfc"] = cbrfc()
except Exception as e:
    print("cbrfc", e, file=sys.stderr)

path = sys.argv[1] if len(sys.argv) > 1 else "snapshot.json"
with open(path, "w") as f:
    json.dump(out, f, separators=(",", ":"))
print("ok", len(json.dumps(out)) // 1024, "KB")


# --- Daily log for scoring the spill model after runoff: one row per day, latest run of the day wins.
# Uses the page's default settings: spill = 0.92 x max(0, April 1 storage + April-July inflow - 486 KAF).
import csv
import os

HIST_AJ = [194, 185, 116, 235, 299, 519, 239, 470, 147, 461, 318, 312, 203, 209, 45, 204, 204, 462, 169, 212, 379, 255, 246, 275, 120, 84, 174, 227, 243, 348, 47, 455, 94, 85, 146, 526, 114, 109, 61]  # April-July inflow, KAF, 1988-2026
X0, SLOPE, WINTER_NET = 486.0, 0.92, 12.5


def p_spill(q, need):
    """Chance April-July inflow exceeds `need`, read off the forecast's exceedance levels."""
    pts = sorted((v, float(ex)) for ex, v in q.items() if v is not None)
    if need <= pts[0][0]:
        return min(0.97, pts[0][1] / 100 + 0.05)
    if need >= pts[-1][0]:
        return max(0.03, pts[-1][1] / 100 - 0.05)
    for (v1, e1), (v2, e2) in zip(pts, pts[1:]):
        if v1 <= need <= v2:
            return (e1 + (e2 - e1) * (need - v1) / ((v2 - v1) or 1)) / 100


try:
    local = now - dt.timedelta(hours=7)
    apr_year = local.year + 1 if local.month >= 4 else local.year
    apr1, nov10 = dt.datetime(apr_year, 4, 1), dt.datetime(apr_year - 1, 11, 10)
    frac = max(0.0, min(1.0, (apr1 - local.replace(tzinfo=None)) / (apr1 - nov10)))
    stor = out["mcphee"]["latest"]["value"]
    s0 = stor / 1000 + WINTER_NET * frac
    need = X0 - s0
    cb = out["extras"].get("cbrfc") or {}
    fc = (cb.get("official") or cb.get("esp") or {})
    q = fc.get("q") or {}
    dol = out["gauges"]["dolores"]["latest"]
    row = {
        "date": local.strftime("%Y-%m-%d"),
        "storage_af": round(stor),
        "dolores_cfs": dol[1] if dol else "",
        "est_apr1_kaf": round(s0, 1),
        "inflow_needed_kaf": round(need, 1),
        "odds_history": round(sum(1 for a in HIST_AJ if a > need) / len(HIST_AJ), 2),
        "fc_source": "official" if cb.get("official") else "esp" if cb.get("esp") else "",
        "fc_date": fc.get("date", ""),
        "fc_p10": q.get("10", ""), "fc_p30": q.get("30", ""), "fc_p50": q.get("50", ""), "fc_p70": q.get("70", ""), "fc_p90": q.get("90", ""),
        "spill_at_median_kaf": round(SLOPE * max(0, s0 + q["50"] - X0), 1) if q.get("50") else "",
        "odds_forecast": round(p_spill(q, need), 2) if q.get("50") else "",
    }
    log_path = os.path.join(os.path.dirname(os.path.abspath(path)), "log", "model_log.csv")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    rows = []
    if os.path.exists(log_path):
        with open(log_path, newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != row["date"]]
    rows.append(row)
    with open(log_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        w.writeheader()
        w.writerows(rows)
    print("logged", row["date"], row["est_apr1_kaf"], row["odds_history"])
except Exception as e:
    print("log", e, file=sys.stderr)
