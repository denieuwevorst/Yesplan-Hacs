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
    next: "Volgende",
    at: "om", inTime: "over", todayLbl: "vandaag",
    emptyToday: "Geen evenementen vandaag.", emptyTomorrow: "Geen evenementen morgen.",
    emptyWeek: "Geen evenementen deze week.",
    needUpdate: "De sensor voor deze periode ontbreekt. Werk de Yesplan-integratie bij en herstart Home Assistant.",
    noZones: "Geen zalen gevonden. Is de Yesplan-integratie ingesteld?",
    unavailable: "Niet beschikbaar", min: "min", hr: "u",
  },
  en: {
    next: "Next",
    at: "at", inTime: "in", todayLbl: "today",
    emptyToday: "No events today.", emptyTomorrow: "No events tomorrow.",
    emptyWeek: "No events this week.",
    needUpdate: "The sensor for this period is missing. Update the Yesplan integration and restart Home Assistant.",
    noZones: "No locations found. Is the Yesplan integration set up?",
    unavailable: "Unavailable", min: "min", hr: "h",
  },
};

const slug = (s) =>
  String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const RANGE_KEY = { today: "events_today", tomorrow: "events_tomorrow", week: "events_week" };

const GUESS = {
  events_today: ["sensor", ["voorstellingen_vandaag", "events_today"]],
  events_tomorrow: ["sensor", ["voorstellingen_morgen", "events_tomorrow"]],
  events_week: ["sensor", ["voorstellingen_deze_week", "events_this_week"]],
  next_start: ["sensor", ["volgende_start", "next_start"]],
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
  .next { font-size: .9em; margin-bottom: 6px; line-height: 1.35; }
  .lbl { color: var(--secondary-text-color); font-size: .8em; text-transform: uppercase;
         letter-spacing: .04em; margin-right: 4px; }
  .list { margin-top: 6px; }
  .day { font-size: .78em; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
         color: var(--secondary-text-color); padding: 12px 0 2px; }
  .day:first-child { padding-top: 4px; }
  .day.today { color: var(--primary-color); }
  .row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 10px;
         align-items: baseline; padding: 7px 0; border-top: 1px solid var(--divider-color); }
  .row.past { opacity: .45; }
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
    this._config = { hide_empty: true, show_profile: true, range: "today", ...config };
    if (!RANGE_KEY[this._config.range]) this._config.range = "today";
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

  getCardSize() { return 6; }
  static getStubConfig() { return { title: "Dagplanning" }; }

  get _s() {
    const lang = (this._hass && this._hass.language) || "nl";
    return STR[lang.startsWith("nl") ? "nl" : "en"];
  }
  get _lang() { return (this._hass && this._hass.language) || "nl"; }
  get _tz() { return (this._hass && this._hass.config && this._hass.config.time_zone) || undefined; }

  _guess(name) {
    const ids = {};
    const s = slug(name);
    for (const [key, [domain, names]] of Object.entries(GUESS)) {
      const hit = names.map((n) => `${domain}.${s}_${n}`).find((id) => this._hass.states[id]);
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
        zones = this._config.zalen.map((name) => ({ name, ids: this._guess(name) }));
      }
      zones = zones
        .filter((z) => order.includes(z.name.toLowerCase()))
        .sort((a, b) => order.indexOf(a.name.toLowerCase()) - order.indexOf(b.name.toLowerCase()));
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
      for (const id of Object.values(z.ids)) {
        const st = this._hass.states[id];
        parts.push(`${id}:${st ? st.last_updated : "-"}`);
      }
    }
    return parts.join("|");
  }

  _fmtTime(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleTimeString(this._lang, {
      hour: "2-digit", minute: "2-digit", hour12: false, timeZone: this._tz,
    });
  }
  _dayKey(d) { return new Date(d).toLocaleDateString("en-CA", { timeZone: this._tz }); }

  _until(iso) {
    const s = this._s;
    const m = Math.round((new Date(iso) - new Date()) / 60000);
    if (m <= 0) return "";
    if (m < 60) return `${s.inTime} ${m} ${s.min}`;
    const hh = Math.floor(m / 60), mm = m % 60;
    if (hh >= 24) return "";
    return `${s.inTime} ${hh} ${s.hr}${mm ? ` ${mm} ${s.min}` : ""}`;
  }

  _chip(status) {
    if (!status) return "";
    const k = status.toLowerCase();
    const cls = k.startsWith("bevestigd") || k === "confirmed" ? "ok"
      : k.startsWith("optie") || k === "option" ? "opt"
      : k.startsWith("voorlopig") || k === "tentative" ? "tent" : "";
    return `<span class="chip ${cls}">${esc(status)}</span>`;
  }

  _zoneHtml(z) {
    const s = this._s;
    const h = this._hass;
    const st = (id) => (id ? h.states[id] : undefined);
    const range = this._config.range;
    const todayE = st(z.ids[RANGE_KEY[range]]);
    const nextE = st(z.ids.next_start);
    const now = new Date();

    const unavailable = !todayE || todayE.state === "unavailable";
    const events = (todayE && todayE.attributes && todayE.attributes.events) || [];

    if (this._config.hide_empty && events.length === 0 && !unavailable) return "";

    let nextHtml = "";
    if (range === "today" && nextE && nextE.state && !["unknown", "unavailable"].includes(nextE.state)) {
      const a = nextE.attributes || {};
      const sameDay = this._dayKey(nextE.state) === this._dayKey(now);
      const when = sameDay
        ? `${s.at} ${this._fmtTime(nextE.state)}`
        : `${new Date(nextE.state).toLocaleDateString(this._lang, {
            weekday: "short", day: "numeric", month: "short", timeZone: this._tz })} ${this._fmtTime(nextE.state)}`;
      const rel = sameDay ? this._until(nextE.state) : "";
      nextHtml = `<div class="next"><span class="lbl">${s.next}</span><strong>${esc(a.name)}</strong> <span class="sub">${when}${rel ? ` · ${rel}` : ""}</span></div>`;
    }

    const row = (e) => {
      const end = e.end ? new Date(e.end) : null;
      const past = end ? end <= now : false;
      const profile = this._config.show_profile && e.profile
        ? `<div class="sub">${esc(e.profile)}</div>` : "";
      return `<div class="row ${past ? "past" : ""}">
        <div class="time">${this._fmtTime(e.start)}${e.end ? `–${this._fmtTime(e.end)}` : ""}</div>
        <div><div class="title">${esc(e.name)}</div>${profile}</div>
        ${this._chip(e.status)}</div>`;
    };

    let rows = "";
    if (range === "week") {
      const todayKey = this._dayKey(now);
      let lastKey = null;
      for (const e of events) {
        const key = this._dayKey(e.start);
        if (key !== lastKey) {
          lastKey = key;
          const label = new Date(e.start).toLocaleDateString(this._lang, {
            weekday: "long", day: "numeric", month: "long", timeZone: this._tz });
          rows += `<div class="day ${key === todayKey ? "today" : ""}">${esc(label)}${
            key === todayKey ? ` · ${s.todayLbl}` : ""}</div>`;
        }
        rows += row(e);
      }
    } else {
      rows = events.map(row).join("");
    }

    const listHtml = rows
      ? `<div class="list">${rows}</div>`
      : `<div class="none">${unavailable ? s.unavailable : (range === "week" ? s.emptyWeek : range === "tomorrow" ? s.emptyTomorrow : s.emptyToday)}</div>`;

    return `<div class="zaal">
      <div class="head"><div class="name">${esc(z.name)}</div></div>
      ${nextHtml}${listHtml}</div>`;
  }

  _render() {
    if (!this._config || !this._hass) return;
    const s = this._s;
    const zones = this._zones();
    const key = RANGE_KEY[this._config.range];
    const tiles = zones.map((z) => this._zoneHtml(z)).filter(Boolean).join("");
    const empty = { today: s.emptyToday, tomorrow: s.emptyTomorrow, week: s.emptyWeek }[this._config.range];
    const body = !zones.length
      ? `<div class="msg">${s.noZones}</div>`
      : zones.every((z) => !z.ids[key] && !this._hass.states[this._guess(z.name)[key]])
        ? `<div class="msg">${s.needUpdate}</div>`
      : tiles
        ? `<div class="grid">${tiles}</div>`
        : `<div class="msg">${empty}</div>`;
    const title = this._config.title;
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card${title ? ` header="${esc(title)}"` : ""}>${body}</ha-card>`;
  }
}

if (!customElements.get("yesplan-card")) {
  customElements.define("yesplan-card", YesplanCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "yesplan-card")) window.customCards.push({
  type: "yesplan-card",
  name: "Yesplan",
  description: "Overzicht per zaal: bezet/vrij, nu bezig, volgende en agenda van vandaag.",
});
console.info(`%c YESPLAN-CARD %c ${CARD_VERSION || "(geen ?v=)"} `, "background:#4f7cff;color:#fff", "");
})();
