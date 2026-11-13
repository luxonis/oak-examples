type StatusDotProps = {
	color: string;
	size?: number;
};

function StatusDot({ color, size = 10 }: StatusDotProps) {
	return (
		<span
			style={{
				width: size,
				height: size,
				borderRadius: '50%',
				backgroundColor: color,
				display: 'inline-block',
				flexShrink: 0,
			}}
		/>
	);
}

export default StatusDot;
