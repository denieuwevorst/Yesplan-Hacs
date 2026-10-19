/* Yesplan card for Home Assistant — served by the Yesplan integration. */
const CARD_VERSION = "0.2.0";

const STR = {
  nl: {
    occupied: "Bezet", free: "Vrij", now: "Nu bezig", until: "tot", next: "Volgende",
    at: "om", inTime: "over", today: "Vandaag", empty: "Geen evenementen vandaag.",
    noZones: "Geen zalen gevonden. Is de Yesplan-integratie ingesteld?",
    unavailable: "Niet beschikbaar", min: "min", hr: "u",
  },
  en: {
    occupied: "Occupied", free: "Free", now: "Now", until: "until", next: "Next",
    at: "at", inTime: "in", today: "Today", empty: "No events today.",
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

const GUESS = {
  events_today: ["sensor", ["voorstellingen_vandaag", "events_today"]],
  next_start: ["sensor", ["volgende_start", "next_start"]],
  active: ["binary_sensor", ["bezet", "occupied"]],
};

const STYLE = `
  :host { display: block; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 12px; padding: 0 16px 16px; }
  .msg { padding: 16px; color: var(--secondary-text-color); }
  .zaal { background: var(--secondary-background-color, rgba(127,127,127,.08));
          border-radius: var(--ha-card-border-radius, 12px); padding: 12px 14px;
          border-left: 4px solid var(--divider-color); }
  .zaal.busy { border-left-color: var(--primary-color); }
  .head { display: flex; justify-content: space-between; align-items: center;
          gap: 8px; margin-bottom: 8px; }
  .name { font-weight: 600; font-size: 1.05em; }
  .badge { font-size: .75em; font-weight: 600; padding: 2px 10px; border-radius: 999px;
           background: var(--divider-color); color: var(--secondary-text-color);
           white-space: nowrap; }
  .badge.busy { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .now, .next { font-size: .9em; margin-bottom: 6px; line-height: 1.35; }
  .now { padding: 8px 10px; border-radius: 8px;
         background: color-mix(in srgb, var(--primary-color) 14%, transparent); }
  .lbl { color: var(--secondary-text-color); font-size: .8em; text-transform: uppercase;
         letter-spacing: .04em; margin-right: 4px; }
  .list { margin-top: 6px; }
  .row { display: grid; grid-template-columns: auto 1fr auto; gap: 10px;
         align-items: baseline; padding: 7px 0; border-top: 1px solid var(--divider-color); }
  .row.past { opacity: .45; }
  .row.live .title { font-weight: 600; }
  .time { font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }
  .title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sub { font-size: .8em; color: var(--secondary-text-color); }
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
    this._config = { hide_empty: true, show_profile: true, ...config };
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
    const todayE = st(z.ids.events_today);
    const nextE = st(z.ids.next_start);
    const actE = st(z.ids.active);
    const now = new Date();

    const unavailable = [todayE, nextE, actE].every(
      (e) => !e || e.state === "unavailable");
    const events = (todayE && todayE.attributes && todayE.attributes.events) || [];
    const busy = !!actE && actE.state === "on";

    if (this._config.hide_empty && !busy && events.length === 0 && !unavailable) return "";

    let nowHtml = "";
    if (busy) {
      const a = actE.attributes || {};
      nowHtml = `<div class="now"><span class="lbl">${s.now}</span><strong>${esc(a.name)}</strong>${
        a.end ? ` <span class="sub">${s.until} ${this._fmtTime(a.end)}</span>` : ""}</div>`;
    }

    let nextHtml = "";
    if (!busy && nextE && nextE.state && !["unknown", "unavailable"].includes(nextE.state)) {
      const a = nextE.attributes || {};
      const sameDay = this._dayKey(nextE.state) === this._dayKey(now);
      const when = sameDay
        ? `${s.at} ${this._fmtTime(nextE.state)}`
        : `${new Date(nextE.state).toLocaleDateString(this._lang, {
            weekday: "short", day: "numeric", month: "short", timeZone: this._tz })} ${this._fmtTime(nextE.state)}`;
      const rel = sameDay ? this._until(nextE.state) : "";
      nextHtml = `<div class="next"><span class="lbl">${s.next}</span><strong>${esc(a.name)}</strong> <span class="sub">${when}${rel ? ` · ${rel}` : ""}</span></div>`;
    }

    const rows = events.map((e) => {
      const start = new Date(e.start);
      const end = e.end ? new Date(e.end) : null;
      const live = start <= now && end && now < end;
      const past = end ? end <= now : false;
      const profile = this._config.show_profile && e.profile
        ? `<div class="sub">${esc(e.profile)}</div>` : "";
      return `<div class="row ${past ? "past" : ""} ${live ? "live" : ""}">
        <div class="time">${this._fmtTime(e.start)}${e.end ? `–${this._fmtTime(e.end)}` : ""}</div>
        <div><div class="title">${esc(e.name)}</div>${profile}</div>
        ${this._chip(e.status)}</div>`;
    }).join("");

    const listHtml = rows
      ? `<div class="list">${rows}</div>`
      : `<div class="none">${unavailable ? s.unavailable : s.empty}</div>`;

    return `<div class="zaal ${busy ? "busy" : ""}">
      <div class="head"><div class="name">${esc(z.name)}</div>
        <span class="badge ${busy ? "busy" : ""}">${busy ? s.occupied : s.free}</span></div>
      ${nowHtml}${nextHtml}${listHtml}</div>`;
  }

  _render() {
    if (!this._config || !this._hass) return;
    const s = this._s;
    const zones = this._zones();
    const tiles = zones.map((z) => this._zoneHtml(z)).filter(Boolean).join("");
    const body = !zones.length
      ? `<div class="msg">${s.noZones}</div>`
      : tiles
        ? `<div class="grid">${tiles}</div>`
        : `<div class="msg">${s.empty}</div>`;
    const title = this._config.title;
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card${title ? ` header="${esc(title)}"` : ""}>${body}</ha-card>`;
  }
}

if (!customElements.get("yesplan-card")) {
  customElements.define("yesplan-card", YesplanCard);
}
window.customCards = window.customCards || [];
window.customCards.push({
  type: "yesplan-card",
  name: "Yesplan",
  description: "Overzicht per zaal: bezet/vrij, nu bezig, volgende en agenda van vandaag.",
});
console.info(`%c YESPLAN-CARD %c ${CARD_VERSION} `, "background:#4f7cff;color:#fff", "");
