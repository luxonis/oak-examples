import type { DAIConnection, DAIService } from '@luxonis/depthai-viewer-common';

export function callService<T>(
	connection: DAIConnection | null,
	service: string,
	body: Record<string, unknown> = {},
): Promise<T> {
	return new Promise((resolve, reject) => {
		if (!connection) return reject(new Error('Not connected to the camera.'));
		const timer = window.setTimeout(
			() => reject(new Error('Device request timed out.')),
			10000,
		);
		void connection
			.postToService(service as DAIService, body, (response) => {
				window.clearTimeout(timer);
				try {
					let data: unknown = response;
					if (data && typeof data === 'object' && 'data' in data)
						data = data.data;
					if (data instanceof ArrayBuffer)
						data = new TextDecoder().decode(data);
					if (ArrayBuffer.isView(data)) data = new TextDecoder().decode(data);
					if (typeof data === 'string') data = JSON.parse(data);
					if (data && typeof data === 'object' && 'error' in data && data.error)
						throw new Error(String(data.error));
					resolve(data as T);
				} catch (error) {
					reject(
						new Error(
							(error instanceof Error ? error.message : String(error)).replace(
								/^API returned error response:\s*/i,
								'',
							),
						),
					);
				}
			})
			.catch((error: unknown) => {
				window.clearTimeout(timer);
				reject(
					new Error(
						(error instanceof Error ? error.message : String(error)).replace(
							/^API returned error response:\s*/i,
							'',
						),
					),
				);
			});
	});
}
