import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button } from '@luxonis/ui-components';
import { useMemo, useRef } from 'react';
import { ClassSelector } from './ClassSelector.tsx';
import { ClickCatcher } from './ClickOverlay.tsx';
import { ConfidenceSlider } from './ConfidenceSlider.tsx';
import { MeasurementMethodSelector } from './MeasurementMethodSelector.tsx';
import { TopBar } from './TopBar.tsx';
import { postToObjectVolumeService } from './services.ts';

function App() {
	const connection = useDaiConnection();
	const viewerRef = useRef<HTMLDivElement>(null);
	const topicGroups = useMemo(
		() => ({ images: 'Images', point_clouds: 'Pointclouds' }),
		[],
	);

	const clearSelection = () => {
		postToObjectVolumeService(connection.daiConnection, 'Selection Service', {
			clear: true,
		});
	};

	return (
		<main className="flex h-screen w-screen flex-row gap-6 overflow-auto bg-muted p-6">
			<div className="flex min-w-[760px] flex-1 shrink-0 flex-col overflow-hidden rounded-md border border-border bg-background shadow-sm">
				<TopBar />

				<div ref={viewerRef} className="relative min-h-0 flex-1">
					<Streams
						defaultTopics={['Video', 'Pointclouds']}
						topicGroups={topicGroups}
					/>

					<ClickCatcher
						containerRef={viewerRef}
						frameWidth={640}
						frameHeight={400}
						allowedPanelTitle="Video"
					/>
				</div>
			</div>

			<div className="w-0.5 shrink-0 bg-border" />

			<aside className="flex max-h-full w-[420px] min-w-[360px] shrink-0 flex-col gap-5 overflow-y-auto pr-2 text-left">
				<h1 className="text-2xl font-bold">Object Volume Measurement 3D</h1>
				<p className="text-sm leading-6 text-muted-foreground">
					This example combines a YOLOE segmentation model with DepthAI point
					clouds to measure real-world objects in 3D. Click any detected object
					in the Video panel to segment it and get its dimensions and volume.
				</p>

				<ClassSelector />
				<ConfidenceSlider initialValue={0.15} />

				<Button className="w-fit" variant="outline" onClick={clearSelection}>
					Clear selected object
				</Button>

				<MeasurementMethodSelector />

				<div
					className={`mt-auto flex items-center gap-2 border-t border-border pt-4 text-sm ${
						connection.connected ? 'text-success' : 'text-destructive'
					}`}
				>
					<div
						className={`h-3 w-3 rounded-full ${
							connection.connected ? 'bg-success' : 'bg-destructive'
						}`}
					/>
					<span>
						{connection.connected ? 'Connected to device' : 'Disconnected'}
					</span>
				</div>
			</aside>
		</main>
	);
}

export default App;
