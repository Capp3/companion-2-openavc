import { InstanceBase, runEntrypoint, TCPHelper } from '@companion-module/base'

class DeclinedAuthNonTelnet extends InstanceBase {
  async init(config) {
    this.socket = new TCPHelper(config.host, config.port)
    this.socket.on('connect', () => {
      this.socket.send(`LOGIN ${config.username} ${config.password}\n`)
    })
  }
}

runEntrypoint(DeclinedAuthNonTelnet)
