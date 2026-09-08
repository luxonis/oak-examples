import { Streams } from '@luxonis/depthai-viewer-common';

interface LuxonisStreamProps {
	title: string;
	caption?: string;
	defaultTopics: string[];
	allowedTopics: string[];
	topicGroups?: Record<string, string>;
}

export default function LuxonisStream({
	title,
	caption,
	defaultTopics,
	allowedTopics,
	topicGroups = {},
}: LuxonisStreamProps) {
	return (
		<section className="flex min-h-72 flex-col gap-2 rounded-md border border-border bg-background p-3 shadow-sm">
			<h2 className="mb-1 text-base font-semibold">{title}</h2>
			{caption ? (
				<p className="mb-2 text-sm text-muted-foreground">{caption}</p>
			) : null}
			<div className="min-h-80 flex-1">
				<Streams
					topicGroups={topicGroups}
					defaultTopics={defaultTopics}
					allowedTopics={allowedTopics}
					hideToolbar
				/>
			</div>
		</section>
	);
}
