import { memo, useLayoutEffect, useRef } from 'react';
import { LogEntry } from './LogEntry';
import type { Job } from './types';

/** Display the most recent immutable decision jobs and their exact inputs. */
export const DecisionLog = memo(function DecisionLog({
	history,
}: { history: Job[] }) {
	const listRef = useRef<HTMLDivElement>(null);

	useLayoutEffect(() => {
		const list = listRef.current;
		if (!list) return;
		if (history.length <= 5) {
			list.style.maxHeight = '';
			return;
		}

		const visibleCards = Array.from(list.children).slice(0, 5) as HTMLElement[];
		const fifthCard = visibleCards[4];
		const resize = () => {
			const bottomMargin = Number.parseFloat(
				getComputedStyle(fifthCard).marginBottom,
			);
			list.style.maxHeight = `${fifthCard.offsetTop + fifthCard.offsetHeight + bottomMargin}px`;
		};
		const observer = new ResizeObserver(resize);
		for (const card of visibleCards) observer.observe(card);
		resize();

		return () => observer.disconnect();
	}, [history]);

	return (
		<section className="history" aria-labelledby="history-title">
			<div className="section-heading">
				<h2 id="history-title">Decision inference log</h2>
				<span>Last 20 · newest first · memory only</span>
			</div>
			{history.length ? (
				<div
					ref={listRef}
					className={`history-list${history.length > 5 ? ' is-scrollable' : ''}`}
				>
					{history.map((job) => (
						<LogEntry key={job.id} job={job} />
					))}
				</div>
			) : (
				<div className="empty">
					Source frames, exact crops and d3-lite answers will appear here.
				</div>
			)}
		</section>
	);
});
