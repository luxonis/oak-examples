import { Streams } from '@luxonis/depthai-viewer-common';
import { Card } from '@luxonis/ui-components';

interface LuxonisStreamProps {
	title: string;
	defaultTopics: string[];
	allowedTopics: string[];
	topicGroups?: Record<string, string>;
}

export default function LuxonisStream({
	title,
	defaultTopics,
	allowedTopics,
	topicGroups = {},
}: LuxonisStreamProps) {
	return (
		<Card
			title={title}
			variant="outline"
			intent="white"
			className="focused-panel"
			contentClassName="focused-panel-body"
		>
			<Streams
				topicGroups={topicGroups}
				defaultTopics={defaultTopics}
				allowedTopics={allowedTopics}
				hideToolbar
			/>
		</Card>
	);
}
