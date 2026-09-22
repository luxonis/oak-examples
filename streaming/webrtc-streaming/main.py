import asyncio
import json
import time
import uuid
from pathlib import Path

import aiohttp_cors
import depthai as dai
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from utils.datachannel import setup_datachannel
from utils.options_wrapper import OptionsWrapper
from utils.transform import VideoTransform, start_pipeline

# There can be only one
#  if every VideoTransform tries to create its own pipeline they would all try to connect to their own device
#  one device can run only one pipeline at a time
pipeline = dai.Pipeline()
startup_queues = start_pipeline(pipeline, OptionsWrapper({}))
print("Pipeline created.")
pipeline.start()
print("Pipeline started.")


async def index(request):
    with (Path(__file__).parent / "client/index.html").open() as f:
        return web.Response(content_type="text/html", text=f.read())


async def javascript(request):
    with (Path(__file__).parent / "client/build/client.js").open() as f:
        return web.Response(content_type="application/javascript", text=f.read())


async def on_shutdown(application):
    # Close peer connections
    coroutines = [pc.close() for pc in application.pcs]
    await asyncio.gather(*coroutines)
    application.pcs.clear()


async def offer(request):
    global pipeline

    params = await request.json()
    options = OptionsWrapper(params.get("options", dict()))
    rtc_offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pc_id = "PeerConnection({})".format(uuid.uuid4())

    # Handle offer
    request.app.pcs.add(pc)
    await pc.setRemoteDescription(rtc_offer)

    for t in pc.getTransceivers():
        if t.kind == "video":
            print("Created for {}".format(request.remote))

            # Removes the connection to the device so that a new pipeline can connect to the device
            try:
                if pipeline is not None and pipeline.isRunning():
                    print("Restarting pipeline...")
                    time.sleep(0.5)
                    pipeline.stop()
                    pipeline = None
            # This can be hit because VideoTransform can call "del pipeline"
            except NameError:
                print("Restarting pipeline...")
                time.sleep(0.5)

            pipeline = dai.Pipeline()

            setup_datachannel(pc, pc_id, request.app)
            request.app.video_transforms[pc_id] = VideoTransform(
                pipeline, request.app, pc_id, options
            )
            pc.addTrack(request.app.video_transforms[pc_id])

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        global pipelines_counter

        print("ICE connection state is {}".format(pc.iceConnectionState))
        if pc.iceConnectionState == "failed":
            await pc.close()
            request.app.pcs.discard(pc)

    @pc.on("track")
    def on_track(track):
        print("Track {} received".format(track.kind))

    await pc.setLocalDescription(await pc.createAnswer())

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


def create_web_app():
    app = web.Application()
    setattr(app, "pcs", set())
    setattr(app, "pcs_datachannels", {})
    setattr(app, "video_transforms", {})

    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        },
    )
    cors.add(app.router.add_post("/offer", offer))
    return app


app = create_web_app()
web.run_app(app, access_log=None, port=8080)
