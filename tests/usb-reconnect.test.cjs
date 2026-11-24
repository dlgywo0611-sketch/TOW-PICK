const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { ReadableStream, WritableStream, TransformStream, TextDecoderStream, TextEncoderStream } = require('node:stream/web');

class CustomEventPolyfill extends Event {
  constructor(type, options = {}) {
    super(type);
    this.detail = options.detail;
  }
}

class FakeSerialPort {
  constructor(options = {}) {
    this.failClose = !!options.failClose;
    this.opened = false;
    this.closed = false;
    this.controller = null;
    this.readable = null;
  }
  async open({ baudRate }) {
    assert.equal(baudRate, 9600);
    this.opened = true;
    this.closed = false;
    this.readable = new ReadableStream({ start: c => { this.controller = c; } });
  }
  send(line) {
    this.controller.enqueue(new TextEncoder().encode(line));
  }
  unplug() {
    this.controller.error(new Error('device disconnected'));
  }
  async close() {
    this.closed = true;
    if (this.failClose) throw new Error('port close failed');
  }
}

const queue = [];
const navigator = { serial: { requestPort: async () => {
  const port = queue.shift();
  if (!port) throw new Error('no fake port queued');
  return port;
} } };
const context = {
  window: { isSecureContext: true },
  navigator, EventTarget, Event, CustomEvent: CustomEventPolyfill,
  TextDecoderStream, TextEncoderStream, TextEncoder,
  ReadableStream, WritableStream, TransformStream,
};
const bridgePath = path.join(__dirname, '..', 'frontend', 'petdock-bridge.js');
vm.runInNewContext(fs.readFileSync(bridgePath, 'utf8'), context);
const Bridge = context.window.PetDockBridge;
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(predicate, label) {
  for (let i = 0; i < 120; i++) {
    if (predicate()) return;
    await wait(5);
  }
  throw new Error(`timed out: ${label}`);
}

(async () => {
  const bridge = new Bridge();
  const states = [], buttons = [];
  bridge.addEventListener('usbstate', ev => states.push(ev.detail.connected));
  bridge.addEventListener('button', ev => buttons.push(ev.detail.button));

  // 1. Initial connection and button parsing
  const first = new FakeSerialPort({ failClose: true });
  queue.push(first);
  await bridge.connectUsb();
  first.send('BTN_A\r\nBTN_B\n');
  await until(() => buttons.length === 2, 'button messages');
  assert.deepEqual(buttons, ['A', 'B']);

  // 2. Physical unplug: read rejects, close also fails; state must still reset
  first.unplug();
  await until(() => bridge.serialPort === null, 'automatic cleanup after unplug');
  assert.equal(bridge.serialReader, null);
  assert.equal(bridge._usbReadTask, null);
  assert.equal(bridge._usbClosing, false);
  assert.deepEqual(states, [true, false]);

  // 3. Reconnect should succeed after unplug
  const second = new FakeSerialPort({ failClose: true });
  queue.push(second);
  await bridge.connectUsb();
  second.send('BTN_A\n');
  await until(() => buttons.length === 3, 'button after reconnect');

  // 4. Explicit disconnect: port.close error propagates, but state resets
  await assert.rejects(() => bridge.disconnectUsb(), /port close failed/);
  assert.equal(bridge.serialPort, null);
  assert.equal(bridge.serialReader, null);
  assert.equal(bridge._usbReadTask, null);
  assert.equal(bridge._usbClosing, false);
  assert.deepEqual(states, [true, false, true, false]);

  // 5. Reconnect after failed close
  const third = new FakeSerialPort();
  queue.push(third);
  await bridge.connectUsb();
  third.send('BTN_B\n');
  await until(() => buttons.length === 4, 'button on third connection');
  await bridge.disconnectUsb();
  assert.deepEqual(states, [true, false, true, false, true, false]);
  assert.deepEqual(buttons, ['A', 'B', 'A', 'B']);
  console.log('PASS: USB button input, unplug cleanup, reconnect, close failure cleanup, reconnect again');
})().catch(error => { console.error(error); process.exitCode = 1; });
