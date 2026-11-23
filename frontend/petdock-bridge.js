class PetDockBridge extends EventTarget {
  static BLE_SERVICE = '0000ffe0-0000-1000-8000-00805f9b34fb';
  static BLE_CHARACTERISTIC = '0000ffe1-0000-1000-8000-00805f9b34fb';

  constructor() {
    super();
    this.serialPort = null;
    this.serialReader = null;
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

    await this.disconnectUsb();
    this.serialPort = await navigator.serial.requestPort();
    await this.serialPort.open({ baudRate: 9600 });
    this.dispatchEvent(new CustomEvent('usbstate', { detail: { connected: true } }));
    this.readSerial().catch((error) => {
      this.dispatchEvent(new CustomEvent('error', { detail: { message: error.message } }));
    });
  }

  async readSerial() {
    const decoder = new TextDecoderStream();
    const readableClosed = this.serialPort.readable.pipeTo(decoder.writable);
    this.serialReader = decoder.readable.getReader();
    let pending = '';

    try {
      while (true) {
        const { value, done } = await this.serialReader.read();
        if (done) break;
        pending += value;
        const lines = pending.split(/\r?\n/);
        pending = lines.pop() || '';
        lines.forEach((line) => this.handleSerialLine(line.trim()));
      }
    } finally {
      this.serialReader.releaseLock();
      this.serialReader = null;
      await readableClosed.catch(() => {});
    }
  }

  handleSerialLine(line) {
    if (line !== 'BTN_A' && line !== 'BTN_B') return;
    this.dispatchEvent(new CustomEvent('button', {
      detail: { button: line === 'BTN_A' ? 'A' : 'B', raw: line },
    }));
  }

  async disconnectUsb() {
    if (this.serialReader) await this.serialReader.cancel().catch(() => {});
    if (this.serialPort) await this.serialPort.close().catch(() => {});
    if (this.serialPort) {
      this.dispatchEvent(new CustomEvent('usbstate', { detail: { connected: false } }));
    }
    this.serialPort = null;
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
    this.bluetoothCharacteristic = await service.getCharacteristic(PetDockBridge.BLE_CHARACTERISTIC);
    this.dispatchEvent(new CustomEvent('blestate', { detail: { connected: true } }));
  }

  async setLed(color) {
    if (!this.bluetoothCharacteristic) {
      throw new Error('먼저 Meem 블루투스를 연결해 주세요.');
    }
    const commands = { red: 'R', green: 'G', blue: 'B', off: 'X' };
    const command = commands[color];
    if (!command) throw new Error('지원하지 않는 LED 색상입니다.');
    const payload = new TextEncoder().encode(command);
    if ('writeValueWithoutResponse' in this.bluetoothCharacteristic) {
      await this.bluetoothCharacteristic.writeValueWithoutResponse(payload);
    } else {
      await this.bluetoothCharacteristic.writeValue(payload);
    }
    this.dispatchEvent(new CustomEvent('led', { detail: { color } }));
  }
}

window.PetDockBridge = PetDockBridge;
