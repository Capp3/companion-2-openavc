import { InstanceBase, Regex, runEntrypoint, TCPHelper } from '@companion-module/base'
import { updateActions } from './actions.js'
import { updateVariables } from './variables.js'
import { updateFeedbacks } from './feedback.js'
import { updatePresets } from './presets.js'

class DummyDevice extends InstanceBase {
  constructor(internal) {
    super(internal)
    this.updateActions = updateActions.bind(this)
    this.updateVariables = updateVariables.bind(this)
    this.updateFeedbacks = updateFeedbacks.bind(this)
    this.updatePresets = updatePresets.bind(this)
  }

  getConfigFields() {
    return [
      {
        type: 'static-text',
        id: 'info',
        label: 'Information',
        value: 'Dummy device for C2O extractor coverage.',
      },
      {
        type: 'textinput',
        id: 'host',
        label: 'Host',
        regex: Regex.IP,
        default: '192.168.1.10',
      },
      {
        type: 'textinput',
        id: 'port',
        label: 'Port',
        regex: Regex.Port,
        default: '5000',
      },
      {
        type: 'number',
        id: 'poll_interval',
        label: 'Poll interval (sec)',
        default: 5,
        min: 1,
        max: 60,
      },
      {
        type: 'checkbox',
        id: 'verbose',
        label: 'Verbose logging',
        default: false,
      },
      {
        type: 'dropdown',
        id: 'mode',
        label: 'Mode',
        default: 'auto',
        choices: [
          { id: 'auto', label: 'Auto' },
          { id: 'manual', label: 'Manual' },
        ],
      },
    ]
  }

  async init(config) {
    this.config = config
    this.socket = new TCPHelper(config.host, config.port)

    this.socket.on('data', (chunk) => {
      const lines = chunk.toString().split('\n')
      for (const line of lines) {
        this.parseLine(line)
      }
    })

    this.socket.on('receiveline', (line) => {
      const match = line.match(/INPUT=(\d+)/)
      if (match) {
        this.setVariableValues({ input_level: parseInt(match[1], 10) })
      }
    })

    this.updateActions()
    this.updateVariables()
    this.updateFeedbacks()
    this.updatePresets()

    this.timer = setInterval(() => {
      this.socket.send('QUERY INPUT\n')
      this.socket.send('QUERY MUTE\n')
    }, (config.poll_interval || 5) * 1000)
  }

  parseLine(line) {
    if (line.startsWith('MUTE=')) {
      this.setVariableValues({ mute_state: line.includes('ON') })
    }
    if (line.startsWith('LABEL=')) {
      this.setVariableValues({ device_label: line.slice(6).trim() })
    }
  }
}

runEntrypoint(DummyDevice)
