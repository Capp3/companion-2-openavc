import { combineRgb } from '@companion-module/base'

export function updateFeedbacks() {
	let feedbacks = {}

	feedbacks['streaming_state'] = {
		type: 'boolean',
		name: 'Device is streaming',
		description: 'Change background colour based on streaming state',
		defaultStyle: {
			color: combineRgb(0, 0, 0),
			bgcolor: combineRgb(0, 204, 0),
		},
		options: [
			{
				type: 'dropdown',
				label: 'State',
				id: 'stream_state',
				default: 'Streaming',
				choices: [
					{ id: 'Idle', label: 'Idle' },
					{ id: 'Connecting', label: 'Connecting' },
					{ id: 'Streaming', label: 'Streaming' },
					{ id: 'Interrupted', label: 'Interrupted' },
				],
			},
		],
		callback: ({ options }) => {
			console.log('update feedback status: ' + this.streaming)
			if (this.streaming === options.stream_state) {
				return true
			} else {
				return false
			}
		},
	}
	this.setFeedbackDefinitions(feedbacks)
}
