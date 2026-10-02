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

export default function App() {
	return (
		<main className="flex h-screen w-screen flex-row gap-6 overflow-auto bg-muted p-6">
			<div className="grid min-w-[900px] flex-1 shrink-0 grid-cols-2 gap-6">
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

			<div className="w-0.5 shrink-0 rounded-full bg-border" />

			<aside className="flex w-[380px] shrink-0 flex-col gap-5 text-left">
				<h1 className="text-2xl font-semibold">Focused Vision</h1>

				<div className="flex flex-col gap-4 text-sm leading-6 text-muted-foreground">
					<p>
						The goal of Focused Vision is to capture an object of interest in as
						much detail as possible and do all necessary steps on-device. It
						excels when the object occupies only a small part of the image -
						whether because it is physically small, relatively far from the
						camera, or both.
					</p>
					<p>
						This application compares a naive face-detection approach with two
						Focused Vision approaches using person detection and tiling.
					</p>

					<ul className="ml-5 list-disc space-y-2">
						<li>
							<strong className="text-foreground">Naive Approach:</strong>{' '}
							detect faces on downscaled low-res RGB.
						</li>
						<li>
							<strong className="text-foreground">NN Model Chaining:</strong>{' '}
							detect person, crop high-res, then detect face on the high-res
							crop.
						</li>
						<li>
							<strong className="text-foreground">Tiling:</strong> detect faces
							on overlapping tiles of the high-res image, then merge results.
						</li>
						<li>
							<strong className="text-foreground">RGB Preview:</strong> H264
							encoded RGB stream. Face detections from the naive approach and
							people detections from the NN model chaining are shown in the
							stream.
						</li>
					</ul>
				</div>
			</aside>
		</main>
	);
}
