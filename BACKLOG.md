# Backlog – Gravelfinder Big Enduro

Ideen und Verbesserungen, die bewusst auf später verschoben wurden.

## Routing

### Fahrzeit realistischer berechnen (vorgemerkt am 22.10.2026)
Die geschätzte Fahrzeit wirkt zu hoch. Heute: feste Geschwindigkeit je Abschnitt (Länge ÷ Tempo), ohne Pausen und Höhe.

| Abschnitt | heute | Vorschlag |
|---|---|---|
| Offroad sehr gut / gut / mittel / schlecht / sehr schlecht | 35 / 28 / 18 / 12 / 7 km/h | 50 / 40 / 25 / 15 / 8 km/h |
| motorway / trunk | 110 / 80 km/h | 120 / 90 km/h |
| primary / secondary / tertiary / unclassified | 75 / 65 / 55 / 45 km/h | 85 / 75 / 65 / 55 km/h |
| residential / service | 30 / 20 km/h | 35 / 25 km/h |

Teilweise erledigt (23.10.2026): Jeder **Fahrzeugtyp** hat eigene Geschwindigkeiten je Stufe und einen Straßen-Faktor
(siehe PROMPT.md). Offen: die Werte nach Testfahrten anheben, Regler **Fahrstil** (gemütlich ×0,8 / normal ×1,0 /
zügig ×1,2), optional eigene Geschwindigkeiten bei „Eigenes“. Beispiel Buchkirchen → Steinhaus (16 km): heute 24 min, mit Vorschlag ca. 17 min.
Code: `Q_SPEED` und `ROAD_SPEED` in `index.html`.

### ~~Höhenprofil der Route~~ – erledigt am 23.10.2026
Im Route-Tab unter dem Ergebnis, mit Qualitäts-Streifen und Anzeige der Stelle auf der Karte.

### Profil nach Testfahrten feinjustieren
Heute (BRouter-Profil in `index.html`): Kosten je Meter nach Stufe 1,0 · 1,15 · 1,7 · 3,0 · 6,0; im Tab „Wege“
nicht angehakte Stufen ×30 (nur wenn es nicht anders geht); Straßen = Grundkosten × Schotter-Vorliebe;
Schranke +3000, Tor +800. Nach Testfahrten prüfen:
- Kostenabstufung der 5 Stufen und der Faktor ×30 für ausgeblendete Stufen,
- Feldwege ohne jede Angabe (`highway=track` ohne tracktype/surface, Kosten 1,6 × Vorliebe) – eher meiden?
- Schranken/Tore (oft geschlossen) – stärker meiden oder als eigene Vermeiden-Kachel,
- Schotter-Vorliebe-Regler (1–5) – passt die Skala?

## GPX-Tracks
- Wegpunkte (`wpt`) aus GPX-Dateien auf der Karte anzeigen (werden derzeit nur gezählt).

## App
- ~~Installierbare Web-App (PWA) mit Querformat~~ – erledigt am 22.10.2026.
- **Android-App als APK:** ggf. als TWA bzw. echte App (Capacitor) mit GPS im Hintergrund / Streckenaufzeichnung.
- **Hintergrundkarte offline:** Kartenbild selbst ist noch nicht offline verfügbar (öffentliche Kartenserver
  verbieten Massen-Downloads) – bräuchte eigene Kartendaten.
