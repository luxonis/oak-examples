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
	children?: ReactNode;
};

export function AppShell({ title, streams, status, children }: AppShellProps) {
	const { connected } = useDaiConnection();

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
				<section className="app-streams" aria-label="Streams">
					{streams}
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
