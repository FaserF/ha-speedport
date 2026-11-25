const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { JSDOM } = require('jsdom');

const source = readFileSync(join(__dirname, '..', 'www', 'router-flyout-card.js'), 'utf8');

function setup(config = {}) {
  const dom = new JSDOM('', { runScripts: 'outside-only' });
  dom.window.eval(source);
  const card = dom.window.document.createElement('router-flyout-card');
  card.setConfig({
    image: '/local/router-flyout-scene.svg',
    router_image: '/local/router-flyout-router.svg',
    entity: 'sensor.example_router',
    refresh_entity: 'button.example_refresh',
    ...config,
  });
  const calls = [];
  card.hass = {
    states: { 'sensor.example_router': { state: 'UP', last_updated: '2026-01-01T00:00:00Z' } },
    callService: async (...args) => { calls.push(['service', ...args]); },
    callWS: async (request) => {
      calls.push(['ws', request]);
      return { response: { device_name: 'Example Router', connected_devices_count: 3 } };
    },
  };
  return { dom, card, calls };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

test('opening refreshes once; HA updates preserve DOM and do not reopen after close', async () => {
  const { dom, card, calls } = setup();
  try {
    const root = card.shadowRoot;
    const panel = root.querySelector('.panel');
    root.querySelector('.router').click();
    root.querySelector('.label').click();
    await tick();
    assert.equal(calls.filter(([kind]) => kind === 'service').length, 1);
    assert.equal(root.querySelector('.dialog').hidden, false);
    panel.dispatchEvent(new dom.window.Event('animationend'));
    card.hass = { ...card._hass };
    assert.equal(root.querySelector('.panel'), panel);
    assert.equal(root.querySelector('.dialog').classList.contains('opening'), false);

    root.querySelector('.close').click();
    card.hass = {
      ...card._hass,
      states: { 'sensor.example_router': { state: 'UP', last_updated: '2026-01-01T00:01:00Z' } },
    };
    await tick();
    assert.equal(root.querySelector('.dialog').hidden, true);
    assert.equal(root.querySelector('.panel'), panel);
    assert.equal(calls.filter(([kind]) => kind === 'service').length, 1);
  } finally {
    dom.window.close();
  }
});

test('manual refresh presses backend before reading response, with selected entry', async () => {
  const { dom, card, calls } = setup({ entry_id: 'example-entry' });
  try {
    card.shadowRoot.querySelector('.refresh').click();
    await tick();
    assert.deepEqual(calls.map(([kind]) => kind), ['service', 'ws']);
    assert.equal(calls[0][1], 'button');
    assert.equal(calls[0][2], 'press');
    assert.equal(calls[0][3].entity_id, 'button.example_refresh');
    assert.equal(calls[1][1].return_response, true);
    assert.equal(calls[1][1].service_data.entry_id, 'example-entry');
    assert.equal(card.readValue('connected_devices_count'), 3);
    assert.equal(card.shadowRoot.querySelector('.feedback').textContent, 'Details erfolgreich aktualisiert.');
    assert.equal(card.shadowRoot.querySelector('.refresh').disabled, false);
    assert.ok(card._lastRefreshAt);
  } finally {
    dom.window.close();
  }
});

test('failed refresh is visible, reenables button and never claims success', async () => {
  const { dom, card } = setup();
  try {
    card._hass.callService = async () => { throw new Error('Example failure'); };
    await card.refreshDetails();
    const error = card.shadowRoot.querySelector('.error');
    assert.equal(error.hidden, false);
    assert.match(error.textContent, /Example failure/);
    assert.equal(card.shadowRoot.querySelector('.feedback').textContent, '');
    assert.equal(card.shadowRoot.querySelector('.refresh').disabled, false);
    assert.equal(card._lastRefreshAt, null);
  } finally {
    dom.window.close();
  }
});

test('new status formats and configurable GUI link do not require private fixtures', () => {
  const { dom, card } = setup({ status_url: 'http://router.example/6.5/gui/status/' });
  try {
    assert.equal(card.formatValue(2, 'percent'), '40 %');
    assert.equal(card.formatValue(0, 'percent'), '0 %');
    assert.equal(card.formatValue(1000, 'lan-speed'), '1 Gbit/s');
    assert.equal(card.formatValue(100, 'lan-speed'), '100 Mbit/s');
    assert.equal(card.formatValue(0, 'lan-speed'), null);
    assert.equal(card.formatValue('DORMANT', 'lan'), 'Keine Verbindung');
    assert.equal(card.formatValue('NONE', 'vpn'), 'Nicht aktiv');
    assert.equal(card.shadowRoot.querySelector('.link').href, 'http://router.example/6.5/gui/status/');
  } finally {
    dom.window.close();
  }
});
