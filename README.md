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
hide_empty: true       # zalen zonder evenementen verbergen (today/tomorrow, standaard true)
sort: time             # time (standaard) of zalen
show_schedule: true    # tijdschema onder elk evenement (alleen bij today, standaard true)
show_tickets: true     # kaartverkoop onder elk evenement (standaard true)
show_fields: true      # eigen velden onder elk evenement (standaard true)
fields:                # optioneel: alleen deze eigen velden tonen (keywords)
  - mijn_keyword
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

Per zaal toont de kaart een tegel met de agenda: tijden, naam, profiel en status
(Bevestigd/Optie/Voorlopig) per evenement. Afgelopen items worden gedimd.

**Tijdschema (alleen `today`):** onder elk evenement staat het tijdschema uit Yesplan, bijvoorbeeld
`10:00–14:00 Rehearsal`, `12:30–13:00 lunch` en `18:00 Zaal dicht`. Yesplan levert "(start)" en "(stop)" als
aparte regels; die worden samengevoegd tot één rij met begin- en eindtijd. Zet `show_schedule: false` om het te verbergen.

**Volgorde:** evenementen staan binnen een zaal altijd op tijd. De zalen zelf staan op de
eerste starttijd, dus de zaal waar het eerst iets begint staat bovenaan (bij gelijke tijd
geldt de volgorde uit `zalen`). Wil je liever vaste volgorde zoals je die onder `zalen` hebt gezet, gebruik dan:

```yaml
sort: zalen
```

- **`today` en `tomorrow`:** één tegel per zaal.
- **`week`:** per dag een sectie (maandag t/m zondag, de dag van vandaag gemarkeerd), met daarin per zaal een tegel,
  ook weer op eerste starttijd. Dagen zonder evenementen worden overgeslagen. `hide_empty` is hier niet van toepassing.

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

## Kaartverkoop

De integratie kan de kaartverkoop meenemen. Die staat in Yesplan in aangepaste velden (custom data), en de namen
daarvan verschillen per installatie, dus ze staan standaard **uit**.

Zet het aan via **Configureren** bij de integratie en vul de veldnamen (keywords) in:

| Optie | Voorbeeld | |
|---|---|---|
| Kaartverkoop: veld voor capaciteit | `evenement_activetickets_capaciteit` | verplicht |
| Kaartverkoop: veld voor verkocht | `activetickets_soldnetto` | optioneel |
| Kaartverkoop: veld voor beschikbaar | `evenement_activetickets_beschikbaar` | optioneel; zonder dit veld wordt het berekend (capaciteit min verkocht) |

Laat alles leeg om het uit te zetten. Zonder capaciteitsveld wordt er niets opgehaald.

De velden worden bij de bestaande dagaanvraag meegevraagd (`customdata_keywords`), dus dit kost **geen extra aanvragen**.
Weigert Yesplan de velden, dan staat er een waarschuwing in het logboek en blijft de agenda gewoon werken, zonder kaartverkoop.

Het resultaat staat per evenement in het attribuut `events` van de sensors, als `tickets` met `capacity`, `sold` en `available`:

```yaml
tickets:
  capacity: 144
  sold: 112
  available: 32
```

Evenementen zonder capaciteit (geen kaartverkoop) hebben geen `tickets`. De kaart toont onder elk evenement een regel
zoals `112 / 144 verkocht · 32 vrij` met een balkje; bij een uitverkochte voorstelling staat er "Uitverkocht".
Zet `show_tickets: false` om dat te verbergen.

Controleren of Yesplan de velden meegeeft (vervang de gegevens):

```bash
curl -s "https://JOUW.yesplan.nl/api/events/date:$(date +%d-%m-%Y)?customdata_keywords=evenement_activetickets_capaciteit,activetickets_soldnetto&api_key=JOUWKEY" | jq '.data[0].customdata'
```

## Eigen velden (custom data)

Naast de kaartverkoop kun je zelf **elk aangepast veld uit Yesplan** laten ophalen, bijvoorbeeld een opmerking,
een leeftijdsadvies of een technische omschrijving.

1. Zoek het keyword van het veld op in Yesplan (de interne naam, bijvoorbeeld `info_leeftijd`).
2. Ga naar **Configureren** bij de integratie en voeg het keyword toe bij **Eigen velden (keywords)**.
   Je kunt er maximaal 20 toevoegen. Komma's en spaties worden opgeschoond.
3. Bij het opslaan controleert de integratie of Yesplan de namen accepteert. Weigert Yesplan er een, dan blijft het
   formulier open en staat erbij welk veld het is.

Ze worden meegevraagd bij dezelfde dagaanvraag als de kaartverkoop, dus ook dit kost **geen extra aanvragen**.
Verschijnt er niets? Dan heeft het veld voor dat evenement geen waarde (lege velden worden overgeslagen), of de naam
klopt niet; controleer hem met het `curl`-commando bij Kaartverkoop.

In het attribuut `events` heeft elk evenement dan `custom`, met per veld het keyword, de naam die Yesplan eraan geeft
en de waarde als tekst:

```yaml
custom:
  - keyword: info_leeftijd
    name: Leeftijd
    value: 6+
```

Alle soorten velden werken: tekst, getal, ja/nee, keuzelijst, datum, en bij een contact- of resourceveld de naam.
Een lijst (bijvoorbeeld checkboxes) wordt samengevoegd tot één tekst met komma's. In een sjabloon of automatisering
(bijvoorbeeld als meldingstekst) geeft dit per evenement en veld één regel:

```yaml
{% for e in state_attr('sensor.grote_zaal_events_today', 'events') or [] %}
  {% for f in e.custom | default([]) %}
    {{ e.name }}: {{ f.name }} = {{ f.value }}
  {% endfor %}
{% endfor %}
```

Op de kaart staat elk veld onder het evenement, als naam en waarde in twee kolommen. Wil je op één kaart maar een deel
tonen, gebruik dan `fields` met de keywords. Met `show_fields: false` verberg je ze.

## Werking en beperkingen

- De Yesplan-API ondersteunt geen datumbereik, dus er is **één aanvraag per dag**. Per verversing worden
  vandaag t/m zondag opgehaald (minimaal tot morgen, of zoveel dagen als je bij "dagen vooruit" instelt).
  Daarbovenop komt één aanvraag per evenement van vandaag voor het tijdschema (maximaal 5 tegelijk; mislukt er één,
  dan blijft het laatst bekende tijdschema staan).
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
