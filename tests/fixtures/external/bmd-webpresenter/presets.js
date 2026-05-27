import { combineRgb } from '@companion-module/base'

export function updatePresets() {
	let presets = {}

	presets['Start'] = {
		type: 'button',
		category: 'Streaming',
		name: 'Start Stream',
		style: {
			text: 'Start Stream',
			size: 'auto',
			bgcolor: combineRgb(0, 0, 0),
			color: combineRgb(255, 255, 255),
		},
		steps: [
			{
				down: [
					{
						actionId: 'stream',
						options: {
							stream_control: 'Start',
						},
					},
				],
				up: [],
			},
		],
		feedbacks: [
			{
				feedbackId: 'streaming_state',
				options: {
					stream_state: 'Idle',
				},
				style: {
					bgcolor: combineRgb(0, 0, 0),
					color: combineRgb(255, 255, 255),
				},
			},
			{
				feedbackId: 'streaming_state',
				options: {
					stream_state: 'Connecting',
				},
				style: {
					bgcolor: combineRgb(255, 128, 0),
					color: combineRgb(255, 255, 255),
				},
			},
			{
				feedbackId: 'streaming_state',
				options: {
					stream_state: 'Streaming',
				},
				style: {
					bgcolor: combineRgb(0, 204, 0),
					color: combineRgb(255, 255, 255),
				},
			},
		],
	}

	presets['Stop'] = {
		type: 'button',
		category: 'Streaming',
		name: 'Stop Stream',
		style: {
			text: 'Stop Stream',
			size: 'auto',
			bgcolor: combineRgb(0, 0, 0),
			color: combineRgb(255, 255, 255),
		},
		steps: [
			{
				down: [
					{
						actionId: 'stream',
						options: {
							stream_control: 'Stop',
						},
					},
				],
				up: [],
			},
		],
		feedbacks: [],
	}

	presets['Reboot'] = {
		type: 'button',
		category: 'Device',
		name: 'Reboot WebPresenter',
		style: {
			text: 'Reboot',
			size: 'auto',
			bgcolor: combineRgb(0, 0, 0),
			color: combineRgb(255, 255, 255),
		},
		steps: [
			{
				down: [
					{
						actionId: 'device',
						options: {
							device_control: 'Reboot',
						},
					},
				],
				up: [],
			},
		],
		feedbacks: [],
	}

	this.setPresetDefinitions(presets)
}
