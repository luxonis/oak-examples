import type { IconType } from '@luxonis/ui-components';

// ui-components exports AddIcon (Material "add") but no minus. This is Material
// "remove" drawn the same way, so a −/+ stepper uses one matching icon set.
// ui-components' Icon only passes className, so no other props are forwarded.
const RemoveIcon: IconType = ({ className }) => (
	<svg
		viewBox="0 0 24 24"
		fill="currentColor"
		width="1em"
		height="1em"
		aria-hidden="true"
		className={className}
	>
		<path d="M19 13H5v-2h14v2z" />
	</svg>
);

export default RemoveIcon;
