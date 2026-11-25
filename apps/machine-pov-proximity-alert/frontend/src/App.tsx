import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Card, Label } from '@luxonis/ui-components';
import { useEffect, useRef } from 'react';
import { AppShell } from './AppShell.tsx';
import SettingsForm from './settings/SettingsForm.tsx';

const STREAM_PANEL_ORDER = [
	'Annotations',
	'Video',
	'Occupancy Grid',
	'Support Plane Status',
	'Point Cloud',
];
const DEFAULT_TOPICS = new Set(STREAM_PANEL_ORDER);
const TOPIC_GROUPS = {
	Video: 'preview',
	Annotations: 'preview',
	'Occupancy Grid': 'grid',
	'Support Plane Status': 'grid',
	'Point Cloud': 'pcl',
};

const getStreamPanelOrder = (topicName: string) => {
	const order = STREAM_PANEL_ORDER.indexOf(topicName);
	return order === -1 ? Number.MAX_SAFE_INTEGER : order;
};

const sortTopics = (a: { name: string }, b: { name: string }) =>
	getStreamPanelOrder(a.name) - getStreamPanelOrder(b.name);

function LiveStreams() {
	const { connected, topics, toggleTopic } = useDaiConnection();
	const opened = useRef(new Set<string>());

	useEffect(() => {
		if (!connected) {
			opened.current.clear();
			return;
		}
		for (const topic of topics) {
			if (!DEFAULT_TOPICS.has(topic.name) || opened.current.has(topic.name))
				continue;
			opened.current.add(topic.name);
			if (!topic.enabled) toggleTopic(topic.name);
		}
	}, [connected, topics, toggleTopic]);

	return (
		<Streams
			topicGroups={TOPIC_GROUPS}
			numberOfColumns={2}
			topicSortingFunction={sortTopics}
		/>
	);
}

function App() {
	return (
		<AppShell
			title="Machine-Mounted Person Proximity Alert"
			streams={<LiveStreams />}
		>
			<Card title="About" variant="outline" intent="white">
				<div className="flex flex-col gap-2">
					<Label text="Proximity alerts from a camera mounted on a machine. Set the warning and danger areas for the machine's view; people entering them appear in the live annotations. Optional generic detection also shows obstacles above the support plane." />
					<Label text="Point cloud: orange = warning zone, red = danger zone." />
				</div>
			</Card>
			<SettingsForm />
		</AppShell>
	);
}

export default App;
