export function updateVariables() {
	let variables = []

	variables.push(
		{
			name: 'Device Model',
			variableId: 'model',
		},
		{
			name: 'Device Label',
			variableId: 'label',
		},
		{
			name: 'Device Software',
			variableId: 'software',
		},
		{
			name: 'Video Mode',
			variableId: 'video_mode',
		},
		{
			name: 'Platform',
			variableId: 'platform',
		},
		{
			name: 'Server',
			variableId: 'server',
		},
		{
			name: 'Stream Key',
			variableId: 'key',
		},
		{
			name: 'Stream Quality',
			variableId: 'quality',
		},
		{
			name: 'Streaming State',
			variableId: 'stream_state',
		},
		{
			name: 'Streaming Duration',
			variableId: 'stream_duration',
		},
		{
			name: 'Streaming Duration (Hours)',
			variableId: 'stream_duration_HH',
		},
		{
			name: 'Streaming Duration (Minutes)',
			variableId: 'stream_duration_MM',
		},
		{
			name: 'Streaming Duration (Seconds)',
			variableId: 'stream_duration_SS',
		},
		{
			name: 'Stream Bitrate',
			variableId: 'stream_bitrate',
		},
		{
			name: 'Cache Used',
			variableId: 'cache',
		},
		{
			name: 'Passphrase',
			variableId: 'passphrase',
		},
		{
			name: 'Current URL',
			variableId: 'URL',
		}
	)

	this.setVariableDefinitions(variables)
}
