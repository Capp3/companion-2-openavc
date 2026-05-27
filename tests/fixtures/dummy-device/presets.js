export function updatePresets() {
  this.setPresetDefinitions({
    mute: {
      type: 'button',
      category: 'Device',
      name: 'Mute',
      style: { text: 'MUTE', size: '14', color: 0xffffff, bgcolor: 0xff0000 },
      steps: [{ down: [{ actionId: 'toggle_mute', options: {} }], up: [] }],
    },
  })
}
