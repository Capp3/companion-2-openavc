export function updateActions() {
  this.setActionDefinitions({
    nonce_command: {
      name: 'Nonce Command',
      options: [],
      callback: async () => {
        const nonce = Date.now()
        this.socket.send(`RUN ${nonce}\n`)
      },
    },
  })
}
