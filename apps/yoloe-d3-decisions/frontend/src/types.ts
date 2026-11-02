import type { Decision, DecisionResult } from './Decision';

export type Track = {
	id: number;
	class_name: string;
	confidence: number;
	box: number[];
	last_result: DecisionResult | null;
	decision_age: number | null;
};

export type Draft = Decision & { id: string };

export type Result = {
	answers: DecisionResult[];
	model_ms: number;
	preparation_ms: number;
	total_ms: number;
};

export type Job = {
	id: string;
	time: string;
	track_id: number;
	class_name: string;
	confidence: number;
	questions: Decision[];
	state: 'running' | 'done' | 'error';
	source_image: string | null;
	crop_image: string | null;
	result: Result | null;
	error: string | null;
};

export type State = {
	history_revision: number;
	has_frame: boolean;
	tracks: Track[];
	history?: Job[];
	detection: {
		classes: string[];
		confidence: number;
		iou: number;
		updating: boolean;
		error: string | null;
	};
	decision: {
		enabled: boolean;
		refresh: number;
		questions: Decision[];
		actual_per_second: number;
	};
	model: { ready: boolean; status: string; error: string | null };
};
