// PET DOCK bridge for TWO PICK (PR #4 USB reconnection fix)
class PetDockBridge extends EventTarget {
  static BLE_SERVICE = '0000ffe0-0000-1000-8000-00805f9b34fb';
  static BLE_CHARACTERISTIC = '0000ffe1-0000-1000-8000-00805f9b34fb';

  constructor() {
    super();
    this.serialPort = null;
    this.serialReader = null;
    this._usbReadTask = null;
    this._usbClosing = false;
    this.bluetoothDevice = null;
    this.bluetoothCharacteristic = null;
  }

  get supportsUsb() {
    return window.isSecureContext && 'serial' in navigator;
  }

  get supportsBluetooth() {
    return window.isSecureContext && 'bluetooth' in navigator;
  }

  async connectUsb() {
    if (!this.supportsUsb) {
      throw new Error('USB 연결은 Windows Chrome/Edge의 HTTPS 또는 localhost에서 사용할 수 있어요.');
    }
    if (this._usbClosing) {
      throw new Error('USB 연결을 종료하는 중입니다. 잠시 후 다시 연결해 주세요.');
    }
    if (this.serialPort) await this.disconnectUsb();

    // Must stay in the direct user-click path for Web Serial permissions.
    const port = await navigator.serial.requestPort();
    try {
      await port.open({ baudRate: 9600 });
    } catch (error) {
      // Opening failed; do not leave a stale port that blocks retry.
      this.serialPort = null;
      this.serialReader = null;
      this._usbReadTask = null;
      this._usbClosing = false;
      throw error;
    }

    this.serialPort = port;
    this.dispatchEvent(new CustomEvent('usbstate', { detail: { connected: true } }));

    const task = this.readSerial(port);
    this._usbReadTask = task;
    // Read termination (including cable removal) must also end USB state.
    // Handle rejection here to avoid unhandled promise rejections.
    void task.then(
      () => this._finishUsbAfterRead(port),
      (error) => {
        if (!this._usbClosing && this.serialPort === port) {
          this.dispatchEvent(new CustomEvent('error', {
            detail: { message: `USB 읽기 종료: ${error.message}` },
          }));
        }
        return this._finishUsbAfterRead(port);
      },
    );
  }

  async readSerial(port = this.serialPort) {
    if (!port?.readable) throw new Error('USB 시리얼 읽기 스트림이 없습니다.');
    const decoder = new TextDecoderStream();
    const readableClosed = port.readable.pipeTo(decoder.writable);
    const reader = decoder.readable.getReader();
    this.serialReader = reader;
    let pending = '';

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        pending += value || '';
        const lines = pending.split(/\r?\n/);
        pending = lines.pop() || '';
        lines.forEach((line) => this.handleSerialLine(line.trim()));
      }
    } finally {
      try { reader.releaseLock(); } catch (_) { /* Reader may already be released. */ }
      if (this.serialReader === reader) this.serialReader = null;
      await readableClosed.catch(() => {});
    }
  }

  handleSerialLine(line) {
    if (line !== 'BTN_A' && line !== 'BTN_B') return;
    this.dispatchEvent(new CustomEvent('button', {
      detail: { button: line === 'BTN_A' ? 'A' : 'B', raw: line },
    }));
  }

  _clearUsbState(port) {
    if (this.serialPort !== port) return;
    this.serialPort = null;
    this.serialReader = null;
    this._usbReadTask = null;
    this._usbClosing = false;
    this.dispatchEvent(new CustomEvent('usbstate', { detail: { connected: false } }));
  }

  // Used when a cable is physically unplugged or the serial read ends unexpectedly.
  async _finishUsbAfterRead(port) {
    if (this.serialPort !== port || this._usbClosing) return;
    this._usbClosing = true;
    try {
      // A detached port may reject close(); cleanup is still mandatory.
      await port.close().catch(() => {});
    } finally {
      this._clearUsbState(port);
    }
  }

  async disconnectUsb() {
    const port = this.serialPort;
    if (!port || this._usbClosing) return;
    this._usbClosing = true;
    try {
      if (this.serialReader) {
        await this.serialReader.cancel().catch(() => {});
      }
      if (this._usbReadTask) {
        await this._usbReadTask.catch(() => {});
      }
      // Keep the close error visible to the caller, but always clear state.
      await port.close();
    } finally {
      this._clearUsbState(port);
    }
  }

  async connectBluetooth() {
    if (!this.supportsBluetooth) {
      throw new Error('블루투스 연결은 Windows Chrome/Edge의 HTTPS 또는 localhost에서 사용할 수 있어요.');
    }

    this.bluetoothDevice = await navigator.bluetooth.requestDevice({
      filters: [{ name: 'Meem' }],
      optionalServices: [PetDockBridge.BLE_SERVICE],
    });
    this.bluetoothDevice.addEventListener('gattserverdisconnected', () => {
      this.bluetoothCharacteristic = null;
      this.dispatchEvent(new CustomEvent('blestate', { detail: { connected: false } }));
    });

    const server = await this.bluetoothDevice.gatt.connect();
    const service = await server.getPrimaryService(PetDockBridge.BLE_SERVICE);
    const characteristic = await service.getCharacteristic(PetDockBridge.BLE_CHARACTERISTIC);
    if (!this.getBleWriteMode(characteristic)) {
      if (server.connected) server.disconnect();
      throw new Error('Meem FFE1 특성이 BLE 쓰기를 지원하지 않습니다.');
    }
    this.bluetoothCharacteristic = characteristic;
    this.dispatchEvent(new CustomEvent('blestate', { detail: { connected: true } }));
  }

  getBleWriteMode(characteristic = this.bluetoothCharacteristic) {
    const properties = characteristic?.properties;
    if (
      properties?.writeWithoutResponse
      && typeof characteristic.writeValueWithoutResponse === 'function'
    ) {
      return 'without-response';
    }
    if (
      properties?.write
      && typeof characteristic.writeValueWithResponse === 'function'
    ) {
      return 'with-response';
    }
    if (
      (properties?.write || properties?.writeWithoutResponse)
      && typeof characteristic.writeValue === 'function'
    ) {
      return 'legacy';
    }
    return null;
  }

  async setLed(color) {
    if (!this.bluetoothCharacteristic) {
      throw new Error('먼저 Meem 블루투스를 연결해 주세요.');
    }
    const commands = { red: 'R', green: 'G', blue: 'B', off: 'X' };
    const command = commands[color];
    if (!command) throw new Error('지원하지 않는 LED 색상입니다.');
    const payload = new TextEncoder().encode(command);
    const writeMode = this.getBleWriteMode();
    if (writeMode === 'without-response') {
      await this.bluetoothCharacteristic.writeValueWithoutResponse(payload);
    } else if (writeMode === 'with-response') {
      await this.bluetoothCharacteristic.writeValueWithResponse(payload);
    } else if (writeMode === 'legacy') {
      await this.bluetoothCharacteristic.writeValue(payload);
    } else {
      throw new Error('Meem FFE1 특성이 BLE 쓰기를 지원하지 않습니다.');
    }
    this.dispatchEvent(new CustomEvent('led', { detail: { color } }));
  }
}

window.PetDockBridge = PetDockBridge;
