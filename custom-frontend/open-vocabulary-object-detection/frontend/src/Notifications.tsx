import {
	createContext,
	useCallback,
	useContext,
	useMemo,
	useRef,
	useState,
} from 'react';

type Notification = {
	id: number;
	message: string;
	type?: 'info' | 'success' | 'warning' | 'error';
	durationMs?: number;
};

type NotificationContextValue = {
	notify: (
		message: string,
		options?: { type?: Notification['type']; durationMs?: number },
	) => void;
};

const NotificationContext = createContext<NotificationContextValue | null>(
	null,
);

export function useNotifications() {
	const ctx = useContext(NotificationContext);
	if (!ctx)
		throw new Error(
			'useNotifications must be used within NotificationProvider',
		);
	return ctx;
}

export function NotificationProvider({
	children,
}: { children: React.ReactNode }) {
	const [items, setItems] = useState<Notification[]>([]);
	const idRef = useRef(1);

	const remove = useCallback((id: number) => {
		setItems((prev) => prev.filter((n) => n.id !== id));
	}, []);

	const notify = useCallback<NotificationContextValue['notify']>(
		(message, options) => {
			const id = idRef.current++;
			const durationMs = options?.durationMs ?? 4500;
			const type = options?.type ?? 'info';
			setItems((prev) =>
				[...prev, { id, message, type, durationMs }].slice(-5),
			);
			if (durationMs > 0) {
				window.setTimeout(() => remove(id), durationMs);
			}
		},
		[remove],
	);

	const value = useMemo(() => ({ notify }), [notify]);

	return (
		<NotificationContext.Provider value={value}>
			{children}
			<div className="pointer-events-auto fixed right-4 bottom-4 z-[1000] flex w-[320px] flex-col items-end gap-2">
				{items.map((n, idx) => (
					<Toast
						key={n.id}
						notification={n}
						onClose={() => remove(n.id)}
						index={idx}
					/>
				))}
			</div>
		</NotificationContext.Provider>
	);
}

function Toast({
	notification,
	onClose,
	index,
}: {
	notification: Notification;
	onClose: () => void;
	index: number;
}) {
	const { message, type } = notification;
	const colorMap: Record<NonNullable<Notification['type']>, string> = {
		info: 'border-primary text-primary',
		success: 'border-success text-success',
		warning: 'border-warning text-warning',
		error: 'border-destructive text-destructive',
	};
	const colors = colorMap[type ?? 'info'];

	return (
		<div
			className={`pointer-events-auto w-[60%] animate-[slideInUp_180ms_ease-out_forwards] break-words rounded-lg border bg-background px-4 py-3 opacity-100 shadow-xl ${colors}`}
			style={{ animationDelay: `${index * 30}ms` }}
		>
			<div className="flex items-center gap-3">
				<span className="font-medium">{message}</span>
				<button
					type="button"
					className="ml-auto cursor-pointer border-0 bg-transparent px-1 text-lg leading-none font-bold transition-transform hover:scale-110 hover:opacity-70"
					onClick={onClose}
				>
					x
				</button>
			</div>
		</div>
	);
}
