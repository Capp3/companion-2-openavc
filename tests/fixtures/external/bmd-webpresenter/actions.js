export function updateActions() {
	let actions = {}

	actions['stream'] = {
		name: 'Streaming Control',
		options: [
			{
				type: 'dropdown',
				label: 'State',
				id: 'stream_control',
				default: 'Start',
				choices: [
					{ id: 'Start', label: 'Start' },
					{ id: 'Stop', label: 'Stop' },
					{ id: 'Toggle', label: 'Toggle' },
				],
			},
		],
		callback: ({ options }) => {
			var cmd = 'STREAM STATE:\nAction: '
			if (options.stream_control === 'Toggle') {
				if (this.streaming === 'Streaming' || this.streaming === 'Connecting') {
					cmd = cmd + 'Stop\n\n'
				} else {
					cmd = cmd + 'Start\n\n'
				}
			} else {
				cmd = cmd + options.stream_control + '\n\n'
			}
			this.sendCommand(cmd)
		},
	}

	actions['stream_settings'] = {
		name: 'Stream Settings',
		options: [
			{
				type: 'dropdown',
				label: 'Video Mode',
				id: 'video_mode',
				default: 'Auto',
				choices: this.formats,
			},
			{
				type: 'dropdown',
				label: 'Platform',
				id: 'platform',
				choices: this.platforms,
			},
			{
				type: 'textinput',
				label: 'Server',
				id: 'server',
				default: '',
				useVariables: true,
				tooltip:
					'Depends on platform.\nRefer to Blackmagic Web Presenter desktop application for possible options. You may use Companion variables.',
			},
			{
				type: 'textinput',
				label: 'Stream Key',
				id: 'key',
				default: '',
				useVariables: true,
				tooltip: 'Provided by the streaming platform. You may use Companion variables.',
			},
			{
				type: 'dropdown',
				label: 'Quality',
				id: 'quality',
				default: 'Streaming Medium',
				choices: this.quality,
			},
		],
		callback: async (action, context) => {
			if (action.options.server == '') {
				this.log('warn', 'Server parameter is missing from Stream Settings')
			}
			if (action.options.key == '') {
				this.log('warn', 'Stream Key parameter is missing from Stream Settings')
			}

			var server = await context.parseVariablesInString(action.options.server)
			var key = await context.parseVariablesInString(action.options.key)
			
			if (server == '' && action.options.platform == 'Facebook') {
				server = 'Default'
			}

			var cmd =
				'STREAM SETTINGS:\nVideo Mode: ' +
				action.options.video_mode +
				'\n' +
				'Current Platform: ' +
				action.options.platform +
				'\n' +
				'Current Server: ' +
				server +
				'\n' +
				'Current Quality Level: ' +
				action.options.quality +
				'\n' +
				'Stream Key: ' +
				key +
				'\n\n'

			this.sendCommand(cmd)
		},
	}

	actions['youtube_settings'] = {
		name: 'YouTube Simple Settings',
		options: [
			{
				type: 'static-text',
				label: 'All settings are set to YouTube defaults except for the Stream Key',
				id: 'info',
			},
			{
				type: 'textinput',
				label: 'Stream Key',
				id: 'key',
				default: '',
				useVariables: true,
				tooltip: 'Enter the Stream Key from your YouTube creator studio. You may use Companion variables.',
			},
		],
		callback: async (action, context) => {
			// find a suitable YouTube platform from available options
			var platform = 'YouTube'
			const checkRTMP = (obj) => obj.label === 'YouTube RTMP'
			if (this.platforms.some(checkRTMP) == true) {
				// changed in WebPresenter 3.3
				platform = 'YouTube RTMP'
			}

			const key = await context.parseVariablesInString(action.options.key)

			var cmd =
				'STREAM SETTINGS:\nVideo Mode: ' +
				'Auto' +
				'\n' +
				'Current Platform: ' +
				platform +
				'\n' +
				'Current Server: ' +
				'Primary' +
				'\n' +
				'Current Quality Level: ' +
				'Streaming Medium' +
				'\n' +
				'Stream Key: ' +
				key +
				'\n\n'

			this.sendCommand(cmd)
		},
	}

	actions['custom_settings'] = {
		name: 'Custom URL H.264/H.265 Settings',
		options: [
			{
				type: 'dropdown',
				label: 'Platform',
				id: 'platform',
				choices: this.customPlatforms,
			},
			{
				type: 'dropdown',
				label: 'Video Mode',
				id: 'video_mode',
				default: 'Auto',
				choices: this.formats,
			},
			{
				type: 'textinput',
				label: 'Custom URL',
				id: 'customURL',
				default: '',
				useVariables: true,
				tooltip: 'Enter the URL of the custom server. You may use Companion variables.',
			},
			{
				type: 'textinput',
				label: 'Stream Key',
				id: 'key',
				default: '',
				useVariables: true,
				tooltip: 'Enter the stream key of the custom server. You may use Companion variables.',
			},
			{
				type: 'dropdown',
				label: 'Quality',
				id: 'quality',
				default: 'Streaming Medium',
				choices: this.quality,
			},
		],
		callback: async (action, context) => {
			const url = await context.parseVariablesInString(action.options.customURL)
			const key = await context.parseVariablesInString(action.options.key)

			var cmd =
				'STREAM SETTINGS:\nVideo Mode: ' +
				action.options.video_mode +
				'\n' +
				'Current Platform:' +
				action.options.platform +
				'\n' +
				'Current Server: Custom' +
				'\n' +
				'Current Quality Level: ' +
				action.options.quality +
				'\n' +
				'Current URL:' +
				url +
				'\n' +
				'Stream Key: ' +
				key +
				'\n\n'

			this.sendCommand(cmd)
		},
	}

	actions['device'] = {
		name: 'Device Control',
		options: [
			{
				type: 'dropdown',
				label: 'State',
				id: 'device_control',
				default: 'Reboot',
				choices: [
					{ id: 'Reboot', label: 'Reboot' },
					{ id: 'Factory Reset', label: 'Factory Reset' },
				],
			},
		],
		callback: ({ options }) => {
			var cmd = 'SHUTDOWN:\nAction: ' + options.device_control + '\n\n'
			this.sendCommand(cmd)
		},
	}

	actions['videoMode'] = {
		name: 'Change Video Mode',
		options: [
			{
				type: 'dropdown',
				label: 'Video Mode',
				id: 'video_mode',
				default: 'Auto',
				choices: this.formats,
			},
		],
		callback: ({ options }) => {
			var cmd = 'STREAM SETTINGS:\nVideo Mode: ' + options.video_mode + '\n\n'
			this.sendCommand(cmd)
		},
	}

	actions['videoQuality'] = {
		name: 'Change Video Quality',
		options: [
			{
				type: 'dropdown',
				label: 'Quality',
				id: 'quality',
				default: 'Streaming Medium',
				choices: this.quality,
			},
		],
		callback: ({ options }) => {
			var cmd = 'STREAM SETTINGS:\nCurrent Quality Level: ' + options.quality + '\n\n'
			this.sendCommand(cmd)
		},
	}

	actions['streamKey'] = {
		name: 'Change Stream Key',
		options: [
			{
				type: 'textinput',
				label: 'Stream Key',
				id: 'key',
				default: '',
				useVariables: true,
				tooltip: 'Enter the Stream Key. You may use Companion variables.',
			},
		],
		callback: async (action, context) => {
			const key = await context.parseVariablesInString(action.options.key)

			var cmd = 'STREAM SETTINGS:\nStream Key: ' + key + '\n\n'

			this.sendCommand(cmd)
		},
	}
	
	actions['passphrase'] = {
		name: 'Change SRT Passphrase',
		options: [
			{
				type: 'textinput',
				label: 'Passphrase',
				id: 'passphrase',
				default: '',
				useVariables: true,
				tooltip: 'You may use Companion variables.',
			},
		],
		callback: async (action, context) => {
			const pass = await context.parseVariablesInString(action.options.passphrase)
	
			var cmd = 'STREAM SETTINGS:\nPassword: ' + pass + '\n\n'
	
			this.sendCommand(cmd)
		},
	}

	this.setActionDefinitions(actions)
}
