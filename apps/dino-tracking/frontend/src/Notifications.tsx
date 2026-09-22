import { ToastHost, type ToastProps, toast } from '@luxonis/ui-components';
import { type ReactNode, useCallback } from 'react';

type NotificationType = 'info' | 'success' | 'warning' | 'error';

type NotificationOptions = {
	type?: NotificationType;
	durationMs?: number;
};

type NotificationApi = {
	notify: (message: string, options?: NotificationOptions) => void;
};

function getToastTone(
	type: NotificationType,
): Pick<ToastProps, 'colorVariant'> {
	switch (type) {
		case 'success':
			return { colorVariant: 'success' };
		case 'warning':
			return { colorVariant: 'warning' };
		case 'error':
			return { colorVariant: 'error' };
		case 'info':
			return { colorVariant: 'active' };
	}
}

export function useNotifications() {
	const notify = useCallback<NotificationApi['notify']>((message, options) => {
		const durationMs = options?.durationMs ?? 4500;
		const type = options?.type ?? 'info';

		toast({
			title: message,
			duration: durationMs,
			permanent: durationMs <= 0,
			...getToastTone(type),
		});
	}, []);

	return { notify };
}

export function NotificationProvider({ children }: { children: ReactNode }) {
	return <ToastHost verticalPosition="bottom">{children}</ToastHost>;
}
