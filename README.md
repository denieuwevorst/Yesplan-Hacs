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
| Sensor **Voorstellingen morgen** | `sensor.grote_zaal_voorstellingen_morgen` | Hetzelfde voor morgen. |
| Sensor **Voorstellingen deze week** | `sensor.grote_zaal_voorstellingen_deze_week` | Evenementen in de kalenderweek (maandag t/m zondag) waarin we zitten. |
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
range: today           # today (standaard), tomorrow of week
hide_empty: true       # zalen zonder evenementen verbergen (standaard true)
show_profile: true     # profiel onder de titel tonen (standaard true)
```

Met `range` kies je de periode. Voeg gerust meerdere kaarten toe:

```yaml
type: custom:yesplan-card
title: Morgen
range: tomorrow
```

```yaml
type: custom:yesplan-card
title: Deze week
range: week
```

Per zaal toont de kaart:

- **Volgende** (alleen bij `today`): naam, starttijd en hoe lang het nog duurt
- **Agenda**: tijden, naam, profiel en status (Bevestigd/Optie/Voorlopig) per evenement; afgelopen items worden gedimd
- Bij `week`: de evenementen gegroepeerd per dag, met de dag van vandaag gemarkeerd. Dagen zonder evenementen worden overgeslagen

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

- De Yesplan-API ondersteunt geen datumbereik, dus er is **één aanvraag per dag**. Per verversing worden
  vandaag t/m zondag opgehaald (minimaal tot morgen, of zoveel dagen als je bij "dagen vooruit" instelt).
  Dagen eerder in de week veranderen zelden en worden maximaal één keer per uur opnieuw opgehaald.
  Houd het interval redelijk; Yesplan heeft rate limits.
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
