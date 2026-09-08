import { Streams, useNavigation } from '@luxonis/depthai-viewer-common';
import { memo, useMemo } from 'react';
import { FaceMetaBar } from './FaceMetaBar.tsx';
import { StatsBanner } from './StatsBanner.tsx';
import { TopBar } from './TopBar.tsx';
import { type FaceMeta, useFacesPoll } from './useFacePoll_load.tsx';

const borderByStatus = (status?: FaceMeta['status']) => {
	if (status === 'NEW') return 'border-active';
	if (status === 'REID') return 'border-success';
	if (status === 'TBD') return 'border-destructive';
	return 'border-border';
};

const LeftVideo = memo(function LeftVideo() {
	const leftGroups = useMemo(
		() => ({ Video: 'images', Annotations: 'images' }),
		[],
	);
	const leftAllowed = useMemo(() => ['Video'], []);
	const { stats } = useFacesPoll();

	return (
		<section className="flex min-h-0 min-w-[760px] flex-1 shrink-0 flex-col overflow-hidden rounded-md border border-border bg-background shadow-sm">
			<TopBar />
			<StatsBanner stats={stats} />
			<div className="relative min-h-0 flex-1">
				<Streams
					allowedTopics={leftAllowed}
					defaultTopics={leftAllowed}
					topicGroups={leftGroups}
					hideToolbar
				/>
			</div>
		</section>
	);
});

function ImgBox({ url }: { url?: string }) {
	const { makePath } = useNavigation();
	const placeholder = useMemo(
		() => makePath('placeholders/empty.jpg', { noSearch: true }),
		[makePath],
	);

	return (
		<div className="relative flex min-h-0 flex-1 items-center justify-center bg-background">
			<img
				src={url ?? placeholder}
				alt=""
				draggable={false}
				className="max-h-full max-w-full object-contain"
			/>
		</div>
	);
}

function CropsWithBars() {
	const { faces } = useFacesPoll();

	return (
		<aside className="flex w-[300px] min-w-[300px] shrink-0 flex-col gap-6">
			{[0, 1, 2].map((slot) => {
				const face = faces[slot];

				return (
					<section
						key={slot}
						className={`flex min-h-[180px] flex-1 flex-col overflow-hidden rounded-md border-8 bg-background shadow-sm ${borderByStatus(
							face?.status,
						)}`}
					>
						<ImgBox url={face?.img_url} />
						<FaceMetaBar face={face} />
					</section>
				);
			})}
		</aside>
	);
}

export default function App() {
	return (
		<main className="flex h-screen w-screen gap-6 overflow-auto bg-muted p-6">
			<LeftVideo />
			<CropsWithBars />
		</main>
	);
}
