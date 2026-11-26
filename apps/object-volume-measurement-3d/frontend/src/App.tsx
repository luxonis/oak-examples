import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Card, Flex } from '@luxonis/ui-components';
import { useMemo, useRef } from 'react';
import { AppShell, Steps } from './AppShell.tsx';
import { ClassSelector } from './ClassSelector.tsx';
import { ClickCatcher } from './ClickOverlay.tsx';
import { ConfidenceSlider } from './ConfidenceSlider.tsx';
import { MeasurementMethodSelector } from './MeasurementMethodSelector.tsx';
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
		<AppShell
			title="Object Volume Measurement 3D"
			streams={
				<div ref={viewerRef} className="ovm-viewer">
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
			}
		>
			<>
				<Card title="How to use" variant="outline" intent="white">
					<Steps
						items={[
							'Click a detected object in the Video panel to segment it and measure its dimensions and volume.',
							'Right-click the Video panel, or select Clear selected object, to clear the selection.',
							'Pick a measurement method to change how the volume is computed.',
						]}
					/>
				</Card>

				<Card title="Detection" variant="outline" intent="white">
					<Flex direction="column" gap="sm">
						<ClassSelector />
						<ConfidenceSlider initialValue={0.15} />
					</Flex>
				</Card>

				<Card title="Measurement" variant="outline" intent="white">
					<Flex direction="column" gap="sm">
						<MeasurementMethodSelector />
						<Button variant="outline" intent="gray" onClick={clearSelection}>
							Clear selected object
						</Button>
					</Flex>
				</Card>
			</>
		</AppShell>
	);
}

export default App;
