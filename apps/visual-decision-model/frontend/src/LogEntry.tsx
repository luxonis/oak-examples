import { Badge } from '@luxonis/ui-components';
import { DecisionOutput } from './Decision';
import type { Job } from './types';

export function LogEntry({ job }: { job: Job }) {
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
			<div className="log-grid">
				<figure>
					{job.source_image && (
						<img
							src={job.source_image}
							alt={`Source frame with ${job.class_name} crop highlighted`}
						/>
					)}
					<figcaption>Full source frame + crop box</figcaption>
				</figure>
				<figure>
					{job.crop_image && (
						<img
							src={job.crop_image}
							alt={`Exact ${job.class_name} crop submitted to d3-lite`}
						/>
					)}
					<figcaption>Exact d3-lite input</figcaption>
				</figure>
			</div>
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
				<p className="muted">
					Model request {job.result.model_ms.toFixed(0)} ms · Image preparation{' '}
					{job.result.preparation_ms.toFixed(0)} ms · Total backend{' '}
					{job.result.total_ms.toFixed(0)} ms
				</p>
			)}
			{job.error && (
				<p role="alert" className="error">
					{job.error}
				</p>
			)}
		</article>
	);
}
