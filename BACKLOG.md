# Backlog – Gravelfinder Big Enduro

Ideen und Verbesserungen, die bewusst auf später verschoben wurden.

## Routing

### Fahrzeit realistischer berechnen (vorgemerkt am 22.10.2026)
Die geschätzte Fahrzeit wirkt zu hoch. Heute: feste Geschwindigkeit je Abschnitt (Länge ÷ Tempo), ohne Pausen und Höhe.

| Abschnitt | heute | Vorschlag |
|---|---|---|
| Schotter hoch / mittel / niedrig | 35 / 28 / 18 km/h | 50 / 40 / 25 km/h |
| primary / secondary / tertiary / unclassified | 75 / 65 / 55 / 45 km/h | 85 / 75 / 65 / 55 km/h |
| residential / service | 30 / 20 km/h | 35 / 25 km/h |

Zusätzlich: Regler **Fahrstil** (gemütlich ×0,8 / normal ×1,0 / zügig ×1,2) im Tab „Route“, optional eigene
Geschwindigkeiten je Stufe. Beispiel Buchkirchen → Steinhaus (16 km): heute 24 min, mit Vorschlag ca. 17 min.
Code: `Q_SPEED` und `ROAD_SPEED` in `index.html`.

### Höhenprofil der Route
Höhendaten liefert BRouter schon mit (stehen auch im GPX) – fehlt nur die Anzeige.

### Profil nach Testfahrten feinjustieren
Schotter-Vorliebe, Kosten für rote Wege, Feldwege ohne Angaben/`grade4–5` ggf. ganz sperren, Schranken.

## GPX-Tracks
- Wegpunkte (`wpt`) aus GPX-Dateien auf der Karte anzeigen (werden derzeit nur gezählt).

## App
- ~~Installierbare Web-App (PWA) mit Querformat~~ – erledigt am 22.10.2026.
- **Android-App als APK:** ggf. als TWA bzw. echte App (Capacitor) mit GPS im Hintergrund / Streckenaufzeichnung.
- **Hintergrundkarte offline:** Kartenbild selbst ist noch nicht offline verfügbar (öffentliche Kartenserver
  verbieten Massen-Downloads) – bräuchte eigene Kartendaten.
