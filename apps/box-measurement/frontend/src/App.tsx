import MeasurementView from './MeasurementView';
import CalibrationView from './calibration/CalibrationView';
import { isCalibrated } from './calibration/calibrationState';
import { useSupportPlaneCalibrationStatus } from './calibration/useSupportPlaneCalibration';
import Page from './components/Page';

// The polled calibration state picks the view: calibrate until a support
// plane is confirmed, then measure.
function App() {
	const statusQuery = useSupportPlaneCalibrationStatus();
	const state = statusQuery.data?.state;

	return (
		<Page>
			{isCalibrated(state) ? <MeasurementView /> : <CalibrationView />}
		</Page>
	);
}

export default App;
