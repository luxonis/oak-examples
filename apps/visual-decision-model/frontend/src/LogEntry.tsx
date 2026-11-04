import { Badge } from '@luxonis/ui-components';
import { memo } from 'react';
import { DecisionOutput } from './Decision';
import type { Job } from './types';

export const LogEntry = memo(function LogEntry({ job }: { job: Job }) {
	return (
		<article className="result-card">
			<div className="section-heading">
				<div>
					<strong>
						{job.class_name} #{job.track_id}
					</strong>
					<span className="muted">
						{' '}
						· YOLO-E {(job.confidence * 100).toFixed(0)}% ·{' '}
						{new Date(job.time).toLocaleTimeString()}
					</span>
				</div>
				<Badge intent="gray" variant="light" label={job.state} />
			</div>
			<div className="log-body">
				<figure className="log-image">
					{job.source_image && (
						<img
							src={job.source_image}
							alt={`Source frame with ${job.class_name} crop highlighted`}
							loading="lazy"
							decoding="async"
						/>
					)}
					<figcaption>Full source frame + crop box</figcaption>
				</figure>
				<figure className="log-image">
					{job.crop_image && (
						<img
							src={job.crop_image}
							alt={`Exact ${job.class_name} crop submitted to d3-lite`}
							loading="lazy"
							decoding="async"
						/>
					)}
					<figcaption>Exact d3-lite input</figcaption>
				</figure>
				<div className="log-answers">
					{job.questions.map((question, index) => (
						<section className="log-question" key={`${job.id}-q${index}`}>
							<h3>
								{index + 1}. {question.instructions}
							</h3>
							{job.result?.answers[index] && (
								<DecisionOutput result={job.result.answers[index]} />
							)}
						</section>
					))}
					{job.result && (
						<p className="muted log-timing">
							Model request {job.result.model_ms.toFixed(0)} ms · Image
							preparation {job.result.preparation_ms.toFixed(0)} ms · Total
							backend {job.result.total_ms.toFixed(0)} ms
						</p>
					)}
					{job.error && (
						<p role="alert" className="error">
							{job.error}
						</p>
					)}
				</div>
			</div>
		</article>
	);
});
