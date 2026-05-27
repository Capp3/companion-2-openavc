import { InstanceBase, runEntrypoint, UDPHelper } from '@companion-module/base'

class DeclinedUdp extends InstanceBase {
  async init(config) {
    this.config = config
    this.socket = new UDPHelper(config.host, config.port)
  }
}

runEntrypoint(DeclinedUdp)
