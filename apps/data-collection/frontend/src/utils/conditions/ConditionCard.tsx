import { Switch } from '@luxonis/ui-components';
import type { ReactNode } from 'react';

interface ConditionCardProps {
	title: string;
	enabled: boolean;
	onToggle: (val: boolean) => void;
	disabled?: boolean;
	description?: string;
	children?: ReactNode;
}

export function ConditionCard({
	title,
	enabled,
	onToggle,
	disabled,
	description,
	children,
}: ConditionCardProps) {
	return (
		<div className="flex flex-col gap-4 border-t border-border pt-4">
			<div className="flex items-center justify-between gap-4">
				<span className="font-semibold">{title}</span>
				<Switch value={enabled} onChange={onToggle} disabled={disabled} />
			</div>
			{enabled && description ? (
				<p className="text-sm text-muted-foreground">{description}</p>
			) : null}
			{enabled ? children : null}
		</div>
	);
}
