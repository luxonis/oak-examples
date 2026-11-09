import { Card, Separator, SubHeader, SubLabel } from '@luxonis/ui-components';
import type { EmotionName, FaceStats } from './useFacePoll_load.tsx';

const EMOTION_ORDER: EmotionName[] = [
	'Happiness',
	'Neutral',
	'Surprise',
	'Anger',
	'Sadness',
	'Fear',
	'Disgust',
	'Contempt',
];

export function StatsBanner({ stats }: { stats?: FaceStats }) {
	if (!stats) return null;

	const emotions = stats.emotions ?? {};

	return (
		<Card title="Statistics" variant="outline" intent="white">
			<div className="flex flex-col gap-4">
				<dl className="grid grid-cols-3 gap-x-4 gap-y-3">
					<StatItem value={stats.age.toFixed(1)} label="Average age" />
					<StatItem value={`${stats.males.toFixed(1)}%`} label="Male" />
					<StatItem value={`${stats.females.toFixed(1)}%`} label="Female" />
				</dl>
				<Separator />
				<dl className="grid grid-cols-4 gap-x-4 gap-y-3">
					{EMOTION_ORDER.map((emotion) => (
						<StatItem
							key={emotion}
							value={`${(emotions[emotion] ?? 0).toFixed(1)}%`}
							label={emotion}
						/>
					))}
				</dl>
			</div>
		</Card>
	);
}

function StatItem({ value, label }: { value: string; label: string }) {
	return (
		<div className="flex min-w-0 flex-col">
			<dt>
				<SubLabel text={label} />
			</dt>
			<dd>
				<SubHeader text={value} />
			</dd>
		</div>
	);
}
