import {css} from "../styled-system/css/css.mjs";
import {Streams, useDaiConnection} from "@luxonis/depthai-viewer-common";
import {MessageInput} from "./MessageInput.tsx";


function App() {
    const connection = useDaiConnection();

    return (
        <main className={css({
            width: 'screen',
            height: 'screen',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 'sm',
            padding: 'sm',
            textAlign: 'center'
        })}>
            <h1 className={css({fontSize: '2xl', fontWeight: 'bold'})}>Local Frontend for Visualizer Example</h1>

            <Streams hideToolbar />

            {connection.connected && <MessageInput />}
        </main>
    );
}

export default App;
