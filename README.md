# Gravelfinder Big Enduro

Karte mit fahrbaren Schotterwegen und nützlichen Orten (Tankstellen, Lebensmittel, …) für Big-Enduro-Fahrer.

- **App:** `index.html` – eine einzige Datei, läuft im Browser (Handy und PC).
- **Schnell-Daten:** Werden jede Woche automatisch auf GitHub aus OpenStreetMap aufbereitet
  und als kleine Dateien bereitgestellt. Die App lädt dadurch einen Ausschnitt in unter einer Sekunde.
- **Außerhalb der aufbereiteten Länder** lädt die App wie früher über den (langsamen) Overpass-Server.

Kartendaten © [OpenStreetMap-Mitwirkende](https://www.openstreetmap.org/copyright), Lizenz ODbL.

---

## Einrichtung (einmalig, ca. 15 Minuten)

### 1. GitHub-Konto anlegen
1. Auf <https://github.com/signup> ein kostenloses Konto anlegen.
2. Der **Benutzername** wird Teil der Adresse der App: `https://BENUTZERNAME.github.io/gravelfinder/`.
   Am besten kurz und ohne Sonderzeichen wählen.

### 2. Projekt („Repository“) anlegen
1. Oben rechts auf **+** → **New repository**.
2. **Repository name:** `gravelfinder`
3. **Public** auswählen (nötig, damit GitHub Pages kostenlos ist).
4. Sonst nichts ankreuzen → **Create repository**.

### 3. Dateien hochladen
1. Auf der neuen, leeren Projektseite auf den Link **uploading an existing file** klicken.
2. Im Windows-Explorer den Ordner `C:\ClaudeCode\GravelOverlay` öffnen, **alles markieren**
   (Strg + A – auch die Ordner `.github` und `build`) und in das Browserfenster ziehen.
3. Unten auf **Commit changes** klicken.

> GitHub startet jetzt sofort einen ersten Lauf. Der kann beim allerersten Mal mit einem Fehler
> enden, weil Schritt 4 noch fehlt – das ist normal.

### 4. Veröffentlichung einschalten
1. Im Projekt oben auf **Settings** → links **Pages**.
2. Bei **Source** „**GitHub Actions**“ auswählen.

### 5. Ersten Lauf starten
1. Oben auf **Actions** → links **Kartendaten aufbereiten** → rechts **Run workflow** → grüner Knopf **Run workflow**.
2. Dauer für Österreich, Slowenien und Kroatien: ca. 10–15 Minuten. Ein grüner Haken = fertig.
3. Die App ist dann erreichbar unter **`https://BENUTZERNAME.github.io/gravelfinder/`**
   – diese Adresse am Handy als Lesezeichen oder auf dem Startbildschirm speichern.

### 6. (Optional) App auch per Doppelklick oder vom eigenen Webspace nutzen
In `index.html` steht oben die Zeile

```
'https://bigendurogravelfinder.github.io/gravelfinder/data/v2/'
```

Damit findet die App die Schnell-Daten auch, wenn sie per Doppelklick oder von einem anderen Webspace
geöffnet wird (bei einem anderen GitHub-Konto den Benutzernamen dort ersetzen).

---

## Im Alltag

| Was | Wie |
|---|---|
| Daten aktualisieren | passiert automatisch jeden Montag früh |
| Sofort aktualisieren | Actions → Kartendaten aufbereiten → Run workflow |
| Land hinzufügen | Auf GitHub `regions.json` öffnen → Stift-Symbol → beim Land `"active": false` auf `true` ändern → Commit changes. Die Daten werden danach automatisch neu aufbereitet. |
| App ändern | neue `index.html` hochladen (Add file → Upload files). Die Daten werden dabei nicht neu aufbereitet, das dauert nur ca. 1 Minute. |
| Routing-Optionen | Menü → 🧭 Route → „🚧 Vermeiden & Routing-Optionen“: Autobahn, Schnellstraße, Maut, Fähre, Furten, schwierige Wege, Ortsgebiet, starke Steigungen. |
| Als App am Handy | `https://bigendurogravelfinder.github.io/gravelfinder/` in Chrome öffnen → Menü ⋮ → **App installieren** (oder in der App: Menü → Einstellungen → 📱 App → „Als App installieren“). Startet dann im Vollbild und dreht mit ins Querformat. Dort auch „Bildschirm wach halten“. |
| Fehler | GitHub schickt bei einem fehlgeschlagenen Lauf eine E-Mail. Unter Actions den roten Lauf öffnen – die Meldungen dort helfen bei der Fehlersuche. |

---

## Ganz Europa

`regions.json` enthält alle 47 Länder Europas (ohne Russland, Türkei und Georgien – lassen sich bei Bedarf
einschalten). Damit alles in die **1-GB-Grenze von GitHub Pages** passt:

- Linien werden vereinfacht (Punkte mit weniger als 3 m Abweichung entfallen – auf der Karte unsichtbar).
- Die Dateien liegen gzip-komprimiert auf dem Server; die App entpackt sie selbst.
- Das Skript bricht mit einer klaren Meldung ab, wenn die Daten trotzdem zu groß würden
  (dann bleibt die zuletzt veröffentlichte Version online).
- **Laufzeit:** ganz Europa ca. 2–4 Stunden je Lauf (GitHub erlaubt bis 6 Stunden, für öffentliche Projekte kostenlos).
- Ein Land mit Fehler (z. B. Download-Abbruch) wird übersprungen, der Rest wird trotzdem veröffentlicht.
  Welche Länder übersprungen wurden, steht am Ende des Protokolls unter „ÜBERSPRUNGEN“.

### Wenn es nicht mehr passt
Sollte Europa später über 1 GB wachsen, werden die Daten an einem anderen Ort abgelegt – App und Skript bleiben gleich,
nur das Ziel im Ablauf ändert sich:

1. **Cloudflare Pages / R2** (kostenlos, keine Kosten für Downloads).
2. **Eigener Webspace per FTP**, wenn dort genug Platz ist.

Bis dahin kann man in `regions.json` einzelne Länder ausschalten.

---

## Routing

Die App berechnet Routen über den freien Dienst **BRouter** (brouter.de) mit einem eigenen Profil, das grüne und
gelbe Schotterwege bevorzugt und Straßen als Verbindungsstücke nutzt. Das Profil steht direkt in `index.html`
(Block `brouterProfile`) und wird von der App automatisch hochgeladen. Routing braucht Internet; die fertige Route
lässt sich als GPX speichern (Garmin, OsmAnd, Kurviger …).

## Technik in Kürze

- `build/build_tiles.py` lädt je Land die Datei von <https://download.geofabrik.de>, filtert mit `osmium` vor,
  wählt mit den gleichen Regeln wie die App Schotterwege und Orte aus und schreibt sie je Block
  (4 × 4 Kacheln à 0,05° × 0,075°, ca. 22 × 22 km) als gzip-JSON nach `data/v2/blocks/<bi>/<bj>.json.gz`.
  Linien sind vereinfacht (3 m) und als Google-Polyline kodiert.
- `data/v2/index.json` sagt der App, welche Länder (mit Größe) und Blöcke es gibt und welche Kacheln
  vollständig im aufbereiteten Gebiet liegen. Kacheln am Rand (z. B. zur Türkei) ergänzt die App über Overpass.
- `.github/workflows/daten.yml` startet das Ganze wöchentlich und veröffentlicht App und Daten auf GitHub Pages.
- Lokaler Test (ohne osmium-tool, nur für kleine Länder):
  `python build/build_tiles.py --only liechtenstein --skip-prefilter`
