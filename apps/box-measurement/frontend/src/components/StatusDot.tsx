type StatusDotProps = {
	color: string;
};

function StatusDot({ color }: StatusDotProps) {
	return (
		<span
			aria-hidden
			className="inline-block size-2.5 shrink-0 rounded-full"
			style={{ backgroundColor: color }}
		/>
	);
}

export default StatusDot;
