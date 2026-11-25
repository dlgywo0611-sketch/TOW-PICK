const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {
  ReadableStream, WritableStream, TransformStream,
  TextDecoderStream, TextEncoderStream,
} = require('node:stream/web');

class CustomEventPolyfill extends Event {
  constructor(type, options = {}) {
    super(type);
    this.detail = options.detail;
  }
}

class FakeCharacteristic extends EventTarget {
  constructor({ notify = true, notifyFailure = null } = {}) {
    super();
    this.properties = { notify, indicate: false, writeWithoutResponse: true, write: true };
    this.notifyFailure = notifyFailure;
    this.started = false;
    this.writes = [];
    this.value = null;
  }

  async startNotifications() {
    if (this.notifyFailure) throw new Error(this.notifyFailure);
    this.started = true;
    return this;
  }

  async writeValueWithoutResponse(payload) {
    this.writes.push(new TextDecoder().decode(payload));
  }

  send(text) {
    const bytes = new TextEncoder().encode(text);
    this.value = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    this.dispatchEvent(new Event('characteristicvaluechanged'));
  }
}

class FakeDevice extends EventTarget {
  constructor(characteristic) {
    super();
    this.characteristic = characteristic;
    this.gatt = {
      connected: false,
      connect: async () => {
        this.gatt.connected = true;
        return {
          connected: true,
          disconnect: () => this.disconnect(),
          getPrimaryService: async service => {
            assert.equal(service, '0000ffe0-0000-1000-8000-00805f9b34fb');
            return {
              getCharacteristic: async characteristicId => {
                assert.equal(characteristicId, '0000ffe1-0000-1000-8000-00805f9b34fb');
                return this.characteristic;
              },
            };
          },
        };
      },
      disconnect: () => this.disconnect(),
    };
  }

  disconnect() {
    if (!this.gatt.connected) return;
    this.gatt.connected = false;
    this.dispatchEvent(new Event('gattserverdisconnected'));
  }
}

const deviceQueue = [];
const navigator = {
  bluetooth: {
    requestDevice: async options => {
      assert.equal(options.filters.length, 1);
      assert.equal(options.filters[0].name, 'Meem');
      const device = deviceQueue.shift();
      if (!device) throw new Error('no fake BLE device queued');
      return device;
    },
  },
};
const context = {
  window: { isSecureContext: true },
  navigator,
  EventTarget, Event, CustomEvent: CustomEventPolyfill,
  TextDecoderStream, TextEncoderStream, TextDecoder, TextEncoder,
  ReadableStream, WritableStream, TransformStream, Uint8Array, DataView,
};
const bridgePath = path.join(__dirname, '..', 'frontend', 'petdock-bridge.js');
vm.runInNewContext(fs.readFileSync(bridgePath, 'utf8'), context);
const Bridge = context.window.PetDockBridge;

const appSource = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'app.js'), 'utf8');
const htmlSource = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'index.html'), 'utf8');
assert.match(appSource, /event\.detail\.source/);
assert.match(appSource, /event\.detail\.count/);
assert.match(htmlSource, /id="pet-event-meta"/);
assert.match(htmlSource, /id="ble-notify-status"/);

(async () => {
  let now = 1000;
  const bridge = new Bridge({ dedupeWindowMs: 250, now: () => now });
  const states = [];
  const buttons = [];
  bridge.addEventListener('blestate', event => states.push(event.detail));
  bridge.addEventListener('button', event => buttons.push(event.detail));

  // Notify-capable FFE1 receives button signals and keeps LED writes working.
  const firstCharacteristic = new FakeCharacteristic();
  const firstDevice = new FakeDevice(firstCharacteristic);
  deviceQueue.push(firstDevice);
  const firstResult = await bridge.connectBluetooth();
  assert.equal(firstResult.notifySupported, true);
  assert.equal(firstResult.notifyActive, true);
  assert.equal(firstCharacteristic.started, true);

  firstCharacteristic.send('BTN_A\r\n');
  now += 40;
  bridge.handleSerialLine('BTN_A'); // Same physical press over USB: suppress.
  now += 40;
  bridge.handleSerialLine('BTN_B');
  now += 40;
  firstCharacteristic.send('BTN_B\n'); // Same physical press over BLE: suppress.
  now += 40;
  bridge.handleSerialLine('BTN_A'); // Rapid same-source input remains valid.

  assert.deepEqual(buttons.map(item => `${item.button}:${item.source}`), [
    'A:BLE', 'B:USB', 'A:USB',
  ]);
  assert.equal(buttons.at(-1).count, 3);
  assert.deepEqual({ ...buttons.at(-1).counts }, { A: 2, B: 1 });

  // Notifications may split or combine HM-10 UART text packets.
  now = 2000;
  firstCharacteristic.send('BTN_');
  firstCharacteristic.send('A\r\nBTN_B\n');
  assert.deepEqual(buttons.slice(-2).map(item => item.button), ['A', 'B']);
  assert.equal(buttons.at(-1).count, 5);
  assert.deepEqual({ ...buttons.at(-1).counts }, { A: 3, B: 2 });

  await bridge.setLed('red');
  await bridge.setLed('green');
  await bridge.setLed('blue');
  await bridge.setLed('off');
  assert.deepEqual(firstCharacteristic.writes, ['R', 'G', 'B', 'X']);

  // GATT disconnect clears stale listeners and allows a fresh Notify connection.
  firstDevice.disconnect();
  assert.equal(bridge.bluetoothCharacteristic, null);
  assert.equal(states.at(-1).connected, false);

  const reconnectCharacteristic = new FakeCharacteristic();
  const reconnectDevice = new FakeDevice(reconnectCharacteristic);
  deviceQueue.push(reconnectDevice);
  const reconnectResult = await bridge.connectBluetooth();
  assert.equal(reconnectResult.notifyActive, true);
  now = 3000;
  reconnectCharacteristic.send('BTN_B');
  assert.equal(buttons.at(-1).source, 'BLE');
  assert.equal(buttons.at(-1).count, 6);
  reconnectDevice.disconnect();

  // Notify absence and start failure keep the existing LED write path available.
  const unsupportedCharacteristic = new FakeCharacteristic({ notify: false });
  const unsupportedDevice = new FakeDevice(unsupportedCharacteristic);
  deviceQueue.push(unsupportedDevice);
  const unsupportedResult = await bridge.connectBluetooth();
  assert.equal(unsupportedResult.notifySupported, false);
  assert.equal(unsupportedResult.notifyActive, false);
  await bridge.setLed('blue');
  assert.deepEqual(unsupportedCharacteristic.writes, ['B']);
  unsupportedDevice.disconnect();

  const failedCharacteristic = new FakeCharacteristic({ notifyFailure: 'CCC descriptor rejected' });
  const failedDevice = new FakeDevice(failedCharacteristic);
  deviceQueue.push(failedDevice);
  const failedResult = await bridge.connectBluetooth();
  assert.equal(failedResult.notifySupported, true);
  assert.equal(failedResult.notifyActive, false);
  assert.match(failedResult.notifyError, /CCC descriptor rejected/);
  await bridge.setLed('off');
  assert.deepEqual(failedCharacteristic.writes, ['X']);

  console.log('PASS: BLE FFE1 Notify, USB/BLE dedupe, source/counts, reconnect, fallback, LED writes');
})().catch(error => { console.error(error); process.exitCode = 1; });
