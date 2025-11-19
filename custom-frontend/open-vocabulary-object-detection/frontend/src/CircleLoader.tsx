import type { CircleProps } from '@luxonis/common-fe-components';
import { Circle, LoaderIcon } from '@luxonis/common-fe-components';

export const CircleLoader = (props: CircleProps) => {
	return <Circle icon={LoaderIcon} animation="spin" {...props} />;
};