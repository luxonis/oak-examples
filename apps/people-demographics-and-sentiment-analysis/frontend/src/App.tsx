import { Streams, useNavigation } from '@luxonis/depthai-viewer-common';
import { Card } from '@luxonis/ui-components';
import { memo, useMemo } from 'react';
import { AppShell } from './AppShell.tsx';
import { FaceMetaBar } from './FaceMetaBar.tsx';
import { StatsBanner } from './StatsBanner.tsx';
import { type FaceMeta, useFacesPoll } from './useFacePoll_load.tsx';

const VideoStream = memo(function VideoStream() {
	const topicGroups = useMemo(
		() => ({ Video: 'images', Annotations: 'images' }),
		[],
	);
	const allowedTopics = useMemo(() => ['Video'], []);

	return (
		<Streams
			allowedTopics={allowedTopics}
			defaultTopics={allowedTopics}
			topicGroups={topicGroups}
			hideToolbar
		/>
	);
});

function FaceSlot({ face }: { face?: FaceMeta }) {
	const { makePath } = useNavigation();
	const placeholder = useMemo(
		() => makePath('placeholders/empty.jpg', { noSearch: true }),
		[makePath],
	);

	return (
		<Card variant="outline" intent="white" contentClassName="people-face-body">
			<div className="people-face-image">
				<img
					src={face?.img_url ?? placeholder}
					alt={face?.id != null ? `Face crop of ID ${face.id}` : ''}
					draggable={false}
				/>
			</div>
			<FaceMetaBar face={face} />
		</Card>
	);
}

export default function App() {
	const { faces, stats } = useFacesPoll();

	return (
		<AppShell
			title="People Demographics and Sentiment Analysis"
			streams={<VideoStream />}
		>
			<StatsBanner stats={stats} />
			<section className="people-faces" aria-label="Faces">
				{[0, 1, 2].map((slot) => (
					<FaceSlot key={slot} face={faces[slot]} />
				))}
			</section>
		</AppShell>
	);
}
