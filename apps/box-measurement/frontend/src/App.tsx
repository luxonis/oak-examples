import MeasurementView from './MeasurementView';
import Page from './components/Page';
import SupportPlaneCalibrationView from './supportPlaneCalibration/SupportPlaneCalibrationView';
import { isSupportPlaneConfirmed } from './supportPlaneCalibration/supportPlaneCalibrationState';
import { useSupportPlaneCalibrationStatus } from './supportPlaneCalibration/useSupportPlaneCalibration';

// The polled support plane calibration state picks the view: calibrate until
// a support plane is confirmed, then measure.
function App() {
	const statusQuery = useSupportPlaneCalibrationStatus();
	const state = statusQuery.data?.state;

	return (
		<Page>
			{isSupportPlaneConfirmed(state) ? (
				<MeasurementView />
			) : (
				<SupportPlaneCalibrationView />
			)}
		</Page>
	);
}

export default App;
