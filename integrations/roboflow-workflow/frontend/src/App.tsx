import { Streams } from '@luxonis/depthai-viewer-common';
import { Card, Flex, Label } from '@luxonis/ui-components';
import { AppShell, Steps } from './AppShell.tsx';
import { MessageInput } from './MessageInput.tsx';

function App() {
	return (
		<AppShell title="Roboflow Workflow" streams={<Streams />}>
			<Card title="How to use" variant="outline" intent="white">
				<Flex direction="column" gap="sm">
					<Label text="Camera frames run through your Roboflow workflow on the device with the Inference package. Its predictions and visualizations appear as streams." />
					<Steps
						items={[
							'Open a stream with the Streams button in the stream area.',
							"To switch streams, choose Close Stream in the stream's Stream Settings menu, then pick another.",
							'Show or hide detection overlays under Annotations in the Stream Settings menu.',
						]}
					/>
				</Flex>
			</Card>
			<MessageInput />
		</AppShell>
	);
}

export default App;
