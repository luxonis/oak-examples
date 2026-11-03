import { memo } from 'react';
import { LogEntry } from './LogEntry';
import type { Job } from './types';

/** Display the most recent immutable decision jobs and their exact inputs. */
export const DecisionLog = memo(function DecisionLog({
	history,
}: { history: Job[] }) {
	return (
		<section className="history" aria-labelledby="history-title">
			<div className="section-heading">
				<h2 id="history-title">Decision inference log</h2>
				<span>Last 20 · newest first · memory only</span>
			</div>
			{history.length ? (
				history.map((job) => <LogEntry key={job.id} job={job} />)
			) : (
				<div className="empty">
					Source frames, exact crops and d3-lite answers will appear here.
				</div>
			)}
		</section>
	);
});
