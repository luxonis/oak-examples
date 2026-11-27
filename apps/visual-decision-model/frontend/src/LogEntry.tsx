import { Alert, Badge, NormalText, SubLabel } from '@luxonis/ui-components';
import { memo } from 'react';
import { DecisionOutput } from './Decision';
import type { Job } from './types';

const stateIntent = {
	running: 'active',
	done: 'gray',
	error: 'error',
} as const;

export const LogEntry = memo(function LogEntry({ job }: { job: Job }) {
	return (
		<article className="vdm-log-entry">
			<header className="vdm-log-header">
				<div>
					<h4>
						<NormalText
							weight="medium"
							text={`${job.class_name} #${job.track_id}`}
						/>
					</h4>
					<SubLabel
						text={`YOLO-E ${(job.confidence * 100).toFixed(0)}% at ${new Date(job.time).toLocaleTimeString()}`}
					/>
				</div>
				<Badge
					intent={stateIntent[job.state]}
					variant="light"
					label={job.state}
				/>
			</header>
			<div className="vdm-log-body">
				<figure className="vdm-log-image">
					{job.source_image && (
						<img
							src={job.source_image}
							alt={`Source frame with ${job.class_name} crop highlighted`}
							loading="lazy"
							decoding="async"
						/>
					)}
					<figcaption>
						<SubLabel text="Full source frame with crop box" />
					</figcaption>
				</figure>
				<figure className="vdm-log-image">
					{job.crop_image && (
						<img
							src={job.crop_image}
							alt={`Exact ${job.class_name} crop submitted to d3-lite`}
							loading="lazy"
							decoding="async"
						/>
					)}
					<figcaption>
						<SubLabel text="Exact d3-lite input" />
					</figcaption>
				</figure>
				<div className="vdm-log-answers">
					{job.questions.map((question, index) => (
						<section className="vdm-log-question" key={`${job.id}-q${index}`}>
							<h5>
								<NormalText
									weight="medium"
									text={`${index + 1}. ${question.instructions}`}
								/>
							</h5>
							{job.result?.answers[index] && (
								<DecisionOutput result={job.result.answers[index]} />
							)}
						</section>
					))}
					{job.result && (
						<SubLabel
							text={`Model request ${job.result.model_ms.toFixed(0)} ms, image preparation ${job.result.preparation_ms.toFixed(0)} ms, total backend ${job.result.total_ms.toFixed(0)} ms`}
						/>
					)}
					{job.error && (
						<Alert intent="error" variant="light" description={job.error} />
					)}
				</div>
			</div>
		</article>
	);
});
