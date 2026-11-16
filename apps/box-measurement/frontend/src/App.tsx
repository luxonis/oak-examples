import MeasurementView from './MeasurementView';
import SupportPlaneCalibrationView from './supportPlaneCalibration/SupportPlaneCalibrationView';
import { isSupportPlaneConfirmed } from './supportPlaneCalibration/supportPlaneCalibrationState';
import { useSupportPlaneCalibrationStatus } from './supportPlaneCalibration/useSupportPlaneCalibration';

// The polled support plane calibration state picks the view: calibrate until
// a support plane is confirmed, then measure. Each view fills the shared
// AppLayout with its stream and controls.
function App() {
	const statusQuery = useSupportPlaneCalibrationStatus();
	const state = statusQuery.data?.state;

	return isSupportPlaneConfirmed(state) ? (
		<MeasurementView />
	) : (
		<SupportPlaneCalibrationView />
	);
}

export default App;
