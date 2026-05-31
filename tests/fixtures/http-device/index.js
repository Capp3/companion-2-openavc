import { InstanceBase, Regex, runEntrypoint } from '@companion-module/base'

class HttpDevice extends InstanceBase {
  getConfigFields() {
    return [
      {
        type: 'textinput',
        id: 'host',
        label: 'Host',
        regex: Regex.IP,
        default: '192.168.1.20',
      },
      {
        type: 'textinput',
        id: 'port',
        label: 'Port',
        regex: Regex.Port,
        default: '80',
      },
    ]
  }

  init(config) {
    this.config = config
    this.updateActions()
  }

  updateActions() {
    this.setActionDefinitions({
      get_status: {
        name: 'Get Status',
        options: [
          {
            type: 'dropdown',
            id: 'include',
            label: 'Include',
            choices: [
              { id: 'summary', label: 'Summary' },
              { id: 'details', label: 'Details' },
            ],
            tooltip: 'Select status detail level.',
          },
        ],
        callback: async (event) => {
          await fetch('/api/status?include=' + event.options.include)
        },
      },
      post_event: {
        name: 'Post Event',
        options: [
          {
            type: 'textinput',
            id: 'name',
            label: 'Name',
          },
        ],
        callback: async (event) => {
          await fetch('/api/event', {
            method: 'POST',
            body: JSON.stringify({ name: event.options.name }),
          })
        },
      },
      send_xml: {
        name: 'Send XML',
        options: [
          {
            type: 'textinput',
            id: 'value',
            label: 'Value',
          },
        ],
        callback: async (event) => {
          await fetch('/api/payload', {
            method: 'POST',
            body: '<msg>' + event.options.value + '</msg>',
          })
        },
      },
    })
  }
}

runEntrypoint(HttpDevice)
