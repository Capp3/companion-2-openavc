export function updateActions() {
  this.setActionDefinitions({
    set_input: {
      name: 'Set Input',
      options: [
        {
          type: 'number',
          id: 'input',
          label: 'Input',
          default: 1,
          min: 1,
          max: 8,
        },
      ],
      callback: async (event) => {
        const cmd = `SET INPUT ${event.options.input}\n`
        this.socket.send(cmd)
      },
    },
    stream: {
      name: 'Stream',
      options: [
        {
          type: 'dropdown',
          id: 'action',
          label: 'Action',
          default: 'start',
          choices: [
            { id: 'start', label: 'Start' },
            { id: 'stop', label: 'Stop' },
          ],
        },
      ],
      callback: async (event) => {
        if (event.options.action === 'start') {
          this.socket.send('STREAM START\n')
        } else if (event.options.action === 'stop') {
          this.socket.send('STREAM STOP\n')
        }
      },
    },
    toggle_mute: {
      name: 'Toggle Mute',
      options: [],
      callback: async () => {
        if (this.mute) {
          this.socket.send('MUTE OFF\n')
        } else {
          this.socket.send('MUTE ON\n')
        }
      },
    },
    configure: {
      name: 'Configure',
      options: [
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
        {
          type: 'textinput',
          id: 'label',
          label: 'Label',
          default: 'Main',
        },
      ],
      callback: async (event) => {
        const cmd = `CFG ${event.options.mode} ${event.options.label}\n`
        this.socket.send(cmd)
      },
    },
  })
}
