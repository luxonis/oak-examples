# Streaming Overview

This section contains examples showing different ways to manipulate and stream data from DepthAI devices using various protocols and encoding methods.

## Platform Compatibility

|                                    POE MQTT                                     |                                       RTSP Streaming                                        |
| :-----------------------------------------------------------------------------: | :-----------------------------------------------------------------------------------------: |
| <img src="poe-mqtt/media/mqtt_client.gif" alt="poe mqtt" style="height:250px;"> | <img src="rtsp-streaming/media/rtsp_stream.gif" alt="rtsp streaming" style="height:250px;"> |

| Name                                      | RVC2 | RVC4 (peripheral) | RVC4 (standalone) | DepthAIv2                                                                                              | Notes                                                  |
| ----------------------------------------- | ---- | ----------------- | ----------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| [mjpeg-streaming](mjpeg-streaming/)       | ✅   | ✅                | ✅                | [gen2-mjpeg-streaming](https://github.com/luxonis/oak-examples/tree/master/gen2-mjpeg-streaming)       | Example of MJPEG video streaming implementation        |
| [poe-mqtt](poe-mqtt/)                     | ✅   | ✅                | ✅                | [gen2-poe-mqtt](https://github.com/luxonis/oak-examples/tree/master/gen2-poe-mqtt)                     | Demonstration of MQTT protocol usage with PoE cameras  |
| [poe-tcp-streaming](poe-tcp-streaming/)   | ✅   | ✅                | ✅                | [gen2-poe-tcp-streaming](https://github.com/luxonis/oak-examples/tree/master/gen2-poe-tcp-streaming)   | Example of TCP streaming with PoE cameras              |
| [rtsp-streaming](rtsp-streaming/)         | ✅   | ✅                | ✅                | [gen2-rtsp-streaming](https://github.com/luxonis/oak-examples/tree/master/gen2-rtsp-streaming)         | Implementation of RTSP video streaming                 |
| [webrtc-streaming](webrtc-streaming/)     | ✅   | ✅                | ✅                | [gen2-webrtc-streaming](https://github.com/luxonis/oak-examples/tree/master/gen2-webrtc-streaming)     | Example showing WebRTC streaming capabilities          |
| [on-device-encoding](on-device-encoding/) | ✅   | ✅                | ✅                | [gen2-container-encoding](https://github.com/luxonis/oak-examples/tree/master/gen2-container-encoding) | Demonstration of video encoding directly on OAK device |

✅: available; ❌: not available; 🚧: work in progress
