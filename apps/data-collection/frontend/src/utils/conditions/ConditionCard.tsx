import {
	Flex,
	Label,
	Separator,
	SubLabel,
	Switch,
} from '@luxonis/ui-components';
import { type ReactNode, useId } from 'react';

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
	const labelId = useId();

	return (
		<Flex direction="column" gap="sm">
			<Separator />
			<Flex direction="row" align="center" justify="between" gap="sm">
				<Label id={labelId} text={title} />
				<Switch
					aria-labelledby={labelId}
					value={enabled}
					onChange={onToggle}
					disabled={disabled}
					showActiveLabelOnly
				/>
			</Flex>
			{enabled && description ? <SubLabel text={description} /> : null}
			{enabled ? children : null}
		</Flex>
	);
}
