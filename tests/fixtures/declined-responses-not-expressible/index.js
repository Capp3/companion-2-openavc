import { InstanceBase, runEntrypoint, TCPHelper } from '@companion-module/base'

class DeclinedResponsesNotExpressible extends InstanceBase {
  async init(config) {
    this.socket = new TCPHelper(config.host, config.port)
    this.parserState = 'header'
    this.socket.on('data', (chunk) => {
      switch (this.parserState) {
        case 'header':
          this.parserState = 'payload'
          break
        case 'payload':
          this.parserState = 'header'
          break
      }
    })
  }
}

runEntrypoint(DeclinedResponsesNotExpressible)
