import { InstanceBase, runEntrypoint, TCPHelper } from '@companion-module/base'
import { updateActions } from './actions.js'

class DeclinedCommandsNotStatic extends InstanceBase {
  async init(config) {
    this.socket = new TCPHelper(config.host, config.port)
    this.updateActions = updateActions.bind(this)
    this.updateActions()
  }
}

runEntrypoint(DeclinedCommandsNotStatic)
