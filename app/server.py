import hashlib, hmac, json, os, sqlite3, time
from flask import Flask, request, jsonify, render_template_string

DB_PATH = os.getenv('WMC_DB', 'wmc.sqlite3')
SECRET = os.getenv('WMC_HASH_KEY', 'change-me').encode()
WINDOW = float(os.getenv('WMC_CORRELATION_WINDOW_SEC', '20'))
app = Flask(__name__)

SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS wifi_observations (
 id INTEGER PRIMARY KEY, ts REAL NOT NULL, sensor TEXT NOT NULL,
 device_hash TEXT NOT NULL, rssi REAL, channel TEXT, source TEXT DEFAULT 'kismet'
);
CREATE INDEX IF NOT EXISTS idx_wifi_ts ON wifi_observations(ts);
CREATE INDEX IF NOT EXISTS idx_wifi_dev ON wifi_observations(device_hash, ts);
CREATE TABLE IF NOT EXISTS motion_events (
 id INTEGER PRIMARY KEY, ts REAL NOT NULL, camera TEXT NOT NULL,
 zone TEXT, event_type TEXT DEFAULT 'motion', confidence REAL, raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_motion_ts ON motion_events(ts);
CREATE TABLE IF NOT EXISTS correlations (
 id INTEGER PRIMARY KEY, motion_id INTEGER NOT NULL, wifi_id INTEGER NOT NULL,
 dt REAL NOT NULL, score REAL NOT NULL,
 UNIQUE(motion_id, wifi_id)
);
'''

def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c

def anon(identifier: str) -> str:
    return hmac.new(SECRET, identifier.strip().lower().encode(), hashlib.sha256).hexdigest()[:20]

def correlate_motion(conn, motion_id, ts):
    rows = conn.execute('SELECT id, ts, rssi FROM wifi_observations WHERE ts BETWEEN ? AND ?', (ts-WINDOW, ts+WINDOW)).fetchall()
    for r in rows:
        dt = abs(ts-r['ts'])
        time_score = max(0.0, 1.0-dt/WINDOW)
        rssi = r['rssi'] if r['rssi'] is not None else -90
        signal_score = min(1.0, max(0.0, (rssi+100)/60))
        score = round(0.75*time_score + 0.25*signal_score, 4)
        conn.execute('INSERT OR IGNORE INTO correlations(motion_id,wifi_id,dt,score) VALUES(?,?,?,?)', (motion_id,r['id'],dt,score))

def correlate_wifi(conn, wifi_id, ts):
    rows = conn.execute('SELECT id, ts FROM motion_events WHERE ts BETWEEN ? AND ?', (ts-WINDOW, ts+WINDOW)).fetchall()
    for r in rows:
        dt = abs(ts-r['ts'])
        score = round(max(0.0, 1.0-dt/WINDOW), 4)
        conn.execute('INSERT OR IGNORE INTO correlations(motion_id,wifi_id,dt,score) VALUES(?,?,?,?)', (r['id'],wifi_id,dt,score))

@app.post('/api/wifi')
def wifi():
    d = request.get_json(force=True)
    identifier = d.get('mac') or d.get('device_id')
    if not identifier:
        return {'error':'mac or device_id required'}, 400
    ts = float(d.get('ts', time.time()))
    with db() as c:
        cur = c.execute('INSERT INTO wifi_observations(ts,sensor,device_hash,rssi,channel,source) VALUES(?,?,?,?,?,?)',
            (ts, d.get('sensor','pi'), anon(identifier), d.get('rssi'), str(d.get('channel','')), d.get('source','kismet')))
        correlate_wifi(c, cur.lastrowid, ts)
    return {'ok':True}, 201

@app.post('/api/motion')
def motion():
    d = request.get_json(force=True)
    ts = float(d.get('ts', time.time()))
    with db() as c:
        cur = c.execute('INSERT INTO motion_events(ts,camera,zone,event_type,confidence,raw_json) VALUES(?,?,?,?,?,?)',
            (ts,d.get('camera','camera'),d.get('zone'),d.get('event_type','motion'),d.get('confidence'),json.dumps(d)))
        correlate_motion(c, cur.lastrowid, ts)
    return {'ok':True,'motion_id':cur.lastrowid}, 201

@app.get('/api/events')
def events():
    with db() as c:
        rows=c.execute('''SELECT m.id,m.ts,m.camera,m.zone,m.event_type,m.confidence,
            COUNT(c.id) matches, ROUND(MAX(c.score),3) best_score
            FROM motion_events m LEFT JOIN correlations c ON c.motion_id=m.id
            GROUP BY m.id ORDER BY m.ts DESC LIMIT 200''').fetchall()
    return jsonify([dict(x) for x in rows])

@app.get('/api/event/<int:mid>')
def event(mid):
    with db() as c:
        m=c.execute('SELECT * FROM motion_events WHERE id=?',(mid,)).fetchone()
        if not m: return {'error':'not found'},404
        w=c.execute('''SELECT w.ts,w.sensor,w.device_hash,w.rssi,w.channel,c.dt,c.score
            FROM correlations c JOIN wifi_observations w ON w.id=c.wifi_id
            WHERE c.motion_id=? ORDER BY c.score DESC''',(mid,)).fetchall()
    return jsonify({'motion':dict(m),'wifi':[dict(x) for x in w]})

@app.get('/')
def index():
    return render_template_string('''<!doctype html><meta charset=utf-8><title>WiFi Motion Correlator</title>
<style>body{font:14px system-ui;margin:2rem;max-width:1100px}table{border-collapse:collapse;width:100%}td,th{padding:.55rem;border-bottom:1px solid #ddd;text-align:left}.muted{color:#666}</style>
<h1>WiFi Motion Correlator</h1><p class=muted>Metadata-only event correlation. Device identifiers are HMAC-hashed before storage.</p>
<table><thead><tr><th>Time</th><th>Camera</th><th>Zone</th><th>Type</th><th>Matches</th><th>Best score</th></tr></thead><tbody id=t></tbody></table>
<script>async function load(){let r=await fetch('/api/events'),d=await r.json();t.innerHTML=d.map(x=>`<tr><td>${new Date(x.ts*1000).toLocaleString()}</td><td>${x.camera}</td><td>${x.zone??''}</td><td>${x.event_type}</td><td><a href=/api/event/${x.id}>${x.matches}</a></td><td>${x.best_score??''}</td></tr>`).join('')}load();setInterval(load,5000)</script>''')

if __name__ == '__main__':
    app.run(host=os.getenv('WMC_HOST','0.0.0.0'), port=int(os.getenv('WMC_PORT','8787')))
