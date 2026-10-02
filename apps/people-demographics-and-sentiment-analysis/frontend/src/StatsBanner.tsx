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
		<div className="flex flex-wrap items-center gap-4 border-b border-border bg-background/90 px-4 py-3">
			<StatItem value={stats.age.toFixed(1)} label="Average Age" />

			<div className="hidden self-stretch border-l border-border md:block" />

			<StatItem
				value={`${stats.males.toFixed(1)}%`}
				label="Male"
				valueClassName="text-info"
			/>
			<StatItem
				value={`${stats.females.toFixed(1)}%`}
				label="Female"
				valueClassName="text-accent"
			/>

			<div className="hidden self-stretch border-l border-border md:block" />

			{EMOTION_ORDER.map((emotion) => (
				<StatItem
					key={emotion}
					value={`${(emotions[emotion] ?? 0).toFixed(1)}%`}
					label={emotion}
				/>
			))}
		</div>
	);
}

function StatItem({
	value,
	label,
	valueClassName = '',
}: {
	value: string;
	label: string;
	valueClassName?: string;
}) {
	return (
		<div className="flex min-w-20 flex-col items-center text-center">
			<div className={`text-base font-bold ${valueClassName}`}>
				{value}
			</div>
			<div className="text-xs font-semibold text-muted-foreground">{label}</div>
		</div>
	);
}
