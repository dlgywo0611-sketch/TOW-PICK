// PET DOCK bridge for TWO PICK
class PetDockBridge extends EventTarget {
  static BLE_SERVICE = '0000ffe0-0000-1000-8000-00805f9b34fb';
  static BLE_CHARACTERISTIC = '0000ffe1-0000-1000-8000-00805f9b34fb';

  constructor({ dedupeWindowMs = 150, now = () => Date.now() } = {}) {
    super();
    this.serialPort = null;
    this.serialReader = null;
    this._usbReadTask = null;
    this._usbClosing = false;
    this.bluetoothDevice = null;
    this.bluetoothCharacteristic = null;
    this.bleNotifyActive = false;
    this._bleDecoder = new TextDecoder();
    this._blePending = '';
    this._onGattDisconnected = this._handleGattDisconnected.bind(this);
    this._onBleValueChanged = this._handleBleValueChanged.bind(this);
    this._dedupeWindowMs = dedupeWindowMs;
    this._now = now;
    this._lastButton = null;
    this.buttonCounts = { total: 0, A: 0, B: 0 };
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
    this._emitButton(line, 'USB');
  }

  _emitButton(raw, source) {
    if (raw !== 'BTN_A' && raw !== 'BTN_B') return false;
    const button = raw === 'BTN_A' ? 'A' : 'B';
    const timestamp = this._now();
    const duplicate = this._lastButton
      && this._lastButton.button === button
      && this._lastButton.source !== source
      && timestamp - this._lastButton.timestamp <= this._dedupeWindowMs;
    if (duplicate) return false;

    this._lastButton = { button, source, timestamp };
    this.buttonCounts.total += 1;
    this.buttonCounts[button] += 1;
    this.dispatchEvent(new CustomEvent('button', {
      detail: {
        button,
        raw,
        source,
        count: this.buttonCounts.total,
        counts: { A: this.buttonCounts.A, B: this.buttonCounts.B },
      },
    }));
    return true;
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

    const device = await navigator.bluetooth.requestDevice({
      filters: [{ name: 'Meem' }],
      optionalServices: [PetDockBridge.BLE_SERVICE],
    });
    this._clearBluetoothState(true);
    this.bluetoothDevice = device;
    device.addEventListener('gattserverdisconnected', this._onGattDisconnected);

    let server;
    try {
      server = await device.gatt.connect();
      const service = await server.getPrimaryService(PetDockBridge.BLE_SERVICE);
      const characteristic = await service.getCharacteristic(PetDockBridge.BLE_CHARACTERISTIC);
      if (!this.getBleWriteMode(characteristic)) {
        throw new Error('Meem FFE1 특성이 BLE 쓰기를 지원하지 않습니다.');
      }

      this.bluetoothCharacteristic = characteristic;
      const notifySupported = this.supportsBleNotify(characteristic);
      let notifyError = null;
      if (notifySupported) {
        characteristic.addEventListener('characteristicvaluechanged', this._onBleValueChanged);
        try {
          await characteristic.startNotifications();
          this.bleNotifyActive = true;
        } catch (error) {
          characteristic.removeEventListener('characteristicvaluechanged', this._onBleValueChanged);
          notifyError = error.message || 'Notify 시작 실패';
        }
      }

      const detail = {
        connected: true,
        notifySupported,
        notifyActive: this.bleNotifyActive,
        notifyError,
      };
      this.dispatchEvent(new CustomEvent('blestate', { detail }));
      return detail;
    } catch (error) {
      if (server?.connected) server.disconnect();
      this._clearBluetoothState(false);
      throw error;
    }
  }

  supportsBleNotify(characteristic = this.bluetoothCharacteristic) {
    const properties = characteristic?.properties;
    return Boolean(
      (properties?.notify || properties?.indicate)
      && typeof characteristic.startNotifications === 'function'
      && typeof characteristic.addEventListener === 'function',
    );
  }

  _handleBleValueChanged(event) {
    if (event.target !== this.bluetoothCharacteristic || !event.target?.value) return;
    const value = event.target.value;
    const bytes = value.buffer
      ? new Uint8Array(value.buffer, value.byteOffset || 0, value.byteLength)
      : new Uint8Array(value);
    this._blePending += this._bleDecoder.decode(bytes, { stream: true });

    const matches = [...this._blePending.matchAll(/BTN_[AB]/g)];
    matches.forEach((match) => this._emitButton(match[0], 'BLE'));
    if (matches.length) {
      const last = matches[matches.length - 1];
      this._blePending = this._blePending.slice(last.index + last[0].length);
    }
    this._blePending = this._blePending.replace(/^[\r\n\s]+/, '');
    if (this._blePending.length > 16) this._blePending = this._blePending.slice(-4);
  }

  _handleGattDisconnected(event) {
    if (event.target !== this.bluetoothDevice) return;
    this._clearBluetoothState(false);
    this.dispatchEvent(new CustomEvent('blestate', {
      detail: { connected: false, notifySupported: null, notifyActive: false, notifyError: null },
    }));
  }

  _clearBluetoothState(disconnect = true) {
    const device = this.bluetoothDevice;
    const characteristic = this.bluetoothCharacteristic;
    if (characteristic?.removeEventListener) {
      characteristic.removeEventListener('characteristicvaluechanged', this._onBleValueChanged);
    }
    if (device?.removeEventListener) {
      device.removeEventListener('gattserverdisconnected', this._onGattDisconnected);
    }
    this.bluetoothCharacteristic = null;
    this.bluetoothDevice = null;
    this.bleNotifyActive = false;
    this._blePending = '';
    this._bleDecoder = new TextDecoder();
    if (disconnect && device?.gatt?.connected) device.gatt.disconnect();
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
