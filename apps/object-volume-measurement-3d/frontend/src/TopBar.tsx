export const TopBar = () => {
	return (
		<header className="flex h-14 w-full shrink-0 items-center justify-between border-b border-border px-4">
			<img src="logo.svg" alt="Luxonis" className="h-auto w-[120px]" />
			<span className="text-xs font-medium text-muted-foreground">
				Video + Pointclouds
			</span>
		</header>
	);
};
