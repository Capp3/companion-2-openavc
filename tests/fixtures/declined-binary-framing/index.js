import { InstanceBase, runEntrypoint, TCPHelper } from '@companion-module/base'

class DeclinedBinaryFraming extends InstanceBase {
  async init(config) {
    this.socket = new TCPHelper(config.host, config.port)
    this.socket.on('data', (chunk) => {
      const frame = Buffer.alloc(4)
      frame.writeUInt16BE(chunk.length, 0)
      this.socket.send(frame)
    })
  }
}

runEntrypoint(DeclinedBinaryFraming)
