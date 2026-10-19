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
