import {
	Badge,
	type ColorIntent,
	NormalText,
	SubLabel,
} from '@luxonis/ui-components';
import type { FaceMeta } from './useFacePoll_load.tsx';

const statusBadge: Record<
	NonNullable<FaceMeta['status']>,
	{ label: string; intent: ColorIntent }
> = {
	NEW: { label: 'New person', intent: 'active' },
	REID: { label: 'Re-identified', intent: 'success' },
	TBD: { label: 'Deciding', intent: 'gray' },
};

export function FaceMetaBar({ face }: { face?: FaceMeta }) {
	if (face?.id == null) {
		return (
			<div className="people-face-meta">
				<SubLabel text="No face yet" />
			</div>
		);
	}

	const left =
		face.gender && face.age != null
			? `${face.gender} (${face.age})`
			: face.gender || (face.age != null ? `Age ${face.age}` : '');
	const right = face.emotion ?? '';
	const details = left && right ? `${left}, ${right}` : left || right;
	const status = face.status ? statusBadge[face.status] : null;

	return (
		<div className="people-face-meta">
			<div className="flex flex-wrap items-center gap-2">
				<NormalText text={`ID ${face.id}`} />
				{status ? (
					<Badge intent={status.intent} variant="light" label={status.label} />
				) : null}
			</div>
			{details ? <SubLabel text={details} /> : null}
		</div>
	);
}
