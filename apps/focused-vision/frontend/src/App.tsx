import { Card, Label, NormalText } from '@luxonis/ui-components';
import { AppShell } from './AppShell.tsx';
import LuxonisStream from './components/LuxonisStream';
import {
	FOCUSED_TILING_TOPIC_GROUPS,
	FOCUSED_TOPIC_GROUPS,
	FOCUSED_VISION_HEAD_CROPS_ALLOWED,
	FOCUSED_VISION_HEAD_CROPS_DEFAULT,
	FOCUSED_VISION_TILING_HEAD_CROPS_ALLOWED,
	FOCUSED_VISION_TILING_HEAD_CROPS_DEFAULT,
	LOW_RES_ALLOWED_TOPICS,
	LOW_RES_DEFAULT_TOPICS,
	LOW_RES_TOPIC_GROUPS,
	NON_FOCUSED_TOPIC_GROUPS,
	NON_FOCUS_HEAD_CROPS_ALLOWED,
	NON_FOCUS_HEAD_CROPS_DEFAULT,
} from './constants';

const approaches = [
	{
		title: 'Naive Approach',
		description: 'Detect faces on the downscaled low-res RGB image.',
	},
	{
		title: 'Focused Vision with NN Model Chaining',
		description:
			'Detect people, crop the high-res image, then detect faces on the high-res crops.',
	},
	{
		title: 'Focused Vision with Tiling',
		description:
			'Detect faces on overlapping tiles of the high-res image, then merge the results.',
	},
	{
		title: 'RGB Preview',
		description:
			'H264 encoded RGB stream. It shows the face detections from the naive approach and the people detections from NN model chaining.',
	},
];

export default function App() {
	return (
		<AppShell
			fitContent
			title="Focused Vision"
			streams={
				<div className="focused-grid">
					<LuxonisStream
						title="RGB Preview"
						topicGroups={LOW_RES_TOPIC_GROUPS}
						defaultTopics={LOW_RES_DEFAULT_TOPICS}
						allowedTopics={LOW_RES_ALLOWED_TOPICS}
					/>
					<LuxonisStream
						title="Naive Approach"
						topicGroups={NON_FOCUSED_TOPIC_GROUPS}
						defaultTopics={NON_FOCUS_HEAD_CROPS_DEFAULT}
						allowedTopics={NON_FOCUS_HEAD_CROPS_ALLOWED}
					/>
					<LuxonisStream
						title="Focused Vision with NN Model Chaining"
						topicGroups={FOCUSED_TOPIC_GROUPS}
						defaultTopics={FOCUSED_VISION_HEAD_CROPS_DEFAULT}
						allowedTopics={FOCUSED_VISION_HEAD_CROPS_ALLOWED}
					/>
					<LuxonisStream
						title="Focused Vision with Tiling"
						topicGroups={FOCUSED_TILING_TOPIC_GROUPS}
						defaultTopics={FOCUSED_VISION_TILING_HEAD_CROPS_DEFAULT}
						allowedTopics={FOCUSED_VISION_TILING_HEAD_CROPS_ALLOWED}
					/>
				</div>
			}
		>
			<Card title="Goal" variant="outline" intent="white">
				<Label text="Focused Vision captures an object of interest in as much detail as possible and does every step on-device. It excels when the object fills only a small part of the image, because it is physically small, far from the camera, or both." />
			</Card>
			<Card title="Approaches" variant="outline" intent="white">
				<div className="flex flex-col gap-4">
					<Label text="This app compares a naive face-detection approach with two Focused Vision approaches that use person detection and tiling." />
					<dl className="flex flex-col gap-4">
						{approaches.map(({ title, description }) => (
							<div key={title}>
								<dt>
									<NormalText text={title} />
								</dt>
								<dd>
									<Label text={description} />
								</dd>
							</div>
						))}
					</dl>
				</div>
			</Card>
		</AppShell>
	);
}
