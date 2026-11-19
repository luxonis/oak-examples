import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { cn } from '@luxonis/ui-components';
import { useEffect, useRef } from 'react';
import { TopBar } from './TopBar.tsx';
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
	const { connected } = useDaiConnection();

	return (
		<main className="flex h-screen w-screen flex-row gap-6 overflow-auto bg-background p-6 text-foreground">
			<div className="flex min-w-[760px] flex-1 shrink-0 flex-col overflow-hidden rounded-md border border-border bg-background shadow-sm">
				<TopBar />
				<div className="relative min-h-0 flex-1">
					<LiveStreams />
				</div>
				<p className="px-4 pt-2 pb-3 text-xs text-muted-foreground">
					Point cloud: orange = warning zone, red = danger zone.
				</p>
			</div>

			<div className="w-0.5 shrink-0 bg-border" />

			<aside className="flex max-h-full w-[420px] min-w-[360px] shrink-0 flex-col gap-5 text-left">
				<div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto pr-2">
					<h1 className="text-2xl font-bold">
						Machine-Mounted Person Proximity Alert
					</h1>
					<p className="text-sm leading-6 text-muted-foreground">
						Proximity alerts from a camera mounted on a machine. Set the warning
						and danger areas for the machine&apos;s view; people entering them
						appear in the live annotations. Optional generic detection also
						shows obstacles above the support plane.
					</p>
					<SettingsForm />
				</div>

				<div
					className={cn(
						'mr-2 flex shrink-0 items-center gap-2 border-t border-border pt-4 text-sm',
						connected ? 'text-success' : 'text-destructive',
					)}
				>
					<div
						className={cn(
							'h-3 w-3 rounded-full',
							connected ? 'bg-success' : 'bg-destructive',
						)}
					/>
					<span>{connected ? 'Connected to device' : 'Disconnected'}</span>
				</div>
			</aside>
		</main>
	);
}

export default App;
