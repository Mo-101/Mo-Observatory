"""Persistent single-node collector and read-only WSGI API. No fabricated fallback."""
import os, json, sqlite3, hashlib, time, signal, sys, math
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from pathlib import Path
import mimetypes
from urllib.error import HTTPError

DB = os.getenv("DATABASE_PATH", "data/observatory.sqlite")
STALE = int(os.getenv("STALE_SECONDS", "1800"))
CHANNELS = {"wind": ("Solar wind", "km/s", 0, 3000), "bz": ("IMF Bz", "nT", -500, 500),
            "dcx": ("Dcx", "nT", -3000, 1000), "fof2": ("Hermanus foF2", "MHz", 0, 50),
            "hmf2": ("Hermanus hmF2", "km", 50, 2000), "tindex": ("T-index", "", -500, 1000)}

def now():
    return datetime.now(timezone.utc).isoformat()

def connection():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c

def init():
    with connection() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS payloads(hash TEXT PRIMARY KEY, body BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY, url TEXT, retrieved_at TEXT,
          http_status INTEGER, hash TEXT, result TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY, source TEXT, channel TEXT,
          observed_at TEXT, value REAL, unit TEXT, hash TEXT, retrieved_at TEXT,
          UNIQUE(source, channel, observed_at));
        CREATE TABLE IF NOT EXISTS conflicts(id INTEGER PRIMARY KEY, source TEXT, channel TEXT,
          observed_at TEXT, original_hash TEXT, incoming_hash TEXT, detected_at TEXT,
          UNIQUE(source,channel,observed_at,incoming_hash));
        """)

def validate(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("measurements"), list):
        raise ValueError("expected object with measurements array")
    if payload.get("source") != "SANSA":
        raise ValueError("source must be SANSA; international channels cannot replace it")
    rows = []
    seen = set()
    for m in payload["measurements"]:
        if not isinstance(m, dict) or not isinstance(m.get("observedAt"), str):
            raise ValueError("measurement object and timestamp required")
        key = m["id"]
        if key not in CHANNELS or key in seen:
            raise ValueError("unknown or duplicate channel")
        seen.add(key)
        label, unit, low, high = CHANNELS[key]
        if m["unit"] != unit:
            raise ValueError("unit mismatch")
        dt = datetime.fromisoformat(m["observedAt"].replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("observation timezone required")
        if dt.timestamp() > time.time() + 300:
            raise ValueError("future observation")
        value = m["value"]
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not math.isfinite(value) or not low <= value <= high):
            raise ValueError("invalid channel value")
        rows.append((key, dt.astimezone(timezone.utc).isoformat(), value, unit))
    if not rows:
        raise ValueError("empty measurements")
    return rows

def ingest(url, body, status=200):
    stamp, digest = now(), hashlib.sha256(body).hexdigest()
    result, error = "accepted", None
    with connection() as c:
        c.execute("INSERT OR IGNORE INTO payloads VALUES(?,?)", (digest, body))
        try:
            if status != 200:
                raise ValueError(f"upstream HTTP {status}")
            rows = validate(json.loads(body))
            for key, observed, value, unit in rows:
                old = c.execute("SELECT * FROM observations WHERE source=? AND channel=? AND observed_at=?",
                                ("SANSA", key, observed)).fetchone()
                if old and old["value"] != value:
                    c.execute("INSERT OR IGNORE INTO conflicts(source,channel,observed_at,original_hash,incoming_hash,detected_at) VALUES(?,?,?,?,?,?)",
                              ("SANSA", key, observed, old["hash"], digest, stamp))
                    result = "conflict"
                elif not old:
                    c.execute("INSERT INTO observations(source,channel,observed_at,value,unit,hash,retrieved_at) VALUES(?,?,?,?,?,?,?)",
                              ("SANSA", key, observed, value, unit, digest, stamp))
        except (ValueError, KeyError, TypeError) as e:
            result, error = "rejected", str(e)
        c.execute("INSERT INTO attempts(url,retrieved_at,http_status,hash,result,error) VALUES(?,?,?,?,?,?)",
                  (url, stamp, status, digest, result, error))
    return result

def snapshot():
    with connection() as c:
        attempts = [dict(r) for r in c.execute("SELECT * FROM attempts ORDER BY id DESC LIMIT 20")]
        measurements = []
        for key, (label, unit, _, _) in CHANNELS.items():
            rows = c.execute("""SELECT o.*, EXISTS(SELECT 1 FROM conflicts q WHERE q.source=o.source
              AND q.channel=o.channel AND q.observed_at=o.observed_at) AS conflict
              FROM observations o WHERE channel=? ORDER BY observed_at DESC LIMIT 120""", (key,)).fetchall()
            latest = rows[0] if rows else None
            age = time.time() - datetime.fromisoformat(latest["observed_at"]).timestamp() if latest else None
            health = ("unavailable" if not latest else "conflict" if latest["conflict"] else
                      "missing" if latest["value"] is None else "stale" if age > STALE else "fresh")
            measurements.append(dict(id=key, label=label, unit=unit, value=latest["value"] if latest else None,
              observedAt=latest["observed_at"] if latest else None, ageSeconds=age, health=health,
              hash=latest["hash"] if latest else None,
              history=[dict(at=r["observed_at"], value=r["value"] if not r["conflict"] else None) for r in reversed(rows)]))
        fresh = all(m["health"] == "fresh" for m in measurements)
        wind, bz = measurements[0], measurements[1]
        usable = wind["health"] == bz["health"] == "fresh" and wind["observedAt"] == bz["observedAt"]
        return dict(status="fresh" if fresh else "degraded", measurements=measurements, attempts=attempts,
                    speedEnergyIndex=(wind["value"]/400)**2 if usable else None,
                    couplingIndex=wind["value"]/400*max(0,-bz["value"]) if usable else None,
                    staleSeconds=STALE, serverTime=now())

def app(environ, start_response):
    path = environ["PATH_INFO"]
    status, body, mime = "200 OK", b"", "application/json"
    if environ["REQUEST_METHOD"] != "GET":
        status, body = "405 Method Not Allowed", b'{"error":"read-only API"}'
    elif path == "/healthz":
        with connection() as c:
            c.execute("SELECT 1").fetchone()
        body = b'{"service":"up","note":"liveness is not telemetry freshness"}'
    elif path == "/api/observatory":
        body = json.dumps(snapshot(), allow_nan=False).encode()
    elif path == "/readyz":
        s = snapshot()
        status = "200 OK" if s["status"] == "fresh" else "503 Service Unavailable"
        body = json.dumps({"telemetry":s["status"]}).encode()
    elif path.startswith("/api/evidence/"):
        digest = path.rsplit("/",1)[-1]
        with connection() as c:
            row = c.execute("SELECT body FROM payloads WHERE hash=?", (digest,)).fetchone()
        if row:
            body, mime = row["body"], "application/octet-stream"
        else:
            status, body = "404 Not Found", b'{"error":"evidence not found"}'
    else:
        root = Path(os.getenv("STATIC_ROOT", "frontend/dist")).resolve()
        target = (root / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
        if target.is_relative_to(root) and target.is_file():
            body, mime = target.read_bytes(), mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        else:
            status, body = "404 Not Found", b'{"error":"not found"}'
    start_response(status, [("Content-Type", mime), ("Content-Length", str(len(body))),
                            ("Cache-Control","no-store"), ("X-Content-Type-Options","nosniff")])
    return [body]

def collect():
    import threading
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    urls = [u.strip() for u in os.getenv("SOURCE_URLS","").split(",") if u.strip()]
    if not urls:
        raise SystemExit("SOURCE_URLS is required: configure a verified normalized SANSA JSON endpoint")
    if any(not u.startswith("https://") for u in urls):
        raise SystemExit("Production sources require HTTPS")
    interval = max(30, int(os.getenv("POLL_SECONDS","60")))
    while not stop.is_set():
        for url in urls:
            try:
                request = Request(url, headers={"Accept":"application/json","User-Agent":"MoStar-Observatory/1.0"})
                with urlopen(request, timeout=15) as response:
                    body = response.read(2_000_001)
                    if len(body) > 2_000_000:
                        raise ValueError("payload exceeds 2 MB limit")
                    result = ingest(url, body, response.status)
                print(json.dumps({"at":now(),"source":url,"result":result}), flush=True)
            except HTTPError as e:
                ingest(url, e.read(2_000_000), e.code)
                print(json.dumps({"at":now(),"source":url,"httpStatus":e.code}), flush=True)
            except Exception as e:
                with connection() as c:
                    c.execute("INSERT INTO attempts(url,retrieved_at,result,error) VALUES(?,?,?,?)",
                              (url, now(), "failed", str(e)))
                print(json.dumps({"at":now(),"source":url,"error":str(e)}), flush=True)
        stop.wait(interval)

if __name__ == "__main__":
    init()
    if sys.argv[1:] == ["collect"]:
        collect()
    elif len(sys.argv) == 3 and sys.argv[1] == "backup":
        with connection() as source, sqlite3.connect(sys.argv[2]) as target:
            source.backup(target)
    else:
        from waitress import serve
        serve(app, host="0.0.0.0", port=8080, threads=4)
