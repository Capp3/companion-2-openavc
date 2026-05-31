import { InstanceBase, Regex, runEntrypoint, TCPHelper } from '@companion-module/base'

class StaticOnConnect extends InstanceBase {
  getConfigFields() {
    return [
      {
        type: 'textinput',
        id: 'host',
        label: 'Host',
        regex: Regex.IP,
        default: '10.0.0.1',
      },
      {
        type: 'textinput',
        id: 'port',
        label: 'Port',
        regex: Regex.Port,
        default: '6000',
      },
    ]
  }

  async init(config) {
    this.config = config
    this.socket = new TCPHelper(config.host, config.port)
    this.socket.on('connect', () => {
      this.socket.send('HELLO\n')
      this.socket.send('INIT\n')
    })
    this.socket.on('data', (_chunk) => {})
  }
}

runEntrypoint(StaticOnConnect)
