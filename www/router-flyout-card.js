class RouterFlyoutCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.image || !config.router_image) {
      throw new Error('image and router_image are required');
    }
    this.config = config;
    if (this._dialogOpen === undefined) {
      this._dialogOpen = false;
      this._refreshing = false;
      this._refreshError = '';
      this._refreshMessage = '';
      this._routerData = {};
      this._lastRefreshAt = null;
      this._lastRouterUpdate = null;
    }
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    if (!this._rendered) {
      this.render();
      this._rendered = true;
      this.updateValues();
      this.updateFeedback();
    } else {
      this.updateValues();
    }
  }

  set hass(hass) {
    this._hass = hass;
    this.updateValues();
    const state = hass.states?.[this.config.timestamp_entity || this.config.entity];
    const reported = state?.last_reported || state?.last_updated;
    if (reported && reported !== this._lastRouterUpdate) {
      this._lastRouterUpdate = reported;
      if (this._dialogOpen && !this._refreshing) void this.loadCurrentData();
    }
  }

  getCardSize() {
    return 7;
  }

  async fetchRouterData() {
    const result = await this._hass.callWS({
      type: 'call_service',
      domain: 'speedport',
      service: 'get_raw_data',
      service_data: this.config.entry_id ? { entry_id: this.config.entry_id } : {},
      return_response: true,
    });
    if (!result?.response || typeof result.response !== 'object') {
      throw new Error('Home Assistant returned no router data');
    }
    this._routerData = result.response;
    this.updateValues();
  }

  async loadCurrentData() {
    try {
      await this.fetchRouterData();
      this._refreshError = '';
    } catch (error) {
      this._refreshError = `Zusätzliche Routerdaten konnten nicht geladen werden: ${error?.message || error}`;
    }
    this.updateFeedback();
  }

  async refreshDetails() {
    if (this._refreshing) return;
    if (!this.config.refresh_entity || !this._hass) {
      this._refreshError = 'Aktualisierung ist nicht konfiguriert.';
      this.updateFeedback();
      return;
    }

    this._refreshing = true;
    this._refreshError = '';
    this._refreshMessage = '';
    this.updateFeedback();

    let serviceCompleted = false;
    try {
      await this._hass.callService('button', 'press', {
        entity_id: this.config.refresh_entity,
      });
      serviceCompleted = true;
      await this.fetchRouterData();
      this._lastRefreshAt = new Date();
      this._refreshMessage = 'Details erfolgreich aktualisiert.';
    } catch (error) {
      this._refreshError = serviceCompleted
        ? `Router aktualisiert, aber die Details konnten nicht geladen werden: ${error?.message || error}`
        : `Aktualisierung fehlgeschlagen: ${error?.message || error}`;
    } finally {
      this._refreshing = false;
      this.updateValues();
      this.updateFeedback();
    }
  }

  readValue(key, entityKey) {
    const raw = this._routerData?.[key];
    if (raw !== undefined && raw !== null && raw !== '') return raw;

    const entityId = this.config.entity_map?.[entityKey || key];
    const entity = entityId ? this._hass?.states?.[entityId] : undefined;
    if (!entity || ['unknown', 'unavailable'].includes(entity.state)) {
      if (key === 'connected_devices_count' && entity) {
        const devices = entity.attributes?.devices;
        if (Array.isArray(devices)) return devices.length;
      }
      return null;
    }
    if (key === 'connected_devices_count') {
      const devices = entity.attributes?.devices;
      if (Array.isArray(devices)) return devices.length;
    }
    return entity.state;
  }

  formatValue(value, format) {
    if (value === null || value === undefined || value === '') return null;
    const text = String(value).trim();
    const normalized = text.toLowerCase();
    if (format === 'dsl') {
      if (['up', 'online', 'synchronized', 'synchron'].includes(normalized)) return 'Synchron';
      if (['down', 'offline', 'not synchronized'].includes(normalized)) return 'Nicht synchron';
      return text;
    }
    if (format === 'active') {
      if (['1', 'true', 'on', 'enabled', 'up', 'active'].includes(normalized)) return 'Aktiv';
      if (['0', 'false', 'off', 'disabled', 'down', 'inactive'].includes(normalized)) return 'Nicht aktiv';
      return text;
    }
    if (format === 'kbit') return `${text} kbit/s`;
    if (format === 'percent') {
      const signalLevel = Number(value);
      return Number.isInteger(signalLevel) && signalLevel >= 0 && signalLevel <= 5
        ? `${signalLevel * 20} %`
        : `${text} %`;
    }
    if (format === 'latency') return /ms$/i.test(text) ? text : `${text} ms`;
    if (format === 'lan') {
      if (['up', 'connected', 'online'].includes(normalized)) {
        return 'Verbunden';
      }
      if (['down', 'dormant', 'disconnected', 'offline', '0', ''].includes(normalized)) {
        return 'Keine Verbindung';
      }
      return text;
    }
    if (format === 'lan-speed') {
      if (/(bit\/s|bps)$/i.test(text)) return text;
      const rate = Number(value);
      if (!Number.isFinite(rate) || rate <= 0) return null;
      if (Number.isFinite(rate) && rate >= 1_000_000_000) {
        return `${rate / 1_000_000_000} Gbit/s`;
      }
      if (Number.isFinite(rate) && rate >= 1_000_000) {
        return `${rate / 1_000_000} Mbit/s`;
      }
      if (rate >= 1_000) return `${rate / 1_000} Gbit/s`;
      return `${rate} Mbit/s`;
    }
    if (format === 'bonding-dsl') {
      return /BONDING_(LTEDSL|DSL)/i.test(text) ? 'Aktiv' : 'Nicht aktiv';
    }
    if (format === 'bonding-lte') {
      return /BONDING_(LTEDSL|LTE)/i.test(text) ? 'Aktiv' : 'Nicht aktiv';
    }
    if (format === 'bonding-hybrid') {
      return /BONDING/i.test(text) ? 'Aktiv' : 'Nicht aktiv';
    }
    if (format === 'external-modem') {
      if (/^(none|disabled|off|0|lan)$/i.test(text)) return 'Nicht aktiv';
      return /^(wan|sfp)$/i.test(text) ? `Aktiv (${text})` : text;
    }
    if (format === 'vpn') {
      return /^(none|disabled|off|0)$/i.test(text) ? 'Nicht aktiv' : `Aktiv (${text})`;
    }
    if (format === 'duration') {
      const seconds = Number(value);
      if (!Number.isFinite(seconds) || seconds < 0) return text;
      const days = Math.floor(seconds / 86400);
      const hours = Math.floor((seconds % 86400) / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${days} T. ${hours} Std. ${minutes} Min.`;
    }
    if (format === 'date') {
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? text : date.toLocaleString('de-DE');
    }
    return text;
  }

  updateValues() {
    if (!this._rendered || !this.shadowRoot) return;

    for (const element of this.shadowRoot.querySelectorAll('[data-value]')) {
      const value = this.readValue(element.dataset.value, element.dataset.entity);
      const display = this.formatValue(value, element.dataset.format) || 'Nicht verfügbar';
      element.textContent = display;
      element.parentElement.hidden = display === 'Nicht verfügbar';
    }

    for (const section of this.shadowRoot.querySelectorAll('section')) {
      section.hidden = !section.querySelector('.value-row:not([hidden])');
    }

    const statusEntity = this._hass?.states?.[this.config.entity];
    const status = statusEntity?.state || this.config.router_status || 'Status unbekannt';
    const normalized = String(status).toLowerCase();
    const online = ['up', 'online', 'connected'].includes(normalized);
    const offline = ['down', 'offline', 'disconnected'].includes(normalized);
    const displayStatus = online ? 'Online' : offline ? 'Offline' : String(status);
    const dot = this.shadowRoot.querySelector('.status-dot');
    dot.classList.toggle('online', online);
    dot.classList.toggle('offline', offline);
    dot.classList.toggle('unknown', !online && !offline);
    dot.title = displayStatus;
    dot.setAttribute('aria-label', displayStatus);
    const titleText = this.config.title || this._routerData?.device_name || 'Speedport';
    const labelText = this.shadowRoot.querySelector('.label span');
    if (labelText) labelText.textContent = titleText;
    const dialogTitle = this.shadowRoot.querySelector('#router-title');
    if (dialogTitle) dialogTitle.textContent = titleText;
    this.shadowRoot.querySelector('.label').setAttribute(
      'aria-label',
      `${titleText}, Status ${displayStatus}`,
    );

    const timestamp = this._lastRefreshAt || this._routerData?.status_datetime
      || statusEntity?.last_reported || statusEntity?.last_updated;
    const timestampDate = timestamp instanceof Date ? timestamp : new Date(timestamp);
    this.shadowRoot.querySelector('.meta').textContent =
      `Letzte Aktualisierung ${Number.isNaN(timestampDate.getTime()) ? 'Nicht verfügbar' : timestampDate.toLocaleString('de-DE')}`;
  }

  updateFeedback() {
    if (!this._rendered || !this.shadowRoot) return;
    const button = this.shadowRoot.querySelector('.refresh');
    button.disabled = this._refreshing;
    button.textContent = this._refreshing ? 'Aktualisiere …' : 'Details aktualisieren';
    this.shadowRoot.querySelector('.feedback').textContent = this._refreshing
      ? 'Routerdaten werden abgerufen …'
      : this._refreshMessage;
    const error = this.shadowRoot.querySelector('.error');
    error.textContent = this._refreshError;
    error.hidden = !this._refreshError;
  }

  render() {
    const safe = (value) => String(value).replace(/[&<>"']/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[char]));
    const sections = [
      ['Gerät', [
        ['Modell', 'device_name', '', ''],
        ['Firmware', 'firmware_version', '', ''],
        ['Firmware-Datum', 'firmware_date', '', 'date'],
        ['Laufzeit', 'uptime', '', 'duration'],
      ]],
      ['Verbindung', [
        ['DSL-Link', 'dsl_link_status', 'dsl_link', 'dsl'],
        ['DSL-Verbindung', 'ppp_status', 'online_status', 'active'],
        ['Downstream', 'dsl_downstream', 'dsl_downstream', 'kbit'],
        ['Upstream', 'dsl_upstream', 'dsl_upstream', 'kbit'],
        ['Max. Download-Bandbreite', 'download_bandwidth', '', 'kbit'],
        ['Max. Upload-Bandbreite', 'upload_bandwidth', '', 'kbit'],
        ['Breitband-PoP', 'dsl_pop', '', ''],
        ['LTE-Verbindung', 'use_lte', '', 'active'],
        ['LTE-Empfang', 'lte_signal', '', 'percent'],
        ['DSL-Tunnel', 'bonding_mode', '', 'bonding-dsl'],
        ['LTE-Tunnel', 'bonding_mode', '', 'bonding-lte'],
        ['Hybrid-Bonding', 'bonding_mode', '', 'bonding-hybrid'],
        ['Ping-Zeitpunkt', 'ping_timestamp', '', 'date'],
        ['Durchschnittlicher Ping', 'ping_average_latency', '', 'latency'],
        ['DNS-Server', 'dns_v4', '', ''],
        ['Gateway', 'gateway_ip_v4', '', ''],
      ]],
      ['WLAN', [
        ['2,4-GHz-SSID', 'wlan_ssid', 'wlan_24_ghz_ssid', ''],
        ['2,4-GHz-Kanäle', 'wifi_24_channels', '', ''],
        ['2,4-GHz-Geräte', 'wifi_24_device_count', '', ''],
        ['5-GHz-SSID', 'wlan_5ghz_ssid', 'wlan_5_ghz_ssid', ''],
        ['5-GHz-Kanäle', 'wifi_5_channels', '', ''],
        ['5-GHz-Geräte', 'wifi_5_device_count', '', ''],
        ['Gaming-WLAN', 'wifi_gaming_enable', '', 'active'],
        ['Gaming-SSID', 'wifi_gaming_ssid', '', ''],
        ['Gaming-Geräte', 'wifi_gaming_device_count', '', ''],
        ['Gast-WLAN 2,4 GHz', 'wlan_guest_24_enabled', '', 'active'],
        ['Gast-SSID 2,4 GHz', 'wlan_guest_24_ssid', '', ''],
        ['Gast-WLAN 5 GHz', 'wlan_guest_5_enabled', '', 'active'],
        ['Gast-SSID 5 GHz', 'wlan_guest_5_ssid', '', ''],
        ['Gast-Geräte', 'wifi_guest_device_count', '', ''],
        ['Aktive Geräte gesamt', 'connected_devices_count', 'connected_devices_count', ''],
      ]],
      ['LAN und weitere Funktionen', [
        ['LAN-Port 1', 'lan1_status', '', 'lan'],
        ['LAN-Port 1 Geschwindigkeit', 'lan1_speed', '', 'lan-speed'],
        ['LAN-Port 2', 'lan2_status', '', 'lan'],
        ['LAN-Port 2 Geschwindigkeit', 'lan2_speed', '', 'lan-speed'],
        ['LAN-Port 3', 'lan3_status', '', 'lan'],
        ['LAN-Port 3 Geschwindigkeit', 'lan3_speed', '', 'lan-speed'],
        ['LAN-Port 4', 'lan4_status', '', 'lan'],
        ['LAN-Port 4 Geschwindigkeit', 'lan4_speed', '', 'lan-speed'],
        ['SmartHome', 'smart_home_status', '', 'active'],
        ['Externes Modem', 'external_modem', '', 'external-modem'],
        ['VPN-Zugang', 'vpn_access_type', '', 'vpn'],
        ['DECT-Basisstation', 'dect_base_enabled', '', 'active'],
      ]],
    ];
    const rows = sections.map(([title, fields]) =>
      `<section><h3>${safe(title)}</h3><dl>${fields.map(([label, key, entity, format]) =>
        `<div class="value-row" data-row="${safe(key)}"><dt>${safe(label)}</dt><dd data-value="${safe(key)}" data-entity="${safe(entity)}" data-format="${safe(format)}">Nicht verfügbar</dd></div>`
      ).join('')}</dl></section>`
    ).join('');

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;color:var(--primary-text-color);font-family:var(--primary-font-family,Arial,sans-serif)}
        .scene{position:relative;width:100%;overflow:hidden;background:var(--card-background-color,#1c1c1c)}
        .property{display:block;width:100%;height:auto}
        .router{position:absolute;left:30%;top:25%;width:3%;height:auto;max-height:12%;object-fit:contain;transform:translate(-50%,-50%);cursor:pointer;filter:drop-shadow(0 1px 3px #000)}
        .router:focus-visible,button:focus-visible{outline:3px solid var(--primary-color);outline-offset:3px}
        .label{position:absolute;left:31%;top:23%;transform:translateY(-50%);display:flex;align-items:center;gap:8px;padding:4px 8px;border:0;border-radius:4px;background:#000b;color:#fff;font-size:13px;cursor:pointer}
        .status-dot{width:9px;height:9px;flex:none;border-radius:50%;background:#9e9e9e;box-shadow:0 0 4px currentColor}
        .status-dot.online{background:#4caf50;color:#4caf50}.status-dot.offline{background:#f44336;color:#f44336}
        .dialog{position:fixed;inset:0;z-index:1000;display:flex;justify-content:flex-end;align-items:stretch;background:#0009}
        .dialog[hidden]{display:none}
        .panel{box-sizing:border-box;width:min(440px,92vw);height:100%;max-height:100vh;overflow:auto;border-radius:16px 0 0 16px;padding:20px;background:var(--card-background-color,#1c1c1c);box-shadow:0 12px 40px #0008}
        .dialog.opening .panel{animation:flyout-in .2s ease-out}
        @keyframes flyout-in{from{transform:translateX(100%)}to{transform:translateX(0)}}
        header{display:flex;align-items:center;justify-content:space-between;gap:12px}h2{font-size:20px;margin:0}button{font:inherit;color:inherit;background:transparent;border:0;cursor:pointer}.close{font-size:24px;padding:4px 10px}
        section{margin-top:16px}section[hidden],.value-row[hidden]{display:none}h3{margin:0 0 8px;color:var(--primary-color);font-size:16px}dl{margin:0;display:grid;grid-template-columns:1fr 1fr;gap:4px 16px}dl>div{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px solid var(--divider-color,#444)}dt{opacity:.8}dd{margin:0;text-align:right;font-weight:500;overflow-wrap:anywhere}.meta{margin:16px 0 8px;color:var(--secondary-text-color);font-size:12px}.feedback,.error{font-size:13px}.feedback{color:var(--secondary-text-color)}.error{color:var(--error-color,#f44336)}.link{display:inline-block;padding:10px 14px;border-radius:6px;background:var(--primary-color);color:var(--text-primary-color,#fff);text-decoration:none;font-weight:600}.refresh{display:block;margin-top:12px;padding:10px 14px;border-radius:6px;background:var(--primary-color);color:var(--text-primary-color,#fff);font-weight:600}.refresh:disabled{opacity:.6;cursor:wait}
        @media(max-width:480px){.panel{width:100vw;padding:16px;border-radius:0}dl{grid-template-columns:1fr}.label{font-size:10px;padding:3px 5px}}
      </style>
      <div class="scene">
        <img class="property" src="${safe(this.config.image)}" alt="Liegenschaft">
        <img class="router" src="${safe(this.config.router_image)}" alt="Speedport Pro Plus Router" role="button" tabindex="0" aria-label="Routerinformationen anzeigen">
        <button class="label" type="button" aria-label="Speedport Pro Plus, Status unbekannt"><span>Speedport Pro Plus</span><span class="status-dot unknown" role="img"></span></button>
      </div>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="router-title" hidden>
        <div class="panel"><header><h2 id="router-title">Speedport Pro Plus</h2><button class="close" type="button" aria-label="Schließen">×</button></header>
        ${rows}<p class="meta">Letzte Aktualisierung Nicht verfügbar</p><button class="refresh" type="button">Details aktualisieren</button><p class="feedback" role="status"></p><p class="error" role="alert" hidden></p><a class="link" href="${safe(this.config.status_url || 'http://speedport.ip/6.5/gui/status/')}" target="_blank" rel="noopener noreferrer">Router-Statusseite in neuem Tab öffnen ↗</a></div>
      </div>`;

    const dialog = this.shadowRoot.querySelector('.dialog');
    const router = this.shadowRoot.querySelector('.router');
    const open = () => {
      if (this._dialogOpen) return;
      this._dialogOpen = true;
      dialog.hidden = false;
      dialog.classList.add('opening');
      this.shadowRoot.querySelector('.close').focus();
      void this.refreshDetails();
    };
    const close = () => {
      this._dialogOpen = false;
      dialog.classList.remove('opening');
      dialog.hidden = true;
      router.focus();
    };
    this.shadowRoot.querySelector('.panel').addEventListener('animationend', () => {
      dialog.classList.remove('opening');
    });
    router.addEventListener('click', open);
    router.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        open();
      }
    });
    this.shadowRoot.querySelector('.label').addEventListener('click', open);
    this.shadowRoot.querySelector('.close').addEventListener('click', close);
    this.shadowRoot.querySelector('.refresh').addEventListener('click', () => {
      void this.refreshDetails();
    });
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) close();
    });
    this.shadowRoot.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !dialog.hidden) close();
    });
    this.updateValues();
    this.updateFeedback();
  }
}

customElements.define('router-flyout-card', RouterFlyoutCard);
