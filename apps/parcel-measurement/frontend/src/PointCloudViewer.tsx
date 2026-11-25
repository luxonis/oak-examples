import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { MeasurementDetails } from './services';

const CUBOID_EDGES = [
	[0, 1],
	[1, 2],
	[2, 3],
	[3, 0],
	[4, 5],
	[5, 6],
	[6, 7],
	[7, 4],
	[0, 4],
	[1, 5],
	[2, 6],
	[3, 7],
];

function decodePoints(cloud: MeasurementDetails['point_cloud']) {
	const raw = atob(cloud.xyz);
	if (raw.length !== cloud.count * 12) {
		throw new Error('The saved point cloud has an invalid byte count.');
	}
	const bytes = Uint8Array.from(raw, (character) => character.charCodeAt(0));
	const view = new DataView(bytes.buffer);
	const points = new Float32Array(cloud.count * 3);
	for (let i = 0; i < points.length; i++) {
		points[i] = view.getFloat32(i * 4, true);
		if (!Number.isFinite(points[i]))
			throw new Error('The saved point cloud contains invalid coordinates.');
	}
	return points;
}

export function PointCloudViewer({
	measurement,
}: { measurement: MeasurementDetails }) {
	const container = useRef<HTMLDivElement>(null);
	const reset = useRef<() => void>(() => {});
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const host = container.current;
		if (!host) return;
		setError(null);
		let renderer: THREE.WebGLRenderer;
		let positions: Float32Array;
		try {
			positions = decodePoints(measurement.point_cloud);
			renderer = new THREE.WebGLRenderer({ antialias: true });
		} catch (exception) {
			setError(
				exception instanceof Error
					? exception.message
					: 'Could not start the 3D viewer.',
			);
			return;
		}
		renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
		renderer.setClearColor(0x101923);
		renderer.domElement.setAttribute(
			'aria-label',
			'Segmented parcel point cloud with measured cuboid',
		);
		host.appendChild(renderer.domElement);
		const scene = new THREE.Scene();
		const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100000);
		const controls = new OrbitControls(camera, renderer.domElement);
		const center = new THREE.Vector3(...measurement.cuboid.base_center_mm);
		const rotation = new THREE.Quaternion().setFromUnitVectors(
			new THREE.Vector3(...measurement.cuboid.up_axis).normalize(),
			new THREE.Vector3(0, 1, 0),
		);
		const cloud = new THREE.BufferGeometry();
		cloud.setAttribute('position', new THREE.BufferAttribute(positions, 3));
		cloud.translate(-center.x, -center.y, -center.z);
		cloud.applyQuaternion(rotation);
		cloud.computeBoundingBox();
		const pointMaterial = new THREE.PointsMaterial({
			color: 0x71cfff,
			size: 2.5,
			sizeAttenuation: false,
		});
		scene.add(new THREE.Points(cloud, pointMaterial));
		const vertices: number[] = [];
		for (const [a, b] of CUBOID_EDGES) {
			vertices.push(
				...measurement.cuboid.corners_mm[a],
				...measurement.cuboid.corners_mm[b],
			);
		}
		const edges = new THREE.BufferGeometry();
		edges.setAttribute(
			'position',
			new THREE.Float32BufferAttribute(vertices, 3),
		);
		edges.translate(-center.x, -center.y, -center.z);
		edges.applyQuaternion(rotation);
		const edgeMaterial = new THREE.LineBasicMaterial({
			color: 0x82ed8f,
			depthTest: false,
		});
		const wireframe = new THREE.LineSegments(edges, edgeMaterial);
		wireframe.renderOrder = 1;
		scene.add(wireframe);
		const span = Math.max(...measurement.dimensions_mm, 50);
		const grid = new THREE.GridHelper(span * 2.4, 12, 0x3f6477, 0x253b49);
		scene.add(grid);
		controls.target.set(0, measurement.dimensions_mm[2] / 2, 0);
		controls.minDistance = span * 0.15;
		controls.maxDistance = span * 15;
		reset.current = () => {
			camera.position.set(span * 1.7, span * 1.3, span * 1.7);
			controls.target.set(0, measurement.dimensions_mm[2] / 2, 0);
			controls.update();
		};
		reset.current();
		const draw = () => renderer.render(scene, camera);
		controls.addEventListener('change', draw);
		const resize = new ResizeObserver(() => {
			const width = host.clientWidth;
			const height = host.clientHeight;
			if (!width || !height) return;
			renderer.setSize(width, height);
			camera.aspect = width / height;
			camera.updateProjectionMatrix();
			draw();
		});
		resize.observe(host);
		return () => {
			resize.disconnect();
			controls.dispose();
			cloud.dispose();
			edges.dispose();
			pointMaterial.dispose();
			edgeMaterial.dispose();
			grid.dispose();
			renderer.dispose();
			renderer.domElement.remove();
			reset.current = () => {};
		};
	}, [measurement]);

	return (
		<section className="flex flex-col gap-2">
			<div
				ref={container}
				className="relative h-[420px] min-h-[260px] w-full overflow-hidden rounded-lg bg-[#101923] max-[800px]:h-[300px]"
			>
				{error ? (
					<p
						role="alert"
						className="absolute inset-0 flex items-center justify-center p-6 text-center text-white"
					>
						{error}
					</p>
				) : null}
			</div>
			<div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
				<span>
					Drag to orbit · Right-drag to pan · Scroll to zoom. Blue points, green
					cuboid. Units: mm.
				</span>
				<button
					type="button"
					onClick={() => reset.current()}
					className="shrink-0 rounded border border-border px-3 py-1 text-foreground"
				>
					Reset view
				</button>
			</div>
		</section>
	);
}
