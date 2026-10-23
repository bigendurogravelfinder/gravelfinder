#!/usr/bin/env python3
"""
Bereitet Schotterwege und Orte (POIs) aus OpenStreetMap-Länderdateien von Geofabrik auf.

Läuft automatisch auf GitHub (siehe .github/workflows/daten.yml) – nicht auf dem eigenen PC nötig.

Ablauf je Land:
  1. Länderdatei (*.osm.pbf) und Grenzlinie (*.poly) von download.geofabrik.de laden
  2. Mit "osmium tags-filter" grob vorfiltern (macht die Datei ~50× kleiner), Original löschen
  3. Mit pyosmium genau nach den Regeln der App filtern (gleiche Regeln wie die Overpass-Abfrage)
  4. Linien vereinfachen (Punkte mit < 3 m Abweichung weglassen – auf der Karte unsichtbar)
  5. Auf Kacheln (0,05° × 0,075°, ca. 5,5 × 5,6 km) verteilen und je Block (4 × 4 Kacheln)
     eine gzip-komprimierte JSON-Datei schreiben

Ergebnis (Ordner --out):
  index.json                  Verzeichnis: Länder (mit Größe), Blöcke, vollständig abgedeckte Kacheln
  blocks/<bi>/<bj>.json.gz    Daten eines Blocks (gzip – GitHub Pages erlaubt höchstens 1 GB)

Länder werden nacheinander verarbeitet und ihre Blöcke sofort auf die Platte geschrieben
(gemeinsame Grenz-Blöcke werden zusammengeführt). So bleibt der Arbeitsspeicher auch für
ganz Europa im Rahmen. Welche Kacheln "vollständig abgedeckt" sind, wird am Ende aus der
Vereinigung ALLER Ländergrenzen berechnet – Kacheln auf einer Grenze zwischen zwei
aufbereiteten Ländern gelten damit ebenfalls als vollständig.
"""
import argparse
import gzip
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

import osmium
from shapely.geometry import LineString, Polygon, box, mapping
from shapely.ops import unary_union
from shapely.prepared import prep

# ---- muss zur App passen (index.html: CELL_LAT, CELL_LON, BLOCK) ----
CELL_LAT = 0.05
CELL_LON = 0.075
BLOCK = 4
FORMAT = 2
SIMPLIFY_M = 3.0          # Linien-Vereinfachung in Metern
PAGES_LIMIT = 1_000_000_000

GEOFABRIK = 'https://download.geofabrik.de/europe/'
UA = {'User-Agent': 'Gravelfinder-BigEnduro/1.0 (GitHub Actions)'}

# ---- Filterregeln (gleich wie die Overpass-Abfrage in index.html) ----
# unbefestigt bis Hard Enduro (5 Qualitätsstufen in der App: grade1–5, Wiese/Fels/Sand/Schlamm)
SURFACES = {'gravel', 'fine_gravel', 'compacted', 'unpaved', 'dirt', 'ground', 'earth', 'pebblestone',
            'grass', 'rock', 'sand', 'mud'}
GRADES = {'grade1', 'grade2', 'grade3', 'grade4', 'grade5'}
ROAD_HW = {'unclassified', 'tertiary', 'residential', 'service'}
POI_AMENITY = {'fuel', 'restaurant', 'cafe', 'fast_food', 'biergarten', 'pub', 'drinking_water'}
POI_SHOP = {'supermarket', 'convenience', 'bakery', 'butcher', 'greengrocer', 'farm', 'motorcycle', 'motorcycle_repair'}
POI_TOURISM = {'camp_site', 'viewpoint'}
# Ortsnamen (werden von der App über den Wegen beschriftet): 1 = Stadt, 2 = Markt/Kleinstadt, 3 = Dorf
PLACE_RANK = {'city': 1, 'town': 2, 'village': 3}

# nur diese Angaben werden gespeichert (wie WAY_KEYS / POI_KEYS in index.html)
WAY_KEYS = ['name', 'ref', 'highway', 'surface', 'tracktype', 'smoothness', '4wd_only', 'access', 'vehicle', 'motor_vehicle', 'motorcycle']
POI_KEYS = ['name', 'brand', 'operator', 'amenity', 'shop', 'tourism', 'opening_hours', 'addr:street', 'addr:housenumber',
            'addr:postcode', 'addr:city', 'phone', 'contact:phone', 'website', 'contact:website', 'automated', 'self_service']

OSMIUM_FILTERS = [
    'w/highway=track,' + ','.join(sorted(ROAD_HW)),
    'nwr/amenity=' + ','.join(sorted(POI_AMENITY)),
    'nwr/shop=' + ','.join(sorted(POI_SHOP)),
    'nwr/tourism=' + ','.join(sorted(POI_TOURISM)),
    'n/place=' + ','.join(sorted(PLACE_RANK)),
    'w/admin_level=2',          # Staatsgrenzen (für die Grenzlinien in der App)
]
# Staatsgrenzen: Linien mit admin_level=2 an Land (Seegrenzen weglassen), vereinfacht auf 15 m
BORDER_SIMPLIFY_M = 15.0
SEA_BORDER = {'territorial', 'baseline', 'maritime', 'eez', 'contiguous'}


NOT_BORDER_KEYS = ('building', 'office', 'government', 'amenity', 'landuse', 'leisure', 'shop', 'tourism', 'man_made')


def is_land_border(t):
    # boundary=administrative MUSS eingetragen sein: admin_level=2 allein steht auch an Behörden mit
    # Bundeszuständigkeit (z. B. office=government in Hannover) – das sind keine Grenzen
    if t.get('admin_level') != '2' or t.get('boundary') != 'administrative':
        return False
    if any(k in t for k in NOT_BORDER_KEYS):
        return False
    return t.get('maritime') != 'yes' and t.get('border_type') not in SEA_BORDER and t.get('natural') != 'coastline'


NON_LATIN = re.compile('[Ͱ-Ͽἀ-῿Ѐ-ӿ]')   # griechisch, kyrillisch
LATIN_KEYS = ('name:sr-Latn', 'name:latin', 'int_name', 'name:en', 'name:de')


def latin_name(t):
    """Lateinische Schreibweise für kyrillische/griechische Ortsnamen (z. B. Београд → Beograd). Sonst ''."""
    if not NON_LATIN.search(t.get('name', '')):
        return ''
    for k in LATIN_KEYS:
        v = t.get(k)
        if v and not NON_LATIN.search(v):
            return v
    return ''   # die App schreibt dann selbst um


def population(t):
    try:
        return int(str(t.get('population', '0')).replace('.', '').replace(' ', '').split(';')[0] or 0)
    except ValueError:
        return 0


def is_road(t):
    hw = t.get('highway')
    if hw == 'track':
        tt = t.get('tracktype')
        if tt is not None:
            return tt in GRADES
        return t.get('surface') in SURFACES
    if hw in ROAD_HW:
        return t.get('surface') in SURFACES
    return False


def is_poi(t):
    return t.get('amenity') in POI_AMENITY or t.get('shop') in POI_SHOP or t.get('tourism') in POI_TOURISM


def pick(t, keys):
    return {k: t.get(k) for k in keys if k in t}


def cell_of(lat, lon):
    return (math.floor(lat / CELL_LAT), math.floor(lon / CELL_LON))


def simplify(coords, tol=SIMPLIFY_M):
    """Douglas-Peucker in Metern (lokale Projektion). Behält Anfangs- und Endpunkt."""
    if len(coords) <= 2:
        return coords
    lat0 = coords[0][0]
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 110540.0
    xy = [(lon * kx, lat * ky) for lat, lon in coords]
    simple = LineString(xy).simplify(tol, preserve_topology=False)
    out = [(y / ky, x / kx) for x, y in simple.coords]
    return out if len(out) >= 2 else [coords[0], coords[-1]]


def encode_polyline(coords):
    """Google-Polyline-Kodierung, 5 Nachkommastellen (~1 m) – etwa 6× kleiner als Zahlenlisten."""
    out = []
    plat = plon = 0
    for lat, lon in coords:
        ilat, ilon = round(lat * 1e5), round(lon * 1e5)
        for v in (ilat - plat, ilon - plon):
            v = ~(v << 1) if v < 0 else (v << 1)
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1f)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return ''.join(out)


# ------------------------------------------------------------------ Sammeln
class Store:
    def __init__(self):
        self.ways = {}    # id -> [id, tags, polyline]
        self.cells = {}   # (i, j) -> {'w': set(ids), 'p': [poi, ...], 'l': [ort, ...]}
        self.n_pois = 0
        self.n_places = 0
        self.n_points = 0
        self.n_points_raw = 0

    def cell(self, key):
        c = self.cells.get(key)
        if c is None:
            c = self.cells[key] = {'w': set(), 'p': [], 'l': []}
        return c

    def add_place(self, name, rank, lat, lon, pop, latin=''):
        # [Name, Rang, lat, lon, Einwohner(, lateinischer Name – nur bei kyrillischen/griechischen Namen)]
        rec = [name, rank, round(lat, 4), round(lon, 4), pop]
        if latin:
            rec.append(latin)
        self.cell(cell_of(lat, lon))['l'].append(rec)
        self.n_places += 1

    def add_way(self, wid, tags, coords):
        if wid in self.ways:
            return
        # Kachel-Zuordnung mit ALLEN Punkten (wie in der App), Speicherung vereinfacht
        keys = {cell_of(lat, lon) for lat, lon in coords}
        simple = simplify(coords)
        self.n_points_raw += len(coords)
        self.n_points += len(simple)
        self.ways[wid] = [wid, tags, encode_polyline(simple)]
        for key in keys:
            self.cell(key)['w'].add(wid)

    def add_poi(self, typ, oid, lat, lon, tags):
        self.cell(cell_of(lat, lon))['p'].append([typ, oid, round(lat, 5), round(lon, 5), tags])
        self.n_pois += 1


class Collector(osmium.SimpleHandler):
    def __init__(self, store, borders):
        super().__init__()
        self.s = store
        self.borders = borders     # gemeinsam für alle Länder: Weg-ID -> kodierte Grenzlinie (Grenzwege nur einmal)

    def node(self, n):
        t = n.tags
        if not n.location.valid():
            return
        if is_poi(t):
            self.s.add_poi('n', n.id, n.location.lat, n.location.lon, pick(t, POI_KEYS))
        rank = PLACE_RANK.get(t.get('place'))
        if rank and 'name' in t:
            self.s.add_place(t.get('name'), rank, n.location.lat, n.location.lon, population(t), latin_name(t))

    def way(self, w):
        t = w.tags
        border = is_land_border(t)
        if not border and not is_road(t):
            return
        coords = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
        if len(coords) < 2:
            return
        if border and w.id not in self.borders:
            self.borders[w.id] = encode_polyline(simplify(coords, BORDER_SIMPLIFY_M))
        if is_road(t):
            self.s.add_way(w.id, pick(t, WAY_KEYS), coords)

    def area(self, a):
        # Orte, die als Fläche eingetragen sind (z. B. Tankstellen-Gelände): Mittelpunkt verwenden
        t = a.tags
        if not is_poi(t):
            return
        lat_sum = lon_sum = 0.0
        n = 0
        for ring in a.outer_rings():
            for nd in ring:
                if nd.location.valid():
                    lat_sum += nd.lat
                    lon_sum += nd.lon
                    n += 1
        if n:
            self.s.add_poi('w' if a.from_way() else 'r', a.orig_id(), lat_sum / n, lon_sum / n, pick(t, POI_KEYS))


# ------------------------------------------------------------------ Grenzlinie
def parse_poly(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    outers, holes = [], []
    i = 1  # erste Zeile = Name
    while i < len(lines):
        header = lines[i]
        i += 1
        if header == 'END':
            break
        pts = []
        while i < len(lines) and lines[i] != 'END':
            parts = lines[i].split()
            pts.append((float(parts[0]), float(parts[1])))  # lon lat
            i += 1
        i += 1
        if len(pts) >= 3:
            (holes if header.startswith('!') else outers).append(Polygon(pts).buffer(0))
    shape = unary_union(outers)
    if holes:
        shape = shape.difference(unary_union(holes))
    return shape


def mark_coverage(shape, block_info):
    """Kacheln, die vollständig im Gebiet liegen, im Block-Verzeichnis als 'abgedeckt' markieren."""
    minx, miny, maxx, maxy = shape.bounds
    p = prep(shape)
    n = 0
    for i in range(math.floor(miny / CELL_LAT), math.floor(maxy / CELL_LAT) + 1):
        for j in range(math.floor(minx / CELL_LON), math.floor(maxx / CELL_LON) + 1):
            if p.contains(box(j * CELL_LON, i * CELL_LAT, (j + 1) * CELL_LON, (i + 1) * CELL_LAT)):
                bi, bj = i // BLOCK, j // BLOCK
                bit = (i - bi * BLOCK) * BLOCK + (j - bj * BLOCK)
                block_info.setdefault(f'{bi},{bj}', {'m': 0, 'd': 0})['m'] |= 1 << bit
                n += 1
    return n


# ------------------------------------------------------------------ Schreiben
def block_path(out_dir, bi, bj):
    return os.path.join(out_dir, 'blocks', str(bi), f'{bj}.json.gz')


def flush(store, out_dir, block_info, region_blocks):
    """Daten eines Landes in die Block-Dateien schreiben (mit vorhandenen Grenz-Blöcken zusammenführen)."""
    blocks = {}
    for (i, j), c in store.cells.items():
        blocks.setdefault((i // BLOCK, j // BLOCK), []).append(((i, j), c))
    for (bi, bj), items in blocks.items():
        path = block_path(out_dir, bi, bj)
        recs = {}
        if os.path.exists(path):
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                for rec in json.load(f)['cells']:
                    recs[rec['k']] = rec
        for (i, j), c in items:
            k = f'{i}:{j}'
            rec = recs.get(k) or {'k': k, 'w': [], 'p': [], 'l': []}
            rec.setdefault('l', [])
            have_w = {w[0] for w in rec['w']}
            have_p = {(p[0], p[1]) for p in rec['p']}
            have_l = {(p[0], p[2], p[3]) for p in rec['l']}   # (Eintrag kann 5 oder 6 Felder haben)
            for pl in c['l']:
                if (pl[0], pl[2], pl[3]) not in have_l:
                    rec['l'].append(pl)
                    have_l.add((pl[0], pl[2], pl[3]))
            for wid in sorted(c['w']):
                if wid not in have_w:
                    rec['w'].append(store.ways[wid])
            for poi in c['p']:
                if (poi[0], poi[1]) not in have_p:
                    rec['p'].append(poi)
                    have_p.add((poi[0], poi[1]))
            recs[k] = rec
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = json.dumps({'v': FORMAT, 'cells': [recs[k] for k in sorted(recs)]}, ensure_ascii=False, separators=(',', ':'))
        with gzip.open(path, 'wt', encoding='utf-8', compresslevel=9) as f:
            f.write(data)
        key = f'{bi},{bj}'
        block_info.setdefault(key, {'m': 0, 'd': 0})['d'] = 1
        region_blocks.add(key)


# ------------------------------------------------------------------ Hilfen
def download(url, dest):
    t0 = time.time()
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=900) as r, open(dest, 'wb') as f:
                shutil.copyfileobj(r, f, length=8 * 1024 * 1024)
            break
        except Exception as e:
            if attempt == 2:
                raise
            print(f'    Download-Fehler ({e}), neuer Versuch in 30 s …', flush=True)
            time.sleep(30)
    print(f'    geladen: {os.path.getsize(dest) / 1e6:.0f} MB in {time.time() - t0:.0f} s', flush=True)


def fetch_text(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode('utf-8')


def fmt(n):
    return f'{n:,}'.replace(',', '.')


def block_size(out_dir, key):
    bi, bj = key.split(',')
    p = block_path(out_dir, bi, bj)
    return os.path.getsize(p) if os.path.exists(p) else 0


def write_outlines(index_regions, shapes_by_id, out_dir):
    """Vereinfachte Länder-Umrisse (ca. 1 km genau) für die Übersicht beim Herauszoomen."""
    def rnd(obj):
        if isinstance(obj, (list, tuple)):
            if obj and isinstance(obj[0], float):
                return [round(obj[0], 3), round(obj[1], 3)]
            return [rnd(o) for o in obj]
        return obj
    features = []
    for reg in index_regions:
        shape = shapes_by_id.get(reg['id'])
        if shape is None:
            continue
        geom = mapping(shape.simplify(0.01, preserve_topology=True))
        features.append({'type': 'Feature', 'properties': {'id': reg['id'], 'name': reg['name']},
                         'geometry': {'type': geom['type'], 'coordinates': rnd(geom['coordinates'])}})
    with open(os.path.join(out_dir, 'outlines.json'), 'w', encoding='utf-8') as f:
        json.dump({'type': 'FeatureCollection', 'features': features}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'  Länder-Umrisse: {len(features)} Länder, {os.path.getsize(os.path.join(out_dir, "outlines.json")) / 1e3:.0f} KB', flush=True)


def write_borders(borders, out_dir):
    """Staatsgrenzen (admin_level=2, an Land) als eine Datei – die App zeichnet sie in allen Zoomstufen."""
    path = os.path.join(out_dir, 'borders.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'v': 1, 'b': [borders[k] for k in sorted(borders)]}, f, separators=(',', ':'))
    print(f'  Grenzlinien: {fmt(len(borders))} Abschnitte, {os.path.getsize(path) / 1e3:.0f} KB', flush=True)


# ------------------------------------------------------------------ Hauptprogramm
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--regions-file', default='regions.json')
    ap.add_argument('--out', default='site/data/v2')
    ap.add_argument('--work', default='work')
    ap.add_argument('--only', default='', help='nur diese Länder (IDs, kommagetrennt) – zum Testen')
    ap.add_argument('--skip-prefilter', action='store_true',
                    help='ohne osmium-tool (nur für kleine Testländer sinnvoll)')
    args = ap.parse_args()

    with open(args.regions_file, encoding='utf-8') as f:
        regions = json.load(f)['regions']
    only = {s.strip() for s in args.only.split(',') if s.strip()}
    regions = [r for r in regions if (r['id'] in only if only else r.get('active'))]
    if not regions:
        sys.exit('Keine Region ausgewählt.')

    shutil.rmtree(args.out, ignore_errors=True)
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.work, exist_ok=True)

    block_info = {}
    index_regions = []
    shapes = []
    shapes_by_id = {}
    borders = {}
    failed = []
    t_all = time.time()

    for n, r in enumerate(regions, 1):
        rid = r['id']
        print(f'\n=== [{n}/{len(regions)}] {r["name"]} ({rid}) ===', flush=True)
        t0 = time.time()
        raw = os.path.join(args.work, f'{rid}.osm.pbf')
        filtered = os.path.join(args.work, f'{rid}-gefiltert.osm.pbf')
        try:
            print('  1/4 Herunterladen …', flush=True)
            download(f'{GEOFABRIK}{rid}-latest.osm.pbf', raw)

            if args.skip_prefilter:
                print('  2/4 Vorfiltern übersprungen', flush=True)
                os.replace(raw, filtered)
            else:
                print('  2/4 Vorfiltern (osmium) …', flush=True)
                subprocess.run(['osmium', 'tags-filter', raw, *OSMIUM_FILTERS, '-o', filtered, '--overwrite'], check=True)
                os.remove(raw)
                print(f'    gefiltert: {os.path.getsize(filtered) / 1e6:.0f} MB', flush=True)

            print('  3/4 Auswerten (pyosmium) …', flush=True)
            store = Store()
            Collector(store, borders).apply_file(filtered, locations=True)
            os.remove(filtered)
            red = 100 - 100 * store.n_points / max(1, store.n_points_raw)
            print(f'    {fmt(len(store.ways))} Schotterwege, {fmt(store.n_pois)} POI, {fmt(store.n_places)} Ortsnamen, '
                  f'{fmt(len(store.cells))} Kacheln mit Daten, '
                  f'Linienpunkte -{red:.0f} % durch Vereinfachung', flush=True)

            print('  4/4 Schreiben …', flush=True)
            region_blocks = set()
            flush(store, args.out, block_info, region_blocks)
            del store
            try:
                shape = parse_poly(fetch_text(f'{GEOFABRIK}{rid}.poly'))
                shapes.append(shape)
                shapes_by_id[rid] = shape
            except Exception as e:  # ohne Grenzlinie: Daten sind da, Randgebiete lädt die App über Overpass nach
                print(f'    WARNUNG: Grenzlinie nicht verfügbar ({e})', flush=True)
            index_regions.append({'id': rid, 'name': r['name'], 'blocks': sorted(region_blocks)})
            print(f'  fertig in {time.time() - t0:.0f} s', flush=True)
        except Exception as e:
            # Ein fehlerhaftes Land soll nicht den ganzen Lauf abbrechen
            print(f'  FEHLER bei {r["name"]}: {e} – Land wird übersprungen', flush=True)
            failed.append(r['name'])
            for p in (raw, filtered):
                if os.path.exists(p):
                    os.remove(p)

    print('\nAbdeckung berechnen …', flush=True)
    if shapes:
        covered = mark_coverage(unary_union(shapes), block_info)
        print(f'  {fmt(covered)} Kacheln vollständig abgedeckt', flush=True)

    # Größe je Land (komprimiert, so wie sie heruntergeladen wird)
    sizes = {k: block_size(args.out, k) for k in block_info}
    for reg in index_regions:
        reg['size'] = sum(sizes.get(k, 0) for k in reg['blocks'])
    total = sum(sizes.values())

    index = {
        'v': FORMAT,
        'built': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
        'cell': [CELL_LAT, CELL_LON],
        'block': BLOCK,
        'gz': 1,
        'places': 1,   # Block-Dateien enthalten Ortsnamen (Feld "l")
        'size': total,
        'regions': sorted(index_regions, key=lambda r: r['name']),
        # je Block: [Abdeckungs-Maske der 16 Kacheln als Hex, 1 = Datei vorhanden]
        'blocks': {k: [format(v['m'], '04x'), v['d']] for k, v in sorted(block_info.items())},
    }
    with open(os.path.join(args.out, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, separators=(',', ':'))

    write_outlines(index_regions, shapes_by_id, args.out)
    write_borders(borders, args.out)

    files = sum(1 for v in block_info.values() if v['d']) + 1
    print(f'\nGesamt: {len(index_regions)} Länder, {fmt(files)} Dateien, {total / 1e6:.0f} MB, {(time.time() - t_all) / 60:.0f} min', flush=True)
    print('Größte Länder: ' + ', '.join(f'{r["name"]} {r["size"] / 1e6:.0f} MB'
                                       for r in sorted(index_regions, key=lambda r: -r['size'])[:8]), flush=True)
    if failed:
        print('ÜBERSPRUNGEN (Fehler): ' + ', '.join(failed), flush=True)
    if total > 0.95 * PAGES_LIMIT:
        sys.exit(f'ABBRUCH: {total / 1e6:.0f} MB – zu groß für GitHub Pages (max. 1 GB). Siehe README ("Wenn es nicht mehr passt").')


if __name__ == '__main__':
    main()
