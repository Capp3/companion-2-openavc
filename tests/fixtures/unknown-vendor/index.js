import { InstanceBase, TCPHelper, runEntrypoint } from '@companion-module/base'

class UnknownVendorDevice extends InstanceBase {
  async init(config) {
    this.config = config
    this.socket = new TCPHelper(config.host, config.port)
  }
}

runEntrypoint(UnknownVendorDevice)
