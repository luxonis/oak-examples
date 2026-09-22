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
			<div className="flex min-w-24 flex-col items-center text-center">
				<div className="text-xs font-semibold text-muted-foreground">
					Average Age
				</div>
				<div className="text-xl font-bold">{stats.age.toFixed(1)}</div>
			</div>

			<div className="hidden self-stretch border-l border-border md:block" />

			<div className="flex min-w-16 flex-col items-center text-center">
				<div className="text-lg font-bold text-info">
					{stats.males.toFixed(1)}%
				</div>
				<img className="h-7 w-7" src="icons/male.png" alt="Male" />
			</div>

			<div className="flex min-w-16 flex-col items-center text-center">
				<div className="text-lg font-bold text-accent">
					{stats.females.toFixed(1)}%
				</div>
				<img className="h-7 w-7" src="icons/female.png" alt="Female" />
			</div>

			<div className="hidden self-stretch border-l border-border md:block" />

			{EMOTION_ORDER.map((emotion) => (
				<div
					key={emotion}
					className="flex min-w-20 flex-col items-center text-center"
				>
					<div className="text-base font-bold">
						{(emotions[emotion] ?? 0).toFixed(1)}%
					</div>
					<div className="text-xs font-semibold text-muted-foreground">
						{emotion}
					</div>
				</div>
			))}
		</div>
	);
}
