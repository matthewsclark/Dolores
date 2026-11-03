"""Build data/snapshot.json from live public APIs (USGS, NOAA NWPS, CO DWR, NRCS AWDB).
Same shape the page's live loader produces in the browser."""
import json, urllib.request, datetime as dt, sys
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"dolores-dashboard"}), timeout=60) as r:
        return json.load(r)
now = dt.datetime.now(dt.timezone.utc)
start = (now - dt.timedelta(days=124)).strftime("%m/%d/%Y")
wy = dt.date(now.year if now.month >= 10 else now.year - 1, 10, 1).isoformat()
h_begin = (now - dt.timedelta(days=2)).strftime("%Y-%m-%d")
GAUGES = [  # id, name, usgs, nwps lid, reach
 ("rico","Dolores below Rico","09165000","DRRC2","upper"),
 ("westfork","West Fork near Stoner","09166000",None,"upper"),
 ("dolores","Dolores at Dolores","09166500","DOLC2","upper"),
 ("lostcanyon","Lost Canyon Creek","09166950","LCCC2","upper"),
 ("belowdam","Below McPhee Dam",None,"DRMC2","lower"),
 ("slickrock","Slick Rock","09168730","SLIC2","lower"),
 ("bedrock","Near Bedrock","09171100","DBDC2","lower"),
 ("sanmiguel","San Miguel at Uravan",None,"SMUC2","lower"),
 ("gateway","Near Gateway","09179450","DGAC2","lower"),
 ("cisco","Near Cisco, UT","09180000","DOLU1","lower"),
]
out = {"generated": now.isoformat(), "mode":"snapshot", "gauges":{}, "mcphee":{}, "diversions":[], "snow":[]}
sites = ",".join(g[2] for g in GAUGES if g[2])
usgs = get(f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={sites}&parameterCd=00060&period=P30D")
useries = {}
for ts in usgs["value"]["timeSeries"]:
    sid = ts["sourceInfo"]["siteCode"][0]["value"]
    pts=[]
    for x in ts["values"][0]["value"]:
        v=float(x["value"])
        if v<=-999: continue
        t=dt.datetime.fromisoformat(x["dateTime"])
        if t.minute==0: pts.append([int(t.timestamp()*1000), v])
    last=ts["values"][0]["value"]
    last=[x for x in last if float(x["value"])>-999]
    useries[sid]=(pts, [int(dt.datetime.fromisoformat(last[-1]["dateTime"]).timestamp()*1000), float(last[-1]["value"])] if last else None)
lcs=get("https://waterservices.usgs.gov/nwis/iv/?format=json&sites=09166950&parameterCd=00065&period=P30D")
lc_stage=[]
for ts in lcs["value"]["timeSeries"]:
    for x in ts["values"][0]["value"]:
        v=float(x["value"])
        if v>-999: lc_stage.append([int(dt.datetime.fromisoformat(x["dateTime"]).timestamp()*1000), v])
for gid,name,usid,lid,reach in GAUGES:
    g={"name":name,"usgs":usid,"lid":lid,"reach":reach,"series":[],"latest":None,"forecast":[],"flood":None,"stage":None}
    if usid in useries: g["series"],g["latest"]=useries[usid]
    if lid:
        try:
            meta=get(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}")
            ob=meta.get("status",{}).get("observed",{})
            g["flood"]=ob.get("floodCategory"); g["stage"]=ob.get("primary")
            g["cats"]={k:v.get("stage") for k,v in (meta.get("flood",{}).get("categories") or {}).items()}
            sf=get(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow")
            obs=[[int(dt.datetime.fromisoformat(p["validTime"].replace("Z","+00:00")).timestamp()*1000), p["secondary"]*1000] for p in (sf.get("observed") or {}).get("data",[]) if p.get("secondary",-999)>-999]
            fc=[[int(dt.datetime.fromisoformat(p["validTime"].replace("Z","+00:00")).timestamp()*1000), p["secondary"]*1000] for p in (sf.get("forecast") or {}).get("data",[]) if p.get("secondary",-999)>-999]
            g["forecast"]=fc
            g["rating"]=sorted({round(p["primary"],2):round(p["secondary"]*1000) for p in (sf.get("forecast") or {}).get("data",[]) if p.get("secondary",-999)>0 and p.get("primary",-999)>-999}.items())
            if not g["series"] and obs:
                g["series"]=[p for p in obs if dt.datetime.fromtimestamp(p[0]/1000).minute==0] or obs
                g["latest"]=obs[-1]; g["seriesSource"]="NOAA NWPS"
        except Exception as e: print("nwps",lid,e,file=sys.stderr)
    if gid=="lostcanyon": g["stageSeries"]=lc_stage
    out["gauges"][gid]=g
B="https://dwr.state.co.us/Rest/GET/api/v2/telemetrystations"
st=get(f"{B}/telemetrytimeseriesday/?abbrev=MCPRESCO&parameter=STORAGE&startDate={start}&format=json")["ResultList"]
out["mcphee"]["storage"]=[[x["measDate"][:10], round(x["measValue"])] for x in st]
rel=get(f"{B}/telemetrytimeseriesday/?abbrev=DOLBMCCO&parameter=DISCHRG&startDate={start}&format=json")["ResultList"]
out["mcphee"]["release"]=[[x["measDate"][:10], round(x["measValue"],1)] for x in rel]
for ab,label in [("MCPRESCO","McPhee storage"),("DOLBMCCO","Release below dam"),("DOLTUNCO","Dolores Tunnel"),("DOVCANCO","Dove Creek Canal"),("MVIDIVCO","Lone Pine Canal (MVIC)"),("UCANALCO","U Lateral (MVIC)"),("TOWCANCO","Towaoc Canal")]:
    s=get(f"{B}/telemetrystation/?abbrev={ab}&format=json")["ResultList"][0]
    rec={"id":ab,"name":label,"value":s.get("measValue"),"unit":s.get("units"),"t":s.get("measDateTime")}
    if ab=="MCPRESCO": out["mcphee"]["latest"]=rec
    elif ab=="DOLBMCCO": out["mcphee"]["releaseNow"]=rec
    else: out["diversions"].append(rec)
SNOW=[("1185:CO:SNTL","Black Mesa",11580),("1060:CO:SNTL","Sharkstooth",10730),("465:CO:SNTL","El Diente Peak",10210),("586:CO:SNTL","Lizard Head Pass",10190),("589:CO:SNTL","Lone Cone",9730),("739:CO:SNTL","Scotch Creek",9160),("08M03:CO:SNOW","Groundhog",8970)]
sd=get("https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data?stationTriplets="+",".join(s[0] for s in SNOW)+"&elements=WTEQ,SNWD,PREC&duration=DAILY&beginDate="+wy+"&endDate="+now.strftime("%Y-%m-%d")+"&centralTendencyType=MEDIAN")
sh=get("https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data?stationTriplets="+",".join(s[0] for s in SNOW)+"&elements=WTEQ,SNWD,PREC&duration=HOURLY&beginDate="+h_begin+"&endDate="+(now+dt.timedelta(days=1)).strftime("%Y-%m-%d"))
hby={s["stationTriplet"]:s for s in sh}
by={s["stationTriplet"]:s for s in sd}
for trip,name,elev in SNOW:
    rec={"id":trip,"name":name,"elev":elev,"manual":trip.endswith("SNOW")}
    for e in by.get(trip,{}).get("data",[]):
        code=e["stationElement"]["elementCode"]
        rec[code]=[[v["date"],v.get("value"),v.get("median")] for v in e["values"]]
    rec["hourly"]={}
    for e in hby.get(trip,{}).get("data",[]):
        vals=[[v["date"],v.get("value")] for v in e["values"] if v.get("value") is not None]
        if vals: rec["hourly"][e["stationElement"]["elementCode"]]=vals[-1]
    out["snow"].append(rec)
json.dump(out, open(sys.argv[1] if len(sys.argv)>1 else "snapshot.json","w"), separators=(",",":"))
print("ok", len(json.dumps(out))//1024, "KB")
