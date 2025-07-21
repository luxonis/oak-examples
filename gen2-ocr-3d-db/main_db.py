import depthai as dai
import cv2
import time
import numpy as np
import re
from utils import get_boxes, postprocess
import argparse

# --------------- Arguments ---------------
parser = argparse.ArgumentParser()
parser.add_argument(
    "-bt",
    "--box_thresh",
    help="set the confidence threshold of boxes",
    default=0.3,
    type=float,
)
parser.add_argument(
    "-t", "--thresh", help="set the bitmap threshold", default=0.6, type=float
)
parser.add_argument(
    "-ms", "--min_size", default=2, type=int, help="set min size of box"
)
parser.add_argument(
    "-mc",
    "--max_candidates",
    default=50,
    type=int,
    help="maximum number of candidate boxes",
)


args = parser.parse_args()

MAX_CANDIDATES = args.max_candidates
MIN_SIZE = args.min_size
BOX_THRESH = args.box_thresh
THRESH = args.thresh
UNCLIP_RATIO = 4  # set big unclip because thresh is high

PREVIEW_W, PREVIEW_H = 320, 320


def create_pipeline():
    pipeline = dai.Pipeline()
    pipeline.setOpenVINOVersion(version=dai.OpenVINO.VERSION_2021_4)

    # ------ Create a camera ------
    cam = pipeline.createColorCamera()
    cam.setPreviewSize(PREVIEW_W, PREVIEW_H)
    cam.setInterleaved(False)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB)
    cam.setPreviewKeepAspectRatio(True)
    cam.setFps(5)
    # ------------------------

    # ------ Image Manip ------
    manip = pipeline.createImageManip()
    manip.initialConfig.setResize(PREVIEW_W, PREVIEW_H)
    manip.initialConfig.setKeepAspectRatio(False)
    manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888p)
    # ------------------------

    cam.preview.link(manip.inputImage)

    # ------ Neural Network ------
    nn = pipeline.createNeuralNetwork()
    nn.setBlobPath("models/text_detection_db_320x320_openvino_2021.4_6shave.blob")
    # ------------------------

    manip.out.link(nn.input)

    # ------ Image Manip ------
    manip_recog = pipeline.createImageManip()
    manip_recog.inputConfig.setWaitForMessage(True)
    manip_img = pipeline.createXLinkIn()
    manip_img.setStreamName("manip_img")
    manip_img.out.link(manip_recog.inputImage)
    manip_cfg = pipeline.createXLinkIn()
    manip_cfg.setStreamName("manip_cfg")
    manip_cfg.out.link(manip_recog.inputConfig)
    # ------------------------

    # ------ Neural Network #2 ------
    nn_recog = pipeline.createNeuralNetwork()
    nn_recog.setBlobPath("models/text_recog_db_32x100_openvino_2021.4_6shave.blob")
    # ------------------------

    manip_recog.out.link(nn_recog.input)

    # ------ Out link ------
    xout_cam = pipeline.createXLinkOut()
    xout_cam.setStreamName("cam")
    cam.preview.link(xout_cam.input)
    # manip.out.link(xout_cam.input)

    xout_nn = pipeline.createXLinkOut()
    xout_nn.setStreamName("nn")
    nn.out.link(xout_nn.input)

    xout_manip_recog = pipeline.createXLinkOut()
    xout_manip_recog.setStreamName("manip_recog")
    manip_recog.out.link(xout_manip_recog.input)

    xout_nn_recog = pipeline.createXLinkOut()
    xout_nn_recog.setStreamName("nn_recog")
    nn_recog.out.link(xout_nn_recog.input)

    return pipeline


if __name__ == "__main__":
    with dai.Device() as device:
        # fps handling
        start_time = time.time()
        counter = 0
        fps = 0

        # start pipeline
        pipeline = create_pipeline()
        device.startPipeline(pipeline)

        while True:
            # get queues
            q_cam = device.getOutputQueue("cam", 4, False)
            q_nn = device.getOutputQueue("nn", 4, False)

            q_manip_recog = device.getOutputQueue("manip_recog", 4, False)
            q_nn_recog = device.getOutputQueue("nn_recog", 4, False)

            q_manip_cfg = device.getInputQueue("manip_cfg", 12)
            q_manip_img = device.getInputQueue("manip_img", 12)

            # get frame
            in_cam = q_cam.get()
            frame = in_cam.getCvFrame()

            # ------ read detection ------
            in_nn = q_nn.get()
            # get output layer
            pred = np.array(in_nn.getLayerFp16("out")).reshape((PREVIEW_W, PREVIEW_H))
            # show output mask
            cv2.imshow("Mask", (pred * 255).astype(np.uint8))
            tv, thresh = cv2.threshold(
                (pred * 255).astype(np.uint8), 10, 255, cv2.THRESH_BINARY
            )
            # get the contours from your thresholded image
            contours = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )[0]
            # decode
            boxes, scores = get_boxes(
                pred, THRESH, BOX_THRESH, MIN_SIZE, MAX_CANDIDATES, UNCLIP_RATIO
            )
            boxes = boxes.astype(np.int16)

            # recognition init
            texts = []
            frame_recogs = np.zeros((32, 100, 1), dtype=np.uint8)
            frame_texts = np.zeros((32, 250, 1), dtype=np.uint8)

            # loop over detections
            for idx, box in enumerate(boxes):
                # display text bb
                cv2.rectangle(
                    frame,
                    (box[0, 0], box[0, 1]),
                    (box[2, 0], box[2, 1]),
                    (255, 0, 0),
                    1,
                )
                cx = (box[0, 0] + box[2, 0]) / 2
                cy = (box[0, 1] + box[2, 1]) / 2
                cv2.circle(frame, (int(cx), int(cy)), 1, (255, 0, 0), 1)
                width = np.linalg.norm(box[0] - box[1])
                height = np.linalg.norm(box[0] - box[3])
                dist = np.abs(box[0, 0] - box[1, 0])
                angle = np.arccos(dist / width)

                # print(f"{dist} / {width} => {np.rad2deg(angle)}")

                # create rr for image manip
                rr = dai.RotatedRect()
                rr.center.x = (
                    cx + 15
                )  # manually add so the crop is centered (myb bug in Manip)
                rr.center.y = cy
                rr.size.width = width * 1.2
                rr.size.height = height  # * 1.05
                rr.angle = 0
                # rr.angle = np.rad2deg(angle)

                # send to image config to get a crop
                cfg = dai.ImageManipConfig()
                cfg.setFrameType(dai.ImgFrame.Type.GRAY8)
                cfg.setCropRotatedRect(rr, False)
                cfg.setResize(100, 32)
                if idx == 0:
                    q_manip_img.send(in_cam)
                else:
                    cfg.setReusePreviousImage(True)
                q_manip_cfg.send(cfg)

                # get cropped image
                frame_recog = q_manip_recog.get()
                shape = (1, frame_recog.getHeight(), frame_recog.getWidth())
                frame_recog = frame_recog.getData().reshape(shape).transpose(1, 2, 0)
                frame_recogs = np.vstack([frame_recogs, frame_recog])

                # get 2nd nn output and decode text
                in_text = q_nn_recog.get()
                text_recog = np.array(in_text.getLayerFp16("output")).reshape(24, 1, 37)
                text_recog = postprocess(text_recog)
                texts.append(text_recog)

                # combine text frames
                frame_text = np.zeros((32, 250, 1), dtype=np.uint8)
                cv2.putText(
                    frame_text, text_recog, (0, 26), cv2.FONT_HERSHEY_DUPLEX, 0.5, 255
                )
                frame_texts = np.vstack([frame_texts, frame_text])

            # show all manip crops
            cv2.imshow("recogs", np.hstack([frame_recogs, frame_texts]))

            # detect 500000k reached
            # print(texts)
            r = re.compile("s[0-9]{6}")
            raised_list = list(filter(r.match, texts))  # Read Note below
            color_black, color_white = (0, 0, 0), (255, 255, 255)
            if len(raised_list) > 0:
                raised_amount = int(raised_list[0][1:])
                print(f"PARSED AMOUNT: {raised_amount}")
                raised_text = f"Raised: ${raised_amount}"
                (w, h), _ = cv2.getTextSize(
                    raised_text, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1
                )
                cv2.rectangle(
                    frame,
                    (160 - w // 2 - 5, 0),
                    (160 + w // 2 + 5, h + 15),
                    color_white,
                    -1,
                )
                cv2.putText(
                    frame,
                    raised_text,
                    (160 - w // 2, 0 + h + 10),
                    cv2.FONT_HERSHEY_DUPLEX,
                    0.5,
                    (100, 100, 100) if raised_amount < 500000 else (255, 0, 255),
                )

            # ------ Show FPS ------
            label_fps = "Fps: {:.2f}".format(fps)
            (w1, h1), _ = cv2.getTextSize(label_fps, cv2.FONT_HERSHEY_TRIPLEX, 0.4, 1)
            cv2.rectangle(
                frame,
                (0, frame.shape[0] - h1 - 6),
                (w1 + 2, frame.shape[0]),
                color_white,
                -1,
            )
            cv2.putText(
                frame,
                label_fps,
                (2, frame.shape[0] - 4),
                cv2.FONT_HERSHEY_TRIPLEX,
                0.4,
                color_black,
            )

            cv2.imshow("frame", frame)

            counter += 1
            if (time.time() - start_time) > 1:
                fps = counter / (time.time() - start_time)

                counter = 0
                start_time = time.time()

            if cv2.waitKey(1) == ord("q"):
                break
