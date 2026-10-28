/* Yesplan card for Home Assistant — served by the Yesplan integration. */
(() => { /* wrapped */
// Version comes from the ?v= parameter the integration adds to this script's URL
// (taken from manifest.json), so it can never go out of sync with the integration.
const CARD_VERSION = (() => {
  const urls = [];
  try {
    document.querySelectorAll("script[src]").forEach((el) => urls.push(el.src));
  } catch (e) { /* ignore */ }
  try {
    performance.getEntriesByType("resource").forEach((r) => urls.push(r.name));
  } catch (e) { /* ignore */ }
  for (const u of urls.filter((x) => x.includes("yesplan-card.js")).reverse()) {
    try {
      const v = new URL(u, location.href).searchParams.get("v");
      if (v) return v;
    } catch (e) { /* ignore */ }
  }
  return "";
})();

const STR = {
  nl: {
    todayLbl: "vandaag", schedule: "Tijdschema",
    sold: "verkocht", free: "vrij", soldOut: "Uitverkocht", seats: "plaatsen",
    emptyToday: "Geen evenementen vandaag.", emptyTomorrow: "Geen evenementen morgen.",
    emptyWeek: "Geen evenementen deze week.",
    needUpdate: "De sensor voor deze periode ontbreekt. Werk de Yesplan-integratie bij en herstart Home Assistant.",
    noZones: "Geen zalen gevonden. Is de Yesplan-integratie ingesteld?",
    unavailable: "Niet beschikbaar",
  },
  en: {
    todayLbl: "today", schedule: "Schedule",
    sold: "sold", free: "free", soldOut: "Sold out", seats: "seats",
    emptyToday: "No events today.", emptyTomorrow: "No events tomorrow.",
    emptyWeek: "No events this week.",
    needUpdate: "The sensor for this period is missing. Update the Yesplan integration and restart Home Assistant.",
    noZones: "No locations found. Is the Yesplan integration set up?",
    unavailable: "Unavailable",
  },
};

const slug = (s) =>
  String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const RANGE_KEY = {
  today: "events_today",
  tomorrow: "events_tomorrow",
  week: "events_week",
};

const GUESS = {
  events_today: ["sensor", ["voorstellingen_vandaag", "events_today"]],
  events_tomorrow: ["sensor", ["voorstellingen_morgen", "events_tomorrow"]],
  events_week: ["sensor", ["voorstellingen_deze_week", "events_this_week"]],
};

const STYLE = `
  :host { display: block; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 12px; padding: 0 16px 16px; }
  .msg { padding: 16px; color: var(--secondary-text-color); }
  .zaal { min-width: 0; background: var(--secondary-background-color, rgba(127,127,127,.08));
          border-radius: var(--ha-card-border-radius, 12px); padding: 12px 14px;
          border-left: 4px solid var(--divider-color); }
  .head { display: flex; justify-content: space-between; align-items: center;
          gap: 8px; margin-bottom: 8px; }
  .name { font-weight: 600; font-size: 1.05em; }
  .list { margin-top: 6px; }
  .daysec { padding-bottom: 2px; }
  .daysec .grid { padding-bottom: 8px; }
  .dayhead { font-size: .8em; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
             color: var(--secondary-text-color); padding: 10px 16px 6px; }
  .dayhead.today { color: var(--primary-color); }
  .row {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
  align-items: start;
  padding: 7px 0;
  border-top: 1px solid var(--divider-color);
  position: relative;
}

.row .chip {
  justify-self: end;
  grid-row: 1;
}

.row > .time,
.row > div:nth-child(2) {
  grid-column: 1;
}

.row > .time {
  grid-row: 2;
}

.row > div:nth-child(2) {
  grid-row: 3;
}
  .row.past { opacity: .45; }
  .tix { margin-top: 6px; display: flex; align-items: center; gap: 8px; font-size: .85em; }
  .tix .bar { flex: 0 1 120px; min-width: 60px; height: 6px; border-radius: 3px;
              background: var(--divider-color); overflow: hidden; }
  .tix .fill { height: 100%; background: var(--primary-color); }
  .tix.full .fill { background: var(--success-color, #43a047); }
  .tix.full span { font-weight: 600; }
  .cust { margin-top: 6px; display: grid; grid-template-columns: auto minmax(0, 1fr);
          column-gap: 10px; row-gap: 1px; font-size: .85em; }
  .cust .cl { color: var(--secondary-text-color); }
  .cust .cv { overflow-wrap: anywhere; }
  .sched { margin-top: 8px; padding-left: 10px; border-left: 2px solid var(--divider-color);
           display: grid; grid-template-columns: auto minmax(0, 1fr); column-gap: 10px; row-gap: 2px;
           font-size: .85em; }
  .sched .cap { grid-column: 1 / -1; font-size: .8em; font-weight: 600; text-transform: uppercase;
                letter-spacing: .04em; color: var(--secondary-text-color); }
  .stime { font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }
  .slabel { overflow-wrap: anywhere; }
  .time { font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }
  .title { overflow-wrap: anywhere; }
  .row > div { min-width: 0; }
  .sub { font-size: .8em; color: var(--secondary-text-color); overflow-wrap: anywhere; }
  .chip { font-size: .7em; font-weight: 600; padding: 1px 8px; border-radius: 999px;
          border: 1px solid currentColor; color: var(--secondary-text-color);
          white-space: nowrap; }
  .chip.ok { color: var(--success-color, #43a047); }
  .chip.opt { color: var(--info-color, #039be5); }
  .chip.tent { color: var(--warning-color, #ffa600); }
  .none { font-size: .9em; color: var(--secondary-text-color); padding-top: 4px; }
`;

class YesplanCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = {
      hide_empty: true,
      show_profile: true,
      range: "today",
      sort: "time",
      show_schedule: true,
      show_tickets: true,
      show_fields: true,
      ...config,
    };

    if (!RANGE_KEY[this._config.range]) this._config.range = "today";
    if (!["time", "zalen"].includes(this._config.sort)) this._config.sort = "time";

    this._zoneCache = null;
    this._sig = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const sig = this._signature();

    if (sig !== this._sig) {
      this._sig = sig;
      this._render();
    }
  }

  connectedCallback() {
    // Relative times / past events change without any state change.
    this._timer = setInterval(() => this._render(), 60000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  getCardSize() {
    return 6;
  }

  // Home Assistant uses this editor in the visual card configuration dialog.
  static getConfigElement() {
    return document.createElement("yesplan-card-editor");
  }

  // A useful preview in the card picker, with a safe default range.
  static getStubConfig() {
    return {
      type: "custom:yesplan-card",
      title: "Yesplan vandaag",
      range: "today",
    };
  }

  get _s() {
    const lang = (this._hass && this._hass.language) || "nl";
    return STR[lang.startsWith("nl") ? "nl" : "en"];
  }

  get _lang() {
    return (this._hass && this._hass.language) || "nl";
  }

  get _tz() {
    return (this._hass && this._hass.config && this._hass.config.time_zone) || undefined;
  }

  _guess(name) {
    const ids = {};
    const s = slug(name);

    for (const [key, [domain, names]] of Object.entries(GUESS)) {
      const hit = names
        .map((n) => `${domain}.${s}_${n}`)
        .find((id) => this._hass.states[id]);

      if (hit) ids[key] = hit;
    }

    return ids;
  }

  _zones() {
    const h = this._hass;
    const c = this._zoneCache;

    if (c && c.ents === h.entities && c.devs === h.devices) return c.zones;

    const byDev = {};

    for (const [eid, ent] of Object.entries(h.entities || {})) {
      if (ent.platform !== "yesplan" || !ent.device_id) continue;

      const dev = (h.devices || {})[ent.device_id];
      const z = (byDev[ent.device_id] ||= {
        name: dev ? dev.name_by_user || dev.name : ent.device_id,
        ids: {},
      });

      if (ent.translation_key) z.ids[ent.translation_key] = eid;
    }

    let zones = Object.values(byDev);
    const order = (this._config.zalen || []).map((n) => String(n).toLowerCase());

    if (order.length) {
      if (!zones.length) {
        zones = this._config.zalen.map((name) => ({
          name,
          ids: this._guess(name),
        }));
      }

      zones = zones
        .filter((z) => order.includes(z.name.toLowerCase()))
        .sort((a, b) =>
          order.indexOf(a.name.toLowerCase()) - order.indexOf(b.name.toLowerCase())
        );
    } else {
      zones.sort((a, b) => a.name.localeCompare(b.name, this._lang));
    }

    this._zoneCache = { ents: h.entities, devs: h.devices, zones };
    return zones;
  }

  _signature() {
    if (!this._config || !this._hass) return "";

    const parts = [];

    for (const z of this._zones()) {
      const id = z.ids[RANGE_KEY[this._config.range]];
      const st = id ? this._hass.states[id] : undefined;
      parts.push(`${id}:${st ? st.last_updated : "-"}`);
    }

    return parts.join("|");
  }

  _fmtTime(iso) {
    if (!iso) return "";

    return new Date(iso).toLocaleTimeString(this._lang, {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: this._tz,
    });
  }

  _dayKey(d) {
    return new Date(d).toLocaleDateString("en-CA", { timeZone: this._tz });
  }

  _chip(status) {
    if (!status) return "";

    const k = status.toLowerCase();
    const cls = k.startsWith("bevestigd") || k === "confirmed" ? "ok"
      : k.startsWith("optie") || k === "option" ? "opt"
      : k.startsWith("voorlopig") || k === "tentative" ? "tent" : "";

    return `<span class="chip ${cls}">${esc(status)}</span>`;
  }

  // One zone's events for the selected range, always sorted by start time.
  _collect(z) {
    const id = z.ids[RANGE_KEY[this._config.range]];
    const ent = id ? this._hass.states[id] : undefined;
    const unavailable = !ent || ent.state === "unavailable";

    // An unavailable sensor must not show stale data.
    const events = unavailable
      ? []
      : [...((ent.attributes && ent.attributes.events) || [])]
          .sort((a, b) => new Date(a.start) - new Date(b.start));

    return { name: z.name, events, unavailable };
  }

  // Tiles with the earliest first start time come first. Ties (and sort: zalen)
  // keep the configured zone order.
  _order(items) {
    if (this._config.sort === "zalen") return items;

    const first = (x) =>
      (x.events.length ? new Date(x.events[0].start).getTime() : Infinity);

    return items
      .map((x, i) => [x, i])
      .sort((a, b) => first(a[0]) - first(b[0]) || a[1] - b[1])
      .map((x) => x[0]);
  }

  // Extra custom data fields (name | value); `fields: [keyword, ...]` limits which are shown.
  _fieldsHtml(rows) {
    if (!Array.isArray(rows) || !rows.length) return "";

    const only = Array.isArray(this._config.fields) ? this._config.fields : null;
    const shown = rows.filter((r) => r && r.value && (!only || only.includes(r.keyword)));

    if (!shown.length) return "";

    return `<div class="cust">${shown
      .map((r) =>
        `<span class="cl">${esc(r.name || r.keyword)}</span><span class="cv">${esc(r.value)}</span>`
      )
      .join("")}</div>`;
  }

  // Ticket sales: "112 / 144 verkocht · 32 vrij" with a bar; nothing for events without capacity.
  _ticketsHtml(t) {
    if (!t || !(t.capacity > 0)) return "";

    const s = this._s;
    const sold = Number.isFinite(t.sold) ? t.sold : null;
    const full = t.available === 0 || (sold !== null && sold >= t.capacity);
    const pct = sold === null ? 0 : Math.min(100, Math.round((sold / t.capacity) * 100));

    const text = sold === null
      ? `${t.capacity} ${s.seats}`
      : `${sold} / ${t.capacity} ${s.sold}` +
        (full ? ` · ${s.soldOut}` : Number.isFinite(t.available) ? ` · ${t.available} ${s.free}` : "");

    const bar = sold === null
      ? ""
      : `<div class="bar"><div class="fill" style="width:${pct}%"></div></div>`;

    return `<div class="tix${full ? " full" : ""}">${bar}<span>${esc(text)}</span></div>`;
  }

  // Schedule rows: "10:00–14:00 Rehearsal", single times for items like "Zaal dicht".
  _scheduleHtml(rows) {
    const cells = rows.map((r) =>
      `<span class="stime">${this._fmtTime(r.start)}${r.end ? `–${this._fmtTime(r.end)}` : ""}</span>` +
      `<span class="slabel">${esc(r.label)}</span>`
    ).join("");

    return `<div class="sched"><div class="cap">${this._s.schedule}</div>${cells}</div>`;
  }

  _rowHtml(e, now) {
    const end = e.end ? new Date(e.end) : null;
    const past = end ? end <= now : false;

    const profile = this._config.show_profile && e.profile
      ? `<div class="sub">${esc(e.profile)}</div>` : "";

    const showSchedule = this._config.range === "today"
      && this._config.show_schedule !== false
      && Array.isArray(e.schedule)
      && e.schedule.length;

    const schedule = showSchedule ? this._scheduleHtml(e.schedule) : "";
    const tickets = this._config.show_tickets !== false ? this._ticketsHtml(e.tickets) : "";
    const fields = this._config.show_fields !== false ? this._fieldsHtml(e.custom) : "";

    return `<div class="row ${past ? "past" : ""}">
  ${this._chip(e.status)}
  <div class="time">${this._fmtTime(e.start)}${e.end ? `–${this._fmtTime(e.end)}` : ""}</div>
  <div>
    <div class="title">${esc(e.name)}</div>
    ${profile}${tickets}${fields}${schedule}
  </div>
</div>`;
  }

  _tileHtml(name, events, emptyText) {
    const now = new Date();

    const list = events.length
      ? `<div class="list">${events.map((e) => this._rowHtml(e, now)).join("")}</div>`
      : `<div class="none">${emptyText}</div>`;

    return `<div class="zaal"><div class="head"><div class="name">${esc(name)}</div></div>${list}</div>`;
  }

  _emptyText() {
    const s = this._s;
    return {
      today: s.emptyToday,
      tomorrow: s.emptyTomorrow,
      week: s.emptyWeek,
    }[this._config.range];
  }

  // Today / tomorrow: one tile per zone.
  _dayHtml(items) {
    const s = this._s;
    const empty = this._emptyText();

    const shown = items.filter(
      (i) => !(this._config.hide_empty && !i.events.length && !i.unavailable)
    );

    if (!shown.length) return `<div class="msg">${empty}</div>`;

    return `<div class="grid">${this._order(shown)
      .map((i) =>
        this._tileHtml(i.name, i.events, i.unavailable ? s.unavailable : empty)
      )
      .join("")}</div>`;
  }

  // Week: one section per day (chronological); inside, one tile per zone.
  _weekHtml(items) {
    const s = this._s;
    const days = new Map();

    for (const info of items) {
      const byDay = new Map();

      for (const e of info.events) {
        const k = this._dayKey(e.start);
        if (!byDay.has(k)) byDay.set(k, []);
        byDay.get(k).push(e);
      }

      for (const [k, events] of byDay) {
        if (!days.has(k)) days.set(k, {
          key: k,
          first: events[0].start,
          tiles: [],
        });

        days.get(k).tiles.push({ name: info.name, events });
      }
    }

    if (!days.size) {
      return `<div class="msg">${items.every((i) => i.unavailable) ? s.unavailable : s.emptyWeek}</div>`;
    }

    const todayKey = this._dayKey(new Date());

    return [...days.values()]
      .sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0))
      .map((d) => {
        const label = new Date(d.first).toLocaleDateString(this._lang, {
          weekday: "long",
          day: "numeric",
          month: "long",
          timeZone: this._tz,
        });

        const isToday = d.key === todayKey;

        return `<section class="daysec">
          <div class="dayhead ${isToday ? "today" : ""}">${esc(label)}${isToday ? ` · ${s.todayLbl}` : ""}</div>
          <div class="grid">${this._order(d.tiles)
            .map((t) => this._tileHtml(t.name, t.events, ""))
            .join("")}</div>
        </section>`;
      })
      .join("");
  }

  _render() {
    if (!this._config || !this._hass) return;

    const s = this._s;
    const zones = this._zones();
    const key = RANGE_KEY[this._config.range];
    let body;

    if (!zones.length) {
      body = `<div class="msg">${s.noZones}</div>`;
    } else if (
      zones.every((z) =>
        !z.ids[key] && !this._hass.states[this._guess(z.name)[key]]
      )
    ) {
      body = `<div class="msg">${s.needUpdate}</div>`;
    } else {
      const items = zones.map((z) => this._collect(z));
      body = this._config.range === "week"
        ? this._weekHtml(items)
        : this._dayHtml(items);
    }

    const title = this._config.title;

    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card${title ? ` header="${esc(title)}"` : ""}>${body}</ha-card>`;
  }
}

class YesplanCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { title: "Dagplanning", range: "today" };
  }

  set hass(hass) {
    this._hass = hass;
  }

  setConfig(config) {
    this._config = {
      title: "Dagplanning",
      range: "today",
      sort: "time",
      hide_empty: true,
      show_profile: true,
      show_schedule: true,
      show_tickets: true,
      show_fields: true,
      ...config,
    };

    this._renderEditor();
  }

  _value(name) {
    const el = this.shadowRoot.querySelector(`[name="${name}"]`);
    return el ? el.value : "";
  }

  _checked(name) {
    const el = this.shadowRoot.querySelector(`[name="${name}"]`);
    return Boolean(el && el.checked);
  }

  _update() {
    if (!this._config) return;

    this._config = {
      ...this._config,
      title: this._value("title"),
      range: this._value("range"),
      sort: this._value("sort"),
      hide_empty: this._checked("hide_empty"),
      show_profile: this._checked("show_profile"),
      show_schedule: this._checked("show_schedule"),
      show_tickets: this._checked("show_tickets"),
      show_fields: this._checked("show_fields"),
    };

    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true,
    }));
  }

  _renderEditor() {
    if (!this.shadowRoot || !this._config) return;

    const c = this._config;
    const checked = (key) => c[key] !== false ? "checked" : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; }
        .form { display:grid; gap:16px; }
        label { display:grid; gap:6px; font-weight:500; }
        input[type="text"], select {
          box-sizing:border-box; width:100%; min-height:40px; padding:8px 10px;
          color:var(--primary-text-color); background:var(--card-background-color);
          border:1px solid var(--outline-color, var(--divider-color)); border-radius:8px;
          font:inherit;
        }
        .checks { display:grid; gap:12px; }
        .check { display:flex; align-items:center; gap:10px; font-weight:400; }
        input[type="checkbox"] { width:18px; height:18px; }
      </style>
      <div class="form">
        <label>Titel
          <input name="title" type="text" value="${esc(c.title || "")}" placeholder="Dagplanning">
        </label>
        <label>Periode
          <select name="range">
            <option value="today" ${c.range === "today" ? "selected" : ""}>Vandaag</option>
            <option value="tomorrow" ${c.range === "tomorrow" ? "selected" : ""}>Morgen</option>
            <option value="week" ${c.range === "week" ? "selected" : ""}>Deze week</option>
          </select>
        </label>
        <label>Sortering
          <select name="sort">
            <option value="time" ${c.sort !== "zalen" ? "selected" : ""}>Op begintijd</option>
            <option value="zalen" ${c.sort === "zalen" ? "selected" : ""}>Op zaal</option>
          </select>
        </label>
        <div class="checks">
          <label class="check"><input name="hide_empty" type="checkbox" ${checked("hide_empty")}> Verberg lege zalen</label>
          <label class="check"><input name="show_profile" type="checkbox" ${checked("show_profile")}> Toon profiel</label>
          <label class="check"><input name="show_schedule" type="checkbox" ${checked("show_schedule")}> Toon tijdschema (vandaag)</label>
          <label class="check"><input name="show_tickets" type="checkbox" ${checked("show_tickets")}> Toon ticketverkoop</label>
          <label class="check"><input name="show_fields" type="checkbox" ${checked("show_fields")}> Toon extra velden</label>
        </div>
      </div>
    `;

    this.shadowRoot.querySelectorAll("input, select").forEach((el) => {
      el.addEventListener("input", () => this._update());
      el.addEventListener("change", () => this._update());
    });
  }
}

if (!customElements.get("yesplan-card-editor")) {
  customElements.define("yesplan-card-editor", YesplanCardEditor);
}

if (!customElements.get("yesplan-card")) {
  customElements.define("yesplan-card", YesplanCard);
}

window.customCards = window.customCards || [];

if (!window.customCards.some((c) => c.type === "yesplan-card")) {
  window.customCards.push({
    type: "yesplan-card",
    name: "Yesplan",
    description: "Overzicht per zaal: bezet/vrij, nu bezig, volgende en agenda van vandaag.",
  });
}

console.info(
  `%c YESPLAN-CARD %c ${CARD_VERSION || "(geen ?v=)"} `,
  "background:#4f7cff;color:#fff",
  ""
);
})();
