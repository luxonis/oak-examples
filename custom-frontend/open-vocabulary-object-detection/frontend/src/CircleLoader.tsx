import { Circle, type CircleProps, LoaderIcon } from '@luxonis/ui-components';

export const CircleLoader = (props: CircleProps) => {
	return <Circle icon={LoaderIcon} animation="spin" {...props} />;
};
