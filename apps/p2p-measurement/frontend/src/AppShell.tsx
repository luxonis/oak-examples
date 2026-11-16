import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Badge,
	Circle,
	EmptyView,
	Label,
	LoaderIcon,
	PageTitle,
} from '@luxonis/ui-components';
import type { ReactNode } from 'react';

type AppShellProps = {
	title: string;
	streams: ReactNode;
	status?: ReactNode;
	below?: ReactNode;
	fitContent?: boolean;
	children?: ReactNode;
};

export function AppShell({
	title,
	streams,
	status,
	below,
	fitContent,
	children,
}: AppShellProps) {
	const { connected } = useDaiConnection();
	const streamsClassName = [
		'app-streams',
		below || fitContent ? 'app-streams-fit' : null,
		below ? 'app-streams-below' : null,
	]
		.filter(Boolean)
		.join(' ');

	return (
		<div className="app-page">
			<header className="app-header">
				<h1>
					<PageTitle text={title} />
				</h1>
				<div className="app-status">
					{status}
					<Badge
						dot
						iconProps={{ color: 'inherit' }}
						intent={connected ? 'success' : 'gray'}
						label={connected ? 'Connected' : 'Connecting'}
					/>
				</div>
			</header>
			<main className="app-main">
				<section className={streamsClassName} aria-label="Streams">
					{below ? <div className="app-viewer">{streams}</div> : streams}
					{below}
				</section>
				{children ? <aside className="app-side">{children}</aside> : null}
			</main>
		</div>
	);
}

type LoadingStateProps = {
	title: string;
	subtitle?: string;
};

export function LoadingState({ title, subtitle }: LoadingStateProps) {
	return (
		<EmptyView
			role="status"
			className="app-loading"
			rawIcon={<Circle icon={LoaderIcon} animation="spin" />}
			title={title}
			subtitle={subtitle}
		/>
	);
}

type StepsProps = {
	items: string[];
};

export function Steps({ items }: StepsProps) {
	return (
		<ol className="app-steps">
			{items.map((item) => (
				<li key={item}>
					<Label text={item} />
				</li>
			))}
		</ol>
	);
}
