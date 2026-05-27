export function updateFeedbacks() {
  this.setFeedbackDefinitions({
    mute_on: {
      type: 'boolean',
      name: 'Mute is on',
      defaultStyle: { bgcolor: 0xff0000 },
      options: [],
      callback: (feedback) => this.mute_state,
    },
  })
}
