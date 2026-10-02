import type { FaceMeta } from './useFacePoll_load.tsx';

const statusLabel: Record<NonNullable<FaceMeta['status']>, string> = {
	NEW: 'new person',
	REID: 're-identified',
	TBD: 'deciding',
};

export function FaceMetaBar({ face }: { face?: FaceMeta }) {
	if (!face) {
		return (
			<div className="min-h-12 border-t border-border bg-background p-2" />
		);
	}

	const line1 =
		face.id != null
			? `ID: ${face.id}${face.status ? `, ${statusLabel[face.status]}` : ''}`
			: '';

	const left =
		face.gender && face.age != null
			? `${face.gender} (${face.age})`
			: face.gender || (face.age != null ? `Age ${face.age}` : '');
	const right = face.emotion ?? '';
	const line2 = left && right ? `${left}, ${right}` : left || right;

	return (
		<div className="min-h-12 border-t border-border bg-background p-2 text-sm leading-tight">
			{line1 ? <div>{line1}</div> : null}
			{line2 ? <div className="text-muted-foreground">{line2}</div> : null}
		</div>
	);
}
