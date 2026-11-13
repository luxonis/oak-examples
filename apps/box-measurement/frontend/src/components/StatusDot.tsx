type StatusDotProps = {
	color: string;
};

function StatusDot({ color }: StatusDotProps) {
	return (
		<span
			aria-hidden
			className="inline-block size-2.5 shrink-0 rounded-full"
			// Inline so the dot matches the exact colour painted on the preview cloud
			style={{ backgroundColor: color }}
		/>
	);
}

export default StatusDot;
