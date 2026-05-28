import { InstanceBase, runEntrypoint } from '@companion-module/base'

class DeclinedTransportUnknown extends InstanceBase {
  async init(config) {
    this.config = config
    this.updateStatus('ok')
  }
}

runEntrypoint(DeclinedTransportUnknown)
