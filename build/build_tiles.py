#!/usr/bin/env python3
"""
Bereitet Schotterwege und Orte (POIs) aus OpenStreetMap-Länderdateien von Geofabrik auf.

Läuft automatisch auf GitHub (siehe .github/workflows/daten.yml) – nicht auf dem eigenen PC nötig.

Ablauf je Land:
  1. Länderdatei (*.osm.pbf) und Grenzlinie (*.poly) von download.geofabrik.de laden
  2. Mit "osmium tags-filter" grob vorfiltern (macht die Datei ~50× kleiner), Original löschen
  3. Mit pyosmium genau nach den Regeln der App filtern (gleiche Regeln wie die Overpass-Abfrage)
  4. Auf Kacheln (0,05° × 0,075°, ca. 5,5 × 5,6 km) verteilen und je Block (4 × 4 Kacheln)
     eine JSON-Datei schreiben – gleiches Format wie der Browser-Speicher der App

Ergebnis (Ordner --out):
  index.json               Verzeichnis: welche Blöcke Daten haben und welche Kacheln vollständig abgedeckt sind
  blocks/<bi>/<bj>.json    Daten eines Blocks

Länder werden nacheinander verarbeitet und ihre Blöcke sofort auf die Platte geschrieben
(bei gemeinsamen Grenz-Blöcken zusammengeführt). So bleibt der Arbeitsspeicher auch für
ganz Europa im Rahmen.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

import osmium
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep

# ---- muss zur App passen (index.html: CELL_LAT, CELL_LON, BLOCK) ----
CELL_LAT = 0.05
CELL_LON = 0.075
BLOCK = 4
FORMAT = 1

GEOFABRIK = 'https://download.geofabrik.de/europe/'

# ---- Filterregeln (gleich wie die Overpass-Abfrage in index.html) ----
SURFACES = {'gravel', 'fine_gravel', 'compacted', 'unpaved', 'dirt', 'ground'}
ROAD_HW = {'unclassified', 'tertiary', 'residential', 'service'}
POI_AMENITY = {'fuel', 'restaurant', 'cafe', 'fast_food', 'biergarten', 'pub', 'drinking_water'}
POI_SHOP = {'supermarket', 'convenience', 'bakery', 'butcher', 'greengrocer', 'farm', 'motorcycle', 'motorcycle_repair'}
POI_TOURISM = {'camp_site', 'viewpoint'}

# nur diese Angaben werden gespeichert (wie WAY_KEYS / POI_KEYS in index.html)
WAY_KEYS = ['name', 'ref', 'highway', 'surface', 'tracktype', 'smoothness', 'access', 'vehicle', 'motor_vehicle', 'motorcycle']
POI_KEYS = ['name', 'brand', 'operator', 'amenity', 'shop', 'tourism', 'opening_hours', 'addr:street', 'addr:housenumber',
            'addr:postcode', 'addr:city', 'phone', 'contact:phone', 'website', 'contact:website', 'automated', 'self_service']

OSMIUM_FILTERS = [
    'w/highway=track,' + ','.join(sorted(ROAD_HW)),
    'nwr/amenity=' + ','.join(sorted(POI_AMENITY)),
    'nwr/shop=' + ','.join(sorted(POI_SHOP)),
    'nwr/tourism=' + ','.join(sorted(POI_TOURISM)),
]


def is_road(t):
    hw = t.get('highway')
    if hw == 'track':
        tt = t.get('tracktype')
        if tt is not None:
            return tt in ('grade1', 'grade2', 'grade3')
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
        self.cells = {}   # (i, j) -> {'w': set(ids), 'p': [poi, ...]}
        self.n_pois = 0

    def cell(self, key):
        c = self.cells.get(key)
        if c is None:
            c = self.cells[key] = {'w': set(), 'p': []}
        return c

    def add_way(self, wid, tags, coords):
        if wid in self.ways:
            return
        self.ways[wid] = [wid, tags, encode_polyline(coords)]
        for key in {cell_of(lat, lon) for lat, lon in coords}:
            self.cell(key)['w'].add(wid)

    def add_poi(self, typ, oid, lat, lon, tags):
        self.cell(cell_of(lat, lon))['p'].append([typ, oid, round(lat, 5), round(lon, 5), tags])
        self.n_pois += 1


class Collector(osmium.SimpleHandler):
    def __init__(self, store):
        super().__init__()
        self.s = store

    def node(self, n):
        t = n.tags
        if is_poi(t) and n.location.valid():
            self.s.add_poi('n', n.id, n.location.lat, n.location.lon, pick(t, POI_KEYS))

    def way(self, w):
        t = w.tags
        if not is_road(t):
            return
        coords = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
        if len(coords) >= 2:
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


def mark_coverage(shape, block_info, region_blocks):
    """Kacheln, die vollständig im Gebiet liegen, im Block-Verzeichnis als 'abgedeckt' markieren."""
    minx, miny, maxx, maxy = shape.bounds
    p = prep(shape)
    n = 0
    for i in range(math.floor(miny / CELL_LAT), math.floor(maxy / CELL_LAT) + 1):
        for j in range(math.floor(minx / CELL_LON), math.floor(maxx / CELL_LON) + 1):
            if p.contains(box(j * CELL_LON, i * CELL_LAT, (j + 1) * CELL_LON, (i + 1) * CELL_LAT)):
                bi, bj = i // BLOCK, j // BLOCK
                bit = (i - bi * BLOCK) * BLOCK + (j - bj * BLOCK)
                key = f'{bi},{bj}'
                block_info.setdefault(key, {'m': 0, 'd': 0})['m'] |= 1 << bit
                region_blocks.add(key)
                n += 1
    return n


# ------------------------------------------------------------------ Schreiben
def block_path(out_dir, bi, bj):
    return os.path.join(out_dir, 'blocks', str(bi), f'{bj}.json')


def flush(store, out_dir, block_info, region_blocks):
    """Daten eines Landes in die Block-Dateien schreiben (mit vorhandenen Grenz-Blöcken zusammenführen)."""
    blocks = {}
    for (i, j), c in store.cells.items():
        blocks.setdefault((i // BLOCK, j // BLOCK), []).append(((i, j), c))
    for (bi, bj), items in blocks.items():
        path = block_path(out_dir, bi, bj)
        recs = {}
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                for rec in json.load(f)['cells']:
                    recs[rec['k']] = rec
        for (i, j), c in items:
            k = f'{i}:{j}'
            rec = recs.get(k) or {'k': k, 'w': [], 'p': []}
            have_w = {w[0] for w in rec['w']}
            have_p = {(p[0], p[1]) for p in rec['p']}
            for wid in sorted(c['w']):
                if wid not in have_w:
                    rec['w'].append(store.ways[wid])
            for poi in c['p']:
                if (poi[0], poi[1]) not in have_p:
                    rec['p'].append(poi)
                    have_p.add((poi[0], poi[1]))
            recs[k] = rec
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'v': FORMAT, 'cells': [recs[k] for k in sorted(recs)]}, f, ensure_ascii=False, separators=(',', ':'))
        key = f'{bi},{bj}'
        block_info.setdefault(key, {'m': 0, 'd': 0})['d'] = 1
        region_blocks.add(key)


# ------------------------------------------------------------------ Hilfen
def download(url, dest):
    t0 = time.time()
    req = urllib.request.Request(url, headers={'User-Agent': 'Gravelfinder-BigEnduro/1.0 (GitHub Actions)'})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, 'wb') as f:
        shutil.copyfileobj(r, f, length=4 * 1024 * 1024)
    size = os.path.getsize(dest) / 1e6
    print(f'    geladen: {size:.0f} MB in {time.time() - t0:.0f} s', flush=True)


def fetch_text(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Gravelfinder-BigEnduro/1.0 (GitHub Actions)'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode('utf-8')


def fmt(n):
    return f'{n:,}'.replace(',', '.')


def dir_size(path):
    total = files = 0
    for root, _, names in os.walk(path):
        for n in names:
            total += os.path.getsize(os.path.join(root, n))
            files += 1
    return total, files


# ------------------------------------------------------------------ Hauptprogramm
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--regions-file', default='regions.json')
    ap.add_argument('--out', default='site/data/v1')
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
    t_all = time.time()

    for r in regions:
        rid = r['id']
        print(f'\n=== {r["name"]} ({rid}) ===', flush=True)
        t0 = time.time()
        raw = os.path.join(args.work, f'{rid}.osm.pbf')
        filtered = os.path.join(args.work, f'{rid}-gefiltert.osm.pbf')

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
        Collector(store).apply_file(filtered, locations=True)
        os.remove(filtered)
        print(f'    {fmt(len(store.ways))} Schotterwege, {fmt(store.n_pois)} Orte, {fmt(len(store.cells))} Kacheln mit Daten', flush=True)

        print('  4/4 Schreiben …', flush=True)
        region_blocks = set()
        flush(store, args.out, block_info, region_blocks)
        del store
        try:
            covered = mark_coverage(parse_poly(fetch_text(f'{GEOFABRIK}{rid}.poly')), block_info, region_blocks)
            print(f'    {fmt(covered)} Kacheln vollständig abgedeckt', flush=True)
        except Exception as e:  # ohne Grenzlinie: Daten sind da, Randgebiete lädt die App über Overpass nach
            print(f'    WARNUNG: Grenzlinie nicht verfügbar ({e}) – Abdeckung wird nicht markiert', flush=True)

        index_regions.append({'id': rid, 'name': r['name'], 'blocks': sorted(region_blocks)})
        print(f'  fertig in {time.time() - t0:.0f} s', flush=True)

    index = {
        'v': FORMAT,
        'built': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
        'cell': [CELL_LAT, CELL_LON],
        'block': BLOCK,
        'regions': index_regions,
        # je Block: [Abdeckungs-Maske der 16 Kacheln als Hex, 1 = Datei vorhanden]
        'blocks': {k: [format(v['m'], '04x'), v['d']] for k, v in sorted(block_info.items())},
    }
    with open(os.path.join(args.out, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, separators=(',', ':'))

    size, files = dir_size(args.out)
    print(f'\nGesamt: {fmt(files)} Dateien, {size / 1e6:.1f} MB, {time.time() - t_all:.0f} s', flush=True)
    if size > 900e6:
        print('WARNUNG: Fast 1 GB – das ist die Obergrenze von GitHub Pages. Siehe README ("Ganz Europa").', flush=True)


if __name__ == '__main__':
    main()
