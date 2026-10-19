# Yesplan voor Home Assistant

Custom integration (via HACS) die evenementen uit [Yesplan](https://www.yesplan.be)
ophaalt en per zaal sensors aanmaakt, bedoeld voor automatiseringen
(verwarming, licht, meldingen, ...).

> Niet gelieerd aan of goedgekeurd door Yesplan. Gebruik van de API valt onder
> de gebruiksvoorwaarden van Yesplan.

## Installatie

1. HACS → ⋮ → **Aangepaste repositories** → voeg de URL van deze repository toe, categorie **Integratie**.
2. Installeer **Yesplan** en herstart Home Assistant.
3. **Instellingen → Apparaten & services → Integratie toevoegen → Yesplan**.
4. Vul het adres (`https://jouwtheater.yesplan.nl`) en je API key in.
5. Kies de zalen uit de lijst die Yesplan teruggeeft, het aantal dagen vooruit en het ververs-interval.

Zalen, dagen en interval kun je later wijzigen via **Configureren** bij de integratie.

## Entiteiten (per zaal een apparaat)

| Entiteit | Voorbeeld | Beschrijving |
|---|---|---|
| Sensor **Volgende start** | `sensor.grote_zaal_volgende_start` | Tijdstip (timestamp) van het eerstvolgende evenement dat nog niet is begonnen. Attributen: `name`, `end`, `status`, `profile`. |
| Sensor **Voorstellingen vandaag** | `sensor.grote_zaal_voorstellingen_vandaag` | Aantal evenementen dat vandaag begint; attribuut `events` met de lijst. |
| Binary sensor **Bezet** | `binary_sensor.grote_zaal_bezet` | `on` zolang er een evenement bezig is. Attributen: `name`, `end`. |

De entiteit-ID's volgen de zaalnaam; controleer ze onder Ontwikkelaarstools → Statussen.

**Tijden:** de voorstellingstijd is `defaultschedulestart`/`defaultscheduleend`.
Ontbreken die, dan wordt de start- of eindtijd van de boeking gebruikt. Geannuleerde evenementen worden genegeerd.

## Dashboardkaart

De integratie levert een eigen kaart mee en laadt die automatisch; je hoeft geen resource toe te voegen.
Na het installeren of updaten één keer de browser hard verversen (Ctrl+F5) en bij de mobiele app
de cache wissen of de app herstarten.

Voeg toe via **Dashboard bewerken → Kaart toevoegen → Handmatig**:

```yaml
type: custom:yesplan-card
title: Dagplanning
zalen:                 # optioneel: volgorde en selectie
  - De Nieuwe Vorst
  - Grote zaal
  - Kleine zaal
  - Leesstudio
  - Rode salon
  - Balkonkamer
hide_empty: true       # zalen zonder evenementen verbergen (standaard true)
show_profile: true     # profiel onder de titel tonen (standaard true)
```

Per zaal toont de kaart:

- **Bezet / Vrij** als badge, met een gekleurde rand zodra er iets bezig is
- **Nu bezig**: naam en eindtijd van het lopende evenement
- **Volgende**: naam, starttijd en hoe lang het nog duurt (op een andere dag met datum)
- **Agenda van vandaag**: tijden, naam, profiel en status (Bevestigd/Optie/Voorlopig) per evenement; afgelopen items worden gedimd, het lopende item is vet

Zonder `zalen` worden alle zalen van de integratie getoond, alfabetisch. De kleuren volgen je thema.

Past de kaart de zaalnaam niet automatisch aan? De kaart zoekt de entiteiten via het apparaat van de integratie, dus
hernoemde apparaten werken ook, mits `zalen` dezelfde naam gebruikt als het apparaat.

## Voorbeeldautomatiseringen

Een uur voor aanvang opwarmen. De `time`-trigger kan direct op een timestamp-sensor draaien:

```yaml
automation:
  - alias: "Grote zaal opwarmen"
    triggers:
      - trigger: time
        at: sensor.grote_zaal_volgende_start
        offset: "-01:00:00"
    actions:
      - action: climate.set_temperature
        target:
          entity_id: climate.JOUW_THERMOSTAAT
        data:
          temperature: 20

  - alias: "Grote zaal terug naar standby"
    triggers:
      - trigger: state
        entity_id: binary_sensor.grote_zaal_bezet
        to: "off"
        for: "00:15:00"
    actions:
      - action: climate.set_temperature
        target:
          entity_id: climate.JOUW_THERMOSTAAT
        data:
          temperature: 16
```

Let op: de tweede automatisering zet de temperatuur ook terug tussen twee voorstellingen op
dezelfde dag. Voeg eventueel een voorwaarde toe op de **Volgende start** (bijv. alleen terugzetten
als de volgende start meer dan 2 uur weg is).

## Werking en beperkingen

- De Yesplan-API ondersteunt geen datumbereik, dus er is **één aanvraag per dag** per verversing
  (standaard 3 dagen × elke 15 min). Houd het interval redelijk; Yesplan heeft rate limits.
- Start- en eindtijden worden elke minuut opnieuw beoordeeld zonder extra aanvragen.
- Alleen kerngegevens van het evenement (naam, tijden, status, profiel) worden opgehaald.
  Tijdschema's, resources en kaartverkoop zitten er niet in.

## Problemen oplossen

Zet logging aan in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.yesplan: debug
```

Vervang in `manifest.json` de `JOUW_GEBRUIKER`-links door je eigen GitHub-gegevens voordat je publiceert.
