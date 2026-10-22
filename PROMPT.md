# Gravelfinder Big Enduro – vollständige Anforderungen

Dieses Dokument beschreibt alles, was nötig ist, um die App, die Datenaufbereitung und die Veröffentlichung
gleichwertig neu zu erstellen. Ich bin kein Programmierer: Alles muss ohne Installation auf meinem PC
funktionieren, Erklärungen bitte in einfachen Worten.

---

## 1. Zweck und Grundidee

Ich fahre Big Enduro und möchte auf einer Karte sehen, welche **fahrbaren Schotterstraßen** und welche
**nützlichen Orte (POI)** es gibt – schnell, auch am Handy und auch **ohne Netz** unterwegs.

Das Projekt besteht aus zwei Teilen:

1. **Die App:** EINE Datei `index.html` (HTML, CSS, JavaScript in einer Datei, kein Build-Schritt).
   Funktioniert per Doppelklick, auf jedem Webspace und auf GitHub Pages.
2. **Die Datenaufbereitung:** Ein Python-Skript, das auf **GitHub Actions** (in der Cloud, kostenlos)
   jede Woche ganz Europa aus OpenStreetMap aufbereitet und als kleine, komprimierte Dateien auf
   **GitHub Pages** veröffentlicht. Die App lädt diese Dateien in Bruchteilen einer Sekunde.
   Nur für Gebiete außerhalb der aufbereiteten Länder fällt die App auf die (langsame) Overpass API zurück.

## 2. Dateien im Projekt

```
index.html                    die App
manifest.webmanifest          macht die App installierbar (Name, Symbole, Vollbild, freie Drehung)
sw.js                         Service Worker (App startet auch ohne Netz)
icon-192.png, icon-512.png, icon-maskable-512.png, apple-touch-icon.png   App-Symbole
regions.json                  Länderliste für die Aufbereitung
build/build_tiles.py          Aufbereitungs-Skript (Python)
build/requirements.txt        osmium>=3.7, shapely>=2.0
.github/workflows/daten.yml   Zeitplan und Ablauf auf GitHub
README.md                     Anleitung (Einrichtung, Alltag, Technik)
PROMPT.md                     dieses Dokument
```

Veröffentlicht wird (GitHub Pages):
```
index.html, manifest.webmanifest, sw.js, die vier Symbole
data/v2/index.json            Verzeichnis (Länder, Blöcke, Abdeckung, Größen)
data/v2/outlines.json         vereinfachte Länder-Umrisse
data/v2/blocks/<bi>/<bj>.json.gz   Daten je Block
```

---

## 3. App – Karte

- **Leaflet 1.9.4** über CDN (`https://unpkg.com/leaflet@1.9.4/dist/leaflet.css` und `.js`), `preferCanvas: true`.
- **Start:** Wels, Oberösterreich (48.1575, 14.0289), Zoomstufe 12.
- **Kartenposition in der Adresszeile:** `#breite,länge,zoom` (z. B. `#46.05,14.51,12`), wird bei jedem
  Verschieben per `history.replaceState` aktualisiert und beim Start ausgewertet (für Lesezeichen/Links).
- **Hintergrundkarten** (Umschalter oben links):
  - Standard: **`https://tile.openstreetmap.de/{z}/{x}/{y}.png`** (deutscher OSM-Server).
    WICHTIG: NICHT `tile.openstreetmap.org` verwenden – der sperrt Seiten, die per Doppelklick (file://)
    geöffnet werden, weil dann kein Referer mitgeschickt wird („403 Access blocked“).
  - Topokarte: `https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png` (maxZoom 17).
  - CyclOSM: `https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png` (zeigt Wege und Oberflächen gut).
- Quellenangabe „© OpenStreetMap-Mitwirkende“ (Link auf openstreetmap.org/copyright), Leaflet-Präfix ausblenden.
- Maßstab unten rechts (metrisch).
- **Zoomstufe immer sichtbar:** kleines Feld direkt unter den Knöpfen + / − (oben links, 44 px breit wie die Knöpfe),
  kleine Überschrift „ZOOM“ und darunter die Zahl fett; aktualisiert sich bei jedem Zoomen (eigenes `L.Control`).

## 4. Schotterwege – Regeln

Als Schotterstraße gelten:
- `highway=track` mit `tracktype=grade1|grade2|grade3`
- `highway=track` **ohne** `tracktype`, aber mit `surface=gravel|fine_gravel|compacted|unpaved|dirt|ground`
- `highway=unclassified|tertiary|residential|service` mit einer dieser Oberflächen

**Gesperrt** (ausgeblendet, optional gestrichelt grau anzeigbar): Der genaueste vorhandene Schlüssel entscheidet,
in der Reihenfolge `motorcycle` → `motor_vehicle` → `vehicle` → `access`. Gesperrt, wenn alle Werte
(bei `;`-Listen) in der Sperrliste des Schlüssels stehen:
- `motorcycle`: no, private
- `motor_vehicle`: no, private, agricultural, forestry, destination
- `vehicle`: no, private
- `access`: no, private

(Damit gilt z. B. `motor_vehicle=no` + `motorcycle=yes` als fahrbar.)

### Qualitätsstufen (Einfärbung)
Der Filter oben bleibt unverändert. Jeder Weg wird zusätzlich in eine von drei Stufen eingeteilt:

| Stufe | Bedeutung | smoothness | tracktype | surface | Standardfarbe |
|---|---|---|---|---|---|
| hoch | fest und gleichmäßig | excellent, good, intermediate | grade1 | asphalt, concrete, paved, compacted, fine_gravel | Grün #00e04b |
| mittel | typischer Schotter, lose Stellen | bad | grade2 | gravel, unpaved | Gelb #ffe600 |
| niedrig | Erde/Naturboden, bei Nässe rutschig | very_bad, horrible, very_horrible, impassable | grade3 (grade4/5) | dirt, ground | Rot #ff1a4b |

- Farben bewusst **leuchtend** – die Hintergrundkarte hat selbst Grün (Wald), Gelb und Rot (Straßen), aber nur in
  Pastelltönen. Früher gespeicherte alte Standardfarben (#1fa83c, #ffc107, #e53935) werden automatisch ersetzt,
  selbst gewählte Farben bleiben.

- Ist `smoothness` eingetragen, entscheidet nur diese Angabe. Sonst zählt die **schlechtere** von `tracktype`
  und `surface` (bewusst vorsichtig). Ohne jede Angabe: mittel.
- Verteilung (Test Slowenien/Kroatien): 12 % hoch, 54 % mittel, 34 % niedrig; Raum Wels: 73 / 247 / 288 Wege.
- Je Stufe im Menü: Farbfeld (Farbe ändern, sofort wirksam), Häkchen (Stufe ein-/ausblenden), Name, kurze
  Beschreibung und Anzahl im Ausschnitt; Link „Standardfarben wiederherstellen“.
- Gezeichnet wird die schlechteste Stufe zuerst, damit gute Wege obenauf liegen. Der Zähler unten zählt nur
  eingeblendete Stufen.
- Gesperrte Wege bleiben grau gestrichelt (unabhängig von der Stufe).

### Darstellung
- Linienbreite 1–5 px (Schieberegler).
- Transparenz 0–100 % (Schieberegler, 5er-Schritte). Wirkt auf die **ganze Wege-Ebene** (CSS-Opacity einer
  eigenen Leaflet-Pane), nicht auf jede Linie – sonst scheint der dunkle Rand durch und die Farbe wird bräunlich.
- Kräftiger schwarzer Rand (#000, Deckkraft 0,95) unter jeder Linie: Randbreite = Linienbreite + 2
  (ab 4 px Linie + 3).
- **Hintergrund abschwächen** 0–100 % (Schieberegler, 10er-Schritte, Standard **60 %**): CSS-Filter auf die
  Kachel-Ebene `saturate(1 − 0,9·f) brightness(1 + 0,1·f) contrast(1 − 0,2·f)` – die Karte verliert Farbe,
  die Wege stechen heraus, Beschriftungen bleiben lesbar.
- Gesperrte Wege (Schalter „Auch gesperrte Wege anzeigen“): grau #7a7a7a, gestrichelt „6 6“, liegen unter den fahrbaren.
- Farb-/Breiten-/Transparenzänderungen sofort, ohne neu zu laden.
- Wege auf eigener Canvas-Ebene mit Klick-Toleranz 10 px (am Handy gut treffbar).

### Ortsnamen über den Wegen
Die Ortsnamen der Hintergrundkarte liegen unter den Wegen und gehen dort unter (Beschriftungs-Kacheln ohne
Bild gibt es nur noch mit API-Schlüssel). Darum beschriftet die App selbst:
- Daten: `place=city` (Rang 1), `town` (2), `village` (3) mit `name` – in den Schnell-Daten je Kachel als
  `l: [[Name, Rang, lat, lon, Einwohner], …]`, über Overpass zusätzlich `node["place"~"^(city|town|village)$"]["name"]`.
- Eigene Leaflet-Pane über den Wegen (zIndex 480, unter POI 600) mit `pointer-events: none` – Klicks gehen durch.
- Zoom 9–10: Städte und Märkte, ab Zoom 11 auch Dörfer. Reihenfolge Rang, dann Einwohner; überlappende Namen
  werden weggelassen (einfache Rechteck-Prüfung), höchstens 250 Namen.
- Stil: dunkle Schrift mit weißem Schein (text-shadow), Städte 15 px extra fett, Märkte 13 px fett, Dörfer 12 px.
- Schalter „Ortsnamen über den Wegen anzeigen“ (Standard an).
- Schalter „Ortsnamen über den POI-Symbolen“ (Standard an): Namen-Pane zIndex 610 statt 480 (POIs 600);
  Klicks gehen trotzdem durch (pointer-events none).
- Frei einstellbar: Farbe (Farbfeld, Standard #1a1a1a), Transparenz 0–80 %, weißer Leuchtrand 0–100 %
  (CSS-Variablen `--lbl-color`, `--lbl-op`, `--lbl-halo`); Vorschaufeld „Wels“ im Menü zeigt die Wirkung sofort.
- Slowenien: 4.889 Ortsnamen, Datenmenge praktisch unverändert.

### Popup beim Antippen eines Weges
Name (oder ref, sonst „Ohne Namen“), Warnhinweis „⛔ Für Motorräder gesperrt / eingeschränkt“ falls gesperrt,
**Qualität** mit farbigem Punkt und Begründung (z. B. „mittel (tracktype grade2)“), Straßentyp, Oberfläche, Tracktype, Smoothness (jeweils deutsche Beschreibung + OSM-Wert, z. B.
„grade2 – Schotter, meist fest“, „schlecht – robustes Fahrzeug (bad)“), Zugangsbeschränkungen
(access/vehicle/motor_vehicle/motorcycle oder „keine Beschränkung eingetragen“), Link „Weg auf openstreetmap.org ansehen ↗“.

## 5. Orte (POI)

Sieben Kategorien, einzeln ein-/ausschaltbar, mit Anzahl im Ausschnitt:

| id | Name | Symbol | Farbe | OSM-Regel |
|---|---|---|---|---|
| fuel | Tankstellen | ⛽ | #d32f2f | amenity=fuel |
| food | Lebensmittel | 🛒 | #2e7d32 | shop=supermarket, convenience, bakery, butcher, greengrocer, farm |
| gastro | Gasthaus / Café | 🍽️ | #ef6c00 | amenity=restaurant, cafe, fast_food, biergarten, pub |
| moto | Motorrad-Werkstatt / Händler | 🏍️ | #37474f | shop=motorcycle, motorcycle_repair |
| water | Trinkwasser | 💧 | #0277bd | amenity=drinking_water |
| camp | Campingplätze | ⛺ | #6d4c41 | tourism=camp_site |
| view | Aussichtspunkte | 🔭 | #7b1fa2 | tourism=viewpoint |

- Punkte, Wege und Flächen (Mittelpunkt). Passt ein Ort zu mehreren Kategorien, bestimmt die erste
  eingeschaltete das Symbol (Tankstelle mit Shop = ⛽; ist Tankstelle aus, erscheint sie als 🛒).
- Symbol: runder Kreis 32 px mit Emoji, weißer Rand, Schatten; unter Zoom 14 auf 70 % verkleinert.
- Alle Kategorien werden immer mitgeladen – Ein-/Ausschalten zeichnet nur neu.
- **„POIs ab Zoomstufe einblenden“** mit Knöpfen − / + (Standard 11, Bereich 9–18; unter 11 nur in Gebieten mit
  Schnell-Daten); Statuszeile zeigt „POIs ab Zoom X“, Zusammenfassung „… · ab Zoom X“.
- **Popup:** Symbol + Name (sonst Marke/Betreiber/Art), Art (deutsch), Marke, Öffnungszeiten, Adresse,
  Telefon (tel-Link), Webseite (nur http/https, „www.“ ergänzt), bei Tankstellen „Selbstbedienung / Automat“,
  Link „Navigation starten ↗“ (`https://www.google.com/maps/dir/?api=1&destination=lat,lon`),
  Link „Auf openstreetmap.org ansehen ↗“.

## 6. Mein Standort

- Button „Mein Standort“ unten links (groß, rund). Startet `navigator.geolocation.watchPosition`
  (hohe Genauigkeit) und zentriert beim ersten Treffer (mind. Zoom 14). Erneutes Tippen zentriert wieder.
- Wurde der Standort früher schon erlaubt (`navigator.permissions` = granted), wird er beim Start sofort
  angezeigt, ohne die Karte zu verschieben.
- Markierung: blauer Punkt (#1a73e8) mit weißem Rand und Schatten, **pulsierender Ring**, hellblauer
  **Genauigkeitskreis**, **Fahrtrichtungspfeil** (nur wenn heading gemeldet und Tempo > 1 m/s).
  Popup: „Du bist hier“, Genauigkeit, Tempo.
- Eigene Leaflet-Pane (zIndex 650) mit **`pointer-events: none`** – sonst fängt die Zeichenfläche des
  Genauigkeitskreises alle Klicks auf Wege und Orte ab. Der Punkt selbst bleibt antippbar.
- Der Button rückt automatisch immer über die Hinweise am unteren Rand (Höhe der Statusleiste messen;
  zusätzlich nach jeder Änderung der Hinweise direkt neu setzen, nicht nur per ResizeObserver).
- Fehlermeldungen: Zugriff verweigert / GPS aus – verständlich auf Deutsch.

## 7. Laden der Daten

### Kacheln und Blöcke
- Feste Kacheln: **0,05° Breite × 0,075° Länge** (ca. 5,5 × 5,6 km). Schlüssel `"i:j"` mit
  `i = floor(lat/0.05)`, `j = floor(lon/0.075)`.
- **Block** = 4 × 4 Kacheln (ca. 22 × 22 km), Schlüssel `"bi,bj"` mit `bi = floor(i/4)`, `bj = floor(j/4)`.
- Ein Weg gehört zu jeder Kachel, in der er (mindestens) einen seiner Original-Punkte hat.

### Zoomstufen
- **Ab Zoom 11 (Detail):** Wege einzeln (antippbar, Popup, schwarzer Rand), Orte (POI), Overpass-Abfragen.
- **Zoom 9–10 (Übersicht):** Schotterwege aus Schnell-Daten/Browser-Speicher, aber
  - alle Wege einer Stufe als EINE Leaflet-Polyline mit vielen Teilen (statt zehntausender Einzel-Linien),
    nicht antippbar, `smoothFactor` 1,5;
  - dünn und ohne schwarzen Rand (Zoom 10: max. 2 px, Zoom 9: 1 px, Deckkraft 0,9) – sonst „bunter Teppich“;
  - keine Orte, keine Overpass-Abfragen (zu groß); Status: „… · Orte und Details ab näherem Zoom“ bzw.
    „für Gebiete außerhalb der Schnell-Daten weiter hineinzoomen“.
  - Messung Raum Wels Zoom 9 (Handygröße): ca. 56.000 Wege, erstes Laden ca. 3 s, Neuzeichnen ca. 0,3 s.
- **Unter Zoom 9:** keine Wege, Hinweis „🔍 Bitte weiter hineinzoomen“ und grüne Offline-Länder (Abschnitt 11).
- Während Block-Dateien eintreffen höchstens alle 400 ms neu zeichnen (sonst wird es bei Zoom 9 extrem langsam),
  am Ende einmal vollständig.

### Ablauf beim Verschieben/Zoomen
- `moveend` mit 800 ms Wartezeit (Debounce); sind alle Kacheln schon im Arbeitsspeicher, sofort zeichnen.
- Benötigt werden die Kacheln im Ausschnitt + 10 % Rand. Reihenfolge:
  1. Arbeitsspeicher
  2. Browser-Speicher (IndexedDB)
  3. **Fertige Daten** (statische Block-Dateien) für Kacheln, die vollständig in einem aufbereiteten Land liegen –
     parallel, 4 gleichzeitig
  4. **Overpass** nur für die übrigen Kacheln
- Grenz-Kacheln (nicht vollständig abgedeckt): Teil-Daten aus den Block-Dateien sofort anzeigen, aber die
  Kachel gilt nicht als vollständig → Overpass ergänzt sie.
- Ist eine Block-Datei nicht erreichbar (z. B. offline), werden diese Kacheln über Overpass versucht.
- Anzeige unten: „X Schotterwege im Ausschnitt (+ Y gesperrt)“, während des Ladens Spinner +
  „Lade Schotterwege … (Teil 1 von 3)“.

### Overpass (Fallback)
- `https://overpass-api.de/api/interpreter`, POST, `[out:json][timeout:90][bbox:s,w,n,e]`.
- **Eine** Abfrage für Wege UND alle POI-Kategorien:
  Wege-Set `->.wege` (`out geom qt`), Orte-Set `->.orte` (`out center tags qt`).
- Fehlende Kacheln werden zu Aufträgen gebündelt: passt alles in ein Rechteck von höchstens 42 Kacheln →
  eine Anfrage, sonst je 4×4-Block eine; nächstgelegene zuerst.
- **Warteschlange:** immer nur eine Overpass-Anfrage gleichzeitig. Aufträge für den sichtbaren Ausschnitt
  haben Vorrang vor Vorlade-Aufträgen (laufendes Vorladen wird unterbrochen und später wiederholt).
  Ein laufender Ausschnitts-Auftrag wird abgebrochen (AbortController), wenn keine seiner Kacheln mehr gebraucht wird.
- **Überlastung:** HTTP 429/502/503/504, `remark` mit „runtime error/timed out/out of memory“ sowie
  `TypeError` (der überlastete Server schickt Fehlerseiten ohne CORS-Freigabe!) → automatisch noch 2× versuchen
  (nach 5 und 10 s, Wartezeit abbrechbar), Anzeige „Server ausgelastet – neuer Versuch in X s …“.
  Danach verständliche Fehlermeldung mit Button „Erneut versuchen“.

### Browser-Speicher (IndexedDB)
- Datenbank `schotterkarte` **Version 2**, Tabellen:
  - `blocks` (keyPath `b`): Block-Dateien **so komprimiert, wie sie vom Server kommen** (`{ b, v, t, data: ArrayBuffer }`).
    Beim Vorladen wird NICHT entpackt – erst beim Ansehen. Das macht das Vorladen gut 2× schneller und den
    Speicher ca. 40 % kleiner (Österreich 20 statt 35 MB).
  - `cells` (keyPath `k`): einzelne entpackte Kacheln (nur noch aus Overpass).
  - `idx` (k, t, v, s = Größe, b = Block-Verweis): kleines Verzeichnis, wird beim Start komplett gelesen.
- Beim Anzeigen: Kacheln mit `b` → Block aus `blocks` lesen und entpacken; sonst aus `cells`.
- Schreiben gesammelt: bis zu 16 Blöcke (oder alle 400 ms) in EINER Transaktion; am Ende des Vorladens sofort.
- Parallele Downloads: 6 beim Anzeigen, 8 beim Vorladen.
- Löschen eines Landes entfernt Block-Dateien nur, wenn keine ihrer Kacheln zu einem noch gewählten Land gehört.
- Messung (PC, Daten von GitHub): Deutschland 83 MB in 19 s (vorher ca. 1,9 MB/s, jetzt ca. 4,4 MB/s);
  danach Wels/München aus dem Speicher in < 1 s ohne Download.
- Datensatz je Kachel: `{ k, v: 2, t: Zeitstempel, w: [[id, tags, Koordinaten]], p: [[typ, id, lat, lon, tags]], l: [[Name, Rang, lat, lon, Einwohner]] }`
  (v = DATA_VERSION; Erhöhen erzwingt Neuladen aller gespeicherten Kacheln – v2 = mit Ortsnamen).
  Koordinaten: entweder flache Zahlenliste (Overpass) oder Polyline-String (fertige Daten).
- Gespeichert werden nur die angezeigten Angaben:
  Wege: name, ref, highway, surface, tracktype, smoothness, access, vehicle, motor_vehicle, motorcycle;
  Orte: name, brand, operator, amenity, shop, tourism, opening_hours, addr:street, addr:housenumber,
  addr:postcode, addr:city, phone, contact:phone, website, contact:website, automated, self_service.
- Aktualität: Overpass-Kacheln 30 Tage; Kacheln aus fertigen Daten werden neu geholt, sobald es einen neueren
  Datenstand gibt (und sie älter als 1 Tag sind).
- `navigator.storage.persist()` anfragen. Arbeitsspeicher begrenzen (über 120.000 Wege → leeren, neu aus IndexedDB).
- Ohne IndexedDB (privater Modus, eingebettete Vorschau) läuft alles weiter, nur ohne dauerhaften Speicher (Hinweis anzeigen).
- Einstellungen in `localStorage` (Schlüssel `schotterkarte.settings`); jeder Zugriff in try/catch.

### Fertige Daten (statisch)
- Quellen der Reihe nach probieren: `data/v2/` (neben der App) und
  `https://bigendurogravelfinder.github.io/gravelfinder/data/v2/` (für Doppelklick / anderen Webspace).
  GitHub Pages erlaubt fremden Seiten den Zugriff (`Access-Control-Allow-Origin: *`).
- `index.json`: `{ v: 2, built: "2026-10-20T19:27Z", cell, block, gz: 1, size, regions: [{ id, name, size, blocks: ["bi,bj", …] }], blocks: { "bi,bj": ["Abdeckungsmaske 16 Bit hex", 1 = Datei vorhanden] } }`.
  Bit der Kachel im Block: `(i − bi·4)·4 + (j − bj·4)`.
- Block-Dateien `.json.gz`: Inhalt `{ v: 2, cells: [Datensätze] }`, Linien als **Google-Polyline (5 Nachkommastellen)**.
  Entpacken mit `DecompressionStream('gzip')`; vorher an den ersten Bytes (1f 8b) prüfen, ob der Server
  schon entpackt geliefert hat.
- Blöcke ohne Datei (nur Abdeckung) ergeben leere Kacheln ohne Download.

---

## 8. Menü (Tab-Stil)

- Kasten oben rechts (Breite 300 px, max. Bildschirmbreite − 76 px), Kopfzeile „☰ Menü“ zum Ein-/Ausklappen.
  Liegt über „Mein Standort“ und der Statusleiste (z-index höher).
- **Beim ersten Start ist alles eingeklappt**; danach werden Menü-Zustand, aktiver Tab und offener Unterpunkt gemerkt.
- **Tab-Leiste** (bleibt beim Scrollen oben) mit vier Hauptpunkten – Symbol, Name und darunter klein der aktuelle Stand:
  | Tab | Inhalt | Kurzstand unter dem Tab |
  |---|---|---|
  | ⚙ **Einstellungen** | drei aufklappbare Unterpunkte (siehe unten) | – |
  | 🧭 **Route** | „Route planen“ (Abschnitt 10a) | z. B. „41 km“ / „2 Punkte“ |
  | 📂 **GPX** | eigene GPX-Tracks (Abschnitt 10c) | z. B. „2 Tracks“ / „1/2 Tracks“ |
  | 💾 **Offline** | Offline Karten (Abschnitt 9) | z. B. „56 MB“ |
- **Unterpunkte von „Einstellungen“** (`<details>`, immer nur einer offen, mit Kurz-Zusammenfassung):
  1. **〰️ Schotterwege** – Qualitätsstufen (Farbe + Ein/Aus), Linienbreite, Transparenz, „Auch gesperrte Wege anzeigen“.
     Zusammenfassung: drei Farbproben (ausgeblendete blass), „2 px, 30 % transparent, mit gesperrten“.
  2. **🗺️ Karte & Ortsnamen** – Hintergrund abschwächen, Ortsnamen an/aus, über POIs, Farbe/Transparenz/Leuchtrand.
     Zusammenfassung: „Hintergrund 60 % · Ortsnamen über allem“.
  3. **📍 POI** – 7 Kategorien, „POIs ab Zoomstufe“ (− / +). Zusammenfassung: „⛽ (1 von 7) · ab Zoom 11“.
  4. **📱 App** – Knopf „📲 Als App installieren“ (nur wenn der Browser `beforeinstallprompt` liefert) mit Hinweistext
     (installiert / Chrome-Menü ⋮ / iPhone: Teilen → Zum Home-Bildschirm / bei `file://` nicht möglich) und
     Schalter **„Bildschirm wach halten“** (Screen Wake Lock, gespeichert; bei `visibilitychange` neu anfordern;
     ohne Unterstützung ausgegraut). Zusammenfassung: „im Browser · Bildschirm normal“ bzw. „installiert · Bildschirm bleibt wach“.
  (Bewusst „Darstellung“ in „Schotterwege“ und „Karte & Ortsnamen“ geteilt – sonst zu lang am Handy.)
- Der Kartenknopf 🧭 (Punkte setzen) schaltet das Menü automatisch auf den Tab „Route“.
- Inhalt scrollbar (max. Bildschirmhöhe − 90 px), große Bedienelemente (mind. 40–44 px hoch).

### Standardeinstellungen beim ersten Aufruf
- Qualitätsfarben **Grün / Gelb / Rot** (leuchtend, alle drei Stufen eingeblendet), Linienbreite **2 px**,
  Transparenz 0 %, **Hintergrund abschwächen 60 %**, gesperrte Wege aus.
- POI: **nur Tankstellen** eingeschaltet.
- Menü und alle Abschnitte eingeklappt. Keine Länder offline ausgewählt.

## 9. Offline Karten (Länder)

- Überschrift „Länder offline speichern“, darunter **„Ganz Europa“** (Checkbox mit Gesamtgröße; Zustand
  „teilweise“, wenn nur manche Länder gewählt) und die **Liste aller Länder** (alphabetisch, scrollbar,
  max. 260 px hoch) mit Checkbox, Download-Größe und Status: ✔ gespeichert · ⟳ neuer Datenstand verfügbar.
- Häkchen = Land soll offline verfügbar sein (Auswahl wird gemerkt).
- Button **„Ausgewählte laden (≈ X MB)“** (zeigt nur die noch fehlende Menge; „✔ Ausgewählte Länder sind
  gespeichert“ wenn nichts fehlt; „Länder auswählen“ wenn nichts gewählt). Ab 300 MB Rückfrage („am besten im WLAN“).
- Häkchen entfernen → nach Rückfrage die gespeicherten Daten des Landes löschen (Kacheln, die auch zu einem
  noch gewählten Land gehören, bleiben). „Ganz Europa“ abwählen → alle löschen (Rückfrage).
- Hinweistext zur Bedeutung der Häkchen und Symbole; Datenstand „Schnell-Daten für 47 Länder (Stand …)“;
  Speicheranzeige „Im Browser gespeichert: N Kacheln, ca. X MB“; Button „Alle gespeicherten Daten löschen“.
- Vorladen läuft über die Block-Dateien (4 parallel). Fortschritt unten: „Vorladen: 40 % (3 von 8)“ mit
  „Abbrechen“; bei Fehler „Vorladen angehalten …“ mit „Fortsetzen“/„Abbrechen“; am Ende
  „✔ Vorladen fertig – das Gebiet ist jetzt gespeichert“. Hat der sichtbare Ausschnitt Vorrang: „– pausiert“.
- KEIN „Umgebung vorladen“ mit Kilometer-Auswahl (wurde bewusst entfernt).

## 10. Angebot „Land offline speichern?“

- Zeigt die Karte (ab Zoom 9) ein aufbereitetes Land, das **nicht** offline gewählt ist und für das noch
  Daten fehlen, erscheint unten ein Kasten:
  „📥 Für **Österreich** sind noch keine Offline-Daten gespeichert. Jetzt für die Offline-Nutzung herunterladen? **(≈ 20 MB)**“
  mit [Ja, herunterladen] [Später] und Link „Für Österreich nicht mehr fragen“.
- Land bestimmen: Block in der Kartenmitte zählt 3-fach, die 8 Nachbarblöcke 1-fach; Land mit den meisten
  Stimmen (an Grenzen das Land, das den Ausschnitt überwiegend füllt).
- **Ja:** Land in den Einstellungen dauerhaft anhaken und sofort laden (läuft schon ein Download, danach).
- **Später:** in dieser Sitzung für dieses Land nicht mehr fragen. Ebenso nach bewusstem Abwählen im Menü.
- **Nicht mehr fragen:** dauerhaft gemerkt; wird zurückgesetzt, wenn man das Land selbst anhakt.
- Nur wenn dauerhafter Speicher (IndexedDB) verfügbar ist.

## 10a. Routing (Start, Zwischenziele, Ziel)

**Dienst:** BRouter (`https://brouter.de/brouter`, frei, erlaubt Browser-Zugriffe/CORS). Eigenes Profil
„Gravelfinder Big Enduro“ steht in `index.html` als `<script type="text/plain" id="brouterProfile">` und wird
einmal je Sitzung per `POST https://brouter.de/brouter/profile` hochgeladen (Antwort `{ profileid: "custom_…" }`;
läuft das Profil auf dem Server ab, automatisch neu hochladen). Routenabfrage:
`GET …/brouter?lonlats=lon,lat|lon,lat|…&profile=<id>&alternativeidx=0&format=geojson&profile:gravel_pref=<1–5>`.

**Profil (BRouter-Profilsprache):**
- Zugang wie die Karte (genauester Schlüssel motorcycle → motor_vehicle → vehicle → access); gesperrt = Kosten 10000.
- Schotterweg = gleicher Filter wie die Karte; Qualitätsstufe wie die Karte (smoothness vor schlechterer von tracktype/surface).
- Kosten je Meter: Schotter hoch 1,0 · mittel 1,15 · niedrig 1,7.
  Straßen = Grundkosten × `gravel_pref` (Standard 3): tertiary/unclassified 1,0 · secondary 1,15 · primary 1,3 ·
  residential 1,2 · service 1,3 · trunk 2,0 · Feldweg ohne Angaben 1,6 · Fähre 2,0; Autobahn und Fuß-/Radwege gesperrt.
- Knoten: Poller/Drängelgitter/Steinblock/Drehkreuz gesperrt (außer Zugang erlaubt), Schranke (`lift_gate`) +3000,
  Tor (`gate`) +800 – Forststraßen-Schranken sind oft geschlossen.
- Auswirkung (Test Wels → Ried): Vorliebe 2 → 10 % Schotter, 3 → 26 %.

**Bedienung:** Menüpunkt „🧭 Route“ (zwischen POI und Offline Karten) und Schnellknopf 🧭 oben links unter der Kartenauswahl.
- „Punkte auf der Karte setzen“ (Routen-Modus): Tippen setzt Punkte – erster = Start, jeder weitere = neues Ziel,
  das bisherige Ziel wird Zwischenziel. Hinweis-Leiste unten „Tippe auf die Karte …“ mit „Fertig“. Im Routen-Modus
  sind Wege nicht antippbar (Wege-Ebene `pointer-events: none`), POIs schon.
- Punkte als runde Nadeln S (grün), 1, 2 … (blau), Z (rot); mit dem Finger verschiebbar; Popup „Punkt entfernen“.
- Liste im Menü mit ↑ ↓ ✕; Knöpfe „📍 Mein Standort als Start“, „⇅ Umkehren“, „🗑 Löschen“.
- POI-Popup: „➕ Zur Route hinzufügen“ (wird neues Ziel, mit Namen).
- **Route ziehen:** Linie anfassen (linke Maustaste / Finger halten) und ziehen → gestrichelte Vorschau vom vorigen
  Wegpunkt über den Zeiger zum nächsten folgt dem Zeiger; beim Loslassen entsteht dort ein neues Zwischenziel
  **zwischen den beiden Wegpunkten dieses Abschnitts**, dann Neuberechnung (während des Ziehens keine Server-Anfragen).
  Umsetzung: unsichtbare, 24 px breite Greif-Linie (SVG-Renderer, eigene Pane zIndex 495) mit `pointerdown`,
  danach `pointermove`/`pointerup` am Dokument (Maus und Touch), Kartenverschieben währenddessen aus. Abschnitt =
  Wegpunkte der Reihe nach der nächstgelegenen Geometrie-Stelle zugeordnet. Nur Antippen (< 6 px) fügt nichts ein.
- WICHTIG: Panes mit Zeichenflächen über der Karte (Routenpunkte, Greif-Linie, Standort) brauchen
  `pointer-events: none` – sonst fangen leere Canvas/SVG-Flächen alle Klicks ab; Marker und Greif-Linie bekommen
  ihre Klick-Freigabe einzeln.
- Schieberegler „Schotter-Vorliebe“ 1–5 (gering … maximal, Standard 3 „stark“).
- Route und Vorliebe werden gespeichert (überstehen Neuladen).

**Linienstärke:** Schieber „Linienstärke der Route“ im Tab Route, 2–10 px (Standard 4 px), weißer Rand = Stärke + 4 px.
**Transparenz:** senkrechter Schieber „Transparenz für angezeigte Route“ als Kartensteuerung in der **linken
Knopfleiste direkt unter dem 🧭-Knopf** (44 px breit wie die Knöpfe) – dort verdeckt ihn das Menü nie (rechts wurde er
vom ausgeklappten Menü verdeckt). 0–90 %, oben = durchsichtiger; nur sichtbar, solange eine Route angezeigt wird; wirkt auf die ganze Routen-Pane (CSS-Opacity),
damit der weiße Rand nicht durch die Farbe scheint. Beides wird gespeichert.

**Anzeige:** Route mit weißem Rand, darüber Abschnitte in den Stufenfarben, Straße blau #2f6fdf;
eigene Pane über Wegen und Ortsnamen, unter POIs, klickdurchlässig. Abschnitte aus `messages` (je Zeile Endpunkt +
`WayTags`). Ergebnis: Länge, geschätzte Fahrzeit (Schotter 35/28/18 km/h je Stufe, Straßen nach Typ 15–80 km/h),
Anstieg (`filtered ascend`), Farbbalken und Anteile hoch/mittel/niedrig/Straße, „🔍 Ganze Route zeigen“,
„⬇ GPX speichern“ (GPX 1.1: Wegpunkte Start/Zwischenziele/Ziel + Track mit Höhen). Zusammenfassung im Menü
„41 km · 20 % Schotter“. Fehler verständlich („Keine Route gefunden …“, „Routing-Server nicht erreichbar“).

**Grenzen:** Routing braucht Internet; brouter.de ist ein freiwillig betriebener Server (für normale Nutzung ok).

## 10c. Eigene GPX-Tracks

- Menüpunkt „📂 GPX-Tracks“ (zwischen Route und Offline Karten): Knopf „📂 GPX-Datei laden …“ (Dateiauswahl, mehrere Dateien).
- Einlesen mit `DOMParser`: alle `trkseg/trkpt` und `rte/rtept` als eigene Abschnitte (mehrere Tracks/Abschnitte je
  Datei); Name aus `metadata/name`, sonst `trk/name`, sonst Dateiname; Länge in km; Wegpunkte werden gezählt, nicht gezeigt.
- Darstellung je Track: weißer Rand + Linie in frei wählbarer Farbe (Farbfeld), **Linienstärke 1–10 px**,
  **Transparenz 0–90 % (Schieber)**, Häkchen ein/aus, 🔍 ganz zeigen, ✕ entfernen. Eigene Pane über den
  Schotterwegen (zIndex 470), unter Ortsnamen und Route, klickdurchlässig. Nach dem Laden auf den Track zoomen.
- Tracks samt Einstellungen in IndexedDB (Tabelle `gpx`, Datenbank-Version 3) – bleiben nach dem Neuladen erhalten.
- Test: TET Croatia (3 Tracks HR-01/02/03, 9.883 Punkte, 757 KB) → 494 km, 3 Abschnitte, Einlesen 0,2 s.
- Hinweis: TET-GPX unterliegen den Bedingungen von transeurotrail.org – nicht in das öffentliche GitHub-Projekt hochladen.

## 10b. Hinweis „Aktuellere Offline-Daten verfügbar“

- Beim Start (nachdem Browser-Speicher und `index.json` gelesen sind) prüfen: Gibt es bei **angehakten** Ländern
  gespeicherte Kacheln, die älter als der Datenstand (`built`) sind oder ein altes Speicherformat (v) haben?
- Dann unten (über dem Statusfeld) ein Kasten:
  „🔄 **Aktuellere Offline-Daten verfügbar** (Stand 21.10.2026). Alle angehakten Länder jetzt aktualisieren?
  Deutschland, Österreich **(≈ 105 MB)**“ mit [Jetzt aktualisieren] [Später]. Bei mehr als 4 Ländern:
  „A, B, C und N weitere“. Größe = Anteil der veralteten Kacheln an der Landesgröße.
- **Jetzt aktualisieren:** alle angehakten Länder neu laden – dabei ohne die sonst übliche 1-Tag-Schonfrist
  (`strictFresh`), ohne zusätzliche Rückfrage; Fortschritt wie beim Vorladen. Danach ✔.
- **Später:** in dieser Sitzung nicht mehr fragen (beim nächsten Öffnen wieder).
- Solange der Kasten sichtbar ist, wird das Angebot „Land offline speichern?“ zurückgestellt (nie zwei Fragen übereinander).
- Test: Datenstand der gespeicherten Blöcke künstlich auf „alt“ setzen → Hinweis erscheint; Deutschland
  (882 Blöcke, 86 MB) in ca. 24 s aktualisiert; danach kein Hinweis mehr.

## 11. Herausgezoomt (unter Zoom 9)

- Keine Wege/Orte, Hinweis „🔍 Bitte weiter hineinzoomen · grün = offline gespeichert“.
- **Offline gespeicherte Länder grün einfärben** (eigene Pane unter den Wegen):
  vollständig = Rand #1b5e20, Füllung #43a047 mit 35 %; teilweise = 15 % und gestrichelter Rand.
- Umrisse aus `outlines.json`; fehlt die Datei, ersatzweise die Blöcke des Landes als randlose Rechtecke.
- Antippen: Popup „Österreich · ✔ offline gespeichert (20 MB)“ mit Link „Hier hineinzoomen“ (→ Zoom 12 an dieser Stelle).

## 12. Bedienung am Handy

- `viewport` ohne Zoomen der Seite, große Buttons (Zoom-Buttons 44 px), Statusleiste und Hinweise unten mittig
  als runde „Pillen“, max. Bildschirmbreite − 32 px.
- Menü einklappbar, Akkordeon-Abschnitte. Alle Bedienelemente leiten Klicks nicht an die Karte weiter.
- **Installierbar (PWA):** `manifest.webmanifest` (`display: standalone`, `orientation: any`, `start_url`/`scope` `./`,
  Farbe #22313a, Symbole 192/512 + maskierbar 512), `<link rel="manifest">`, `theme-color`, `apple-touch-icon`.
  `sw.js` nur über http(s) registrieren: App-Dateien „zuerst Netz, sonst Speicher“, Leaflet von unpkg „zuerst Speicher“;
  Kacheln, `data/…`, Overpass und BRouter **nicht** abfangen.
- **Querformat** (`orientation: landscape` und Höhe ≤ 520 px):
  - Menü = Spalte rechts über die volle Höhe (330 px, max. 45 % Breite), Inhalt scrollt darin.
  - „Mein Standort“ als runder Symbolknopf unten rechts (über Maßstab/Quellenangabe), nicht über den Hinweisen.
  - Routen-Transparenz-Schieber **waagrecht** oben neben der linken Knopfleiste statt senkrecht darunter.
  - Hinweise unten mittig mit Platz für die Knöpfe; bei offenem Menü in die freie linke Kartenhälfte gerückt.

---

## 13. Datenaufbereitung (build/build_tiles.py)

Läuft auf GitHub Actions (Ubuntu, Python 3.12, `osmium-tool` per apt, `pyosmium` und `shapely` per pip).

Je Land aus `regions.json` (nur `"active": true`; Option `--only id1,id2` zum Testen):
1. `https://download.geofabrik.de/europe/<id>-latest.osm.pbf` laden (3 Versuche, eigener User-Agent).
2. Vorfiltern: `osmium tags-filter` mit
   `w/highway=track,residential,service,tertiary,unclassified`, `nwr/amenity=…`, `nwr/shop=…`, `nwr/tourism=…`,
   `n/place=city,town,village` (Ortsnamen; `index.json` bekommt `places: 1`)
   (Option `--skip-prefilter` für kleine Testländer ohne osmium-tool). Original löschen (Platz!).
3. Mit pyosmium (`SimpleHandler`, `locations=True`) genau nach den App-Regeln filtern: `node` (POI-Punkte),
   `way` (Schotterwege), `area` (POI-Flächen → Mittelpunkt der Außenringe, Typ w/r mit Original-ID).
4. Linien mit **Douglas-Peucker 3 m** vereinfachen (lokale Meter-Projektion, shapely `simplify`); Kachel-Zuordnung
   mit allen Original-Punkten. Polyline-Kodierung (5 Nachkommastellen).
5. Je Block eine `.json.gz` schreiben (gzip Stufe 9); gemeinsame Grenz-Blöcke mit vorhandenen Dateien
   zusammenführen (Wege/Orte nach ID entdoppeln). Ein Land mit Fehler wird übersprungen und am Ende gemeldet.
6. Grenzlinie `https://download.geofabrik.de/europe/<id>.poly` lesen (Abschnitte mit `!` = Löcher).

Am Ende:
- **Abdeckung** aus der Vereinigung ALLER Ländergrenzen berechnen (Kachel vollständig enthalten → Bit setzen),
  damit Kacheln auf Grenzen zwischen zwei aufbereiteten Ländern als vollständig gelten.
- Größe je Land (Summe der komprimierten Blöcke, in denen es Daten hat) und Gesamtgröße in `index.json`.
- `outlines.json`: GeoJSON der Ländergrenzen, vereinfacht mit 0,01° und auf 3 Nachkommastellen gerundet.
- Ausgabe: Länder, Dateien, MB, Dauer, größte Länder, übersprungene Länder.
- **Abbruch**, wenn mehr als 95 % von 1 GB (Grenze von GitHub Pages) – dann bleibt die alte Version online.

Ergebnis Oktober 2026: 47 Länder, ca. 31.600 Blöcke, **355 MB**, ca. 92 Minuten.
Größte Länder: Deutschland 82 MB, Frankreich 37, Italien 32, Spanien 29, Polen 21, Österreich 20 MB.

### regions.json
Alle Länder Europas von Geofabrik (`europe/…`), aktiv:
albania, andorra, austria, azores, belarus, belgium, bosnia-herzegovina, bulgaria, croatia, cyprus,
czech-republic, denmark, estonia, faroe-islands, finland, france, germany, great-britain, greece,
guernsey-jersey, hungary, iceland, ireland-and-northern-ireland, isle-of-man, italy, kosovo, latvia,
liechtenstein, lithuania, luxembourg, macedonia, malta, moldova, monaco, montenegro, netherlands, norway,
poland, portugal, romania, serbia, slovakia, slovenia, spain, sweden, switzerland, ukraine –
jeweils mit deutschem Namen. Ausgeschaltet: turkey, georgia (großteils Asien). Russland fehlt bei Geofabrik unter Europa.

## 14. Ablauf auf GitHub (.github/workflows/daten.yml)

- Auslöser: **jeden Montag 02:00 UTC**, von Hand („Run workflow“, optional nur bestimmte Länder),
  bei Push auf `main` von index.html, manifest.webmanifest, sw.js, *.png, regions.json, build/** oder der Workflow-Datei.
- Rechte: contents read, pages write, id-token write; `concurrency: pages` ohne Abbruch laufender Läufe.
- Neu aufbereiten bei Zeitplan, Start von Hand und Änderungen an regions.json/build/ (nicht bei Änderung nur der Workflow-Datei).
  Bei reiner App-Änderung die letzten Daten aus dem Actions-Cache (`kartendaten-v2-…`) wiederverwenden (ca. 1 Minute).
- Vor dem Aufbereiten Speicherplatz schaffen (dotnet, android, ghc, CodeQL, boost löschen – Deutschland/Frankreich > 4 GB).
- Danach: Daten im Cache sichern, `index.html`, die App-Dateien (Manifest, sw.js, Symbole; fehlende nur melden) und `.nojekyll` dazulegen, `actions/upload-pages-artifact@v3`,
  Job `deploy` mit `actions/deploy-pages@v4`. Zeitlimit 360 Minuten.

## 15. Einrichtung und Betrieb

- GitHub-Konto **bigendurogravelfinder**, öffentliches Repository **gravelfinder**,
  Settings → Pages → Source „GitHub Actions“. App: `https://bigendurogravelfinder.github.io/gravelfinder/`.
- Dateien über die Weboberfläche hochladen („Add file → Upload files“). ACHTUNG: Ordner mit Punkt
  (`.github`) werden dabei nicht mit hochgeladen – die Workflow-Datei über „Create new file“ bzw.
  Stift-Symbol anlegen/bearbeiten und den Inhalt einfügen. Doppelte Läufe nach mehreren Commits abbrechen.
- Die App funktioniert auch auf jedem anderen Webspace (nur `index.html` hochladen); für „Mein Standort“ ist `https://` nötig.
  Gespeicherte Offline-Daten gelten jeweils nur für die Adresse, unter der die App geöffnet wurde.
- Lizenz: Kartendaten © OpenStreetMap-Mitwirkende, ODbL.

## 16. Bekannte Stolpersteine (unbedingt beachten)

- `tile.openstreetmap.org` sperrt file:// (kein Referer) → `tile.openstreetmap.de` verwenden.
- Overpass ist oft überlastet (Wartezeiten 30–60 s, Fehlerseiten ohne CORS) → Wiederholungen und fertige Daten.
- Overpass lehnt Skript-Clients (PowerShell o. ä.) teils mit 406 ab – im Browser testen.
- GitHub Pages: max. 1 GB → Vereinfachung + gzip; Größe im Skript prüfen.
- Leaflet-Canvas einer oberen Pane fängt alle Klicks → `pointer-events: none` für die Standort-Pane.
- `<div hidden>` mit `display:flex` wird trotzdem angezeigt → `[hidden] { display: none }` ergänzen.
- Beim Ändern nur des `#…` in der Adresszeile lädt der Browser die Seite nicht neu.
- Versteckte/eingebettete Browser-Vorschauen haben Fenstergröße 0 oder keinen Speicher → Tests mit echter Fenstergröße.

## 17. Tests, die bestanden sein müssen

- Ausschnitt Wels (Zoom 12): Schotterwege und Tankstellen erscheinen; aus fertigen Daten in < 1 s, ohne Overpass.
- München und Grenze Salzburg/Freilassing: Daten ohne Overpass.
- Ein Land ankreuzen → „Ausgewählte laden“ → ✔; abwählen → Daten gelöscht; Auswahl übersteht Neuladen.
- Ganz Österreich vorladen: ca. 13 s über das Internet.
- Angebot erscheint für ein nicht gespeichertes Land; „Ja“ hakt das Land an und lädt; „Später“ fragt nicht erneut.
- Herauszoomen: gespeicherte Länder grün, Popup mit „Hier hineinzoomen“.
- Nach Freigabe des Standorts lassen sich Wege und Orte weiterhin antippen.
- Erster Start: Grün/Gelb/Rot nach Qualität, 2 px, nur Tankstellen, alles eingeklappt.
- Qualität: Stufe ausblenden senkt den Zähler; Farbe ändern wirkt sofort; Popup zeigt Stufe und Begründung.
- Zoom 10 und 9: Wege als dünne Übersicht sichtbar, flüssiges Verschieben, keine Orte; unter 9 grüne Länder.
- Ortsnamen gut lesbar über den Linien (Zoom 10: Städte/Märkte, Zoom 12: auch Dörfer); Klicks gehen durch die Namen.
- Außerhalb Europas (oder ohne fertige Daten): Laden über Overpass mit Wiederholung und Fehlermeldung.
