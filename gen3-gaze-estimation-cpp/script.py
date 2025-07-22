import time
sync = {} # Dict of messages

def find_in_dict(target_seq, name):
    if str(target_seq) in sync:
        return sync[str(target_seq)][name]

def add_to_dict(det, seq, name):
    sync[str(seq)][name] = det

def correct_bb(bb):
    if bb.xmin < 0: bb.xmin = 0.001
    if bb.ymin < 0: bb.ymin = 0.001
    if bb.xmax > 1: bb.xmax = 0.999
    if bb.ymax > 1: bb.ymax = 0.999

def check_gaze_est(seq):
    dict = sync[str(seq)]

    if "left" in dict and "right" in dict and "angles" in dict:
        # node.warn("GOT ALL 3")
        # Send to gaze estimation NN
        node.io['to_gaze_left'].send(dict['left'])
        node.io['to_gaze_right'].send(dict['right'])
        head_pose = NNData(6)
        head_pose.setLayer("head_pose_angles", dict['angles'])
        node.io['to_gaze_head'].send(head_pose)

        # Clear previous results
        for i, sq in enumerate(sync):
            del sync[str(seq)]
            if str(seq) == str(sq):
                return

PAD = 0.15
PAD2x = PAD * 2
def get_eye_coords(x, y, det):
    xdelta = det.xmax - det.xmin
    ydelta = det.ymax - det.ymin

    xmin = x - PAD
    xmax = xmin + PAD2x
    ymin = y - PAD
    ymax = ymin + PAD2x

    xmin2 = det.xmin + xdelta * xmin
    xmax2 = det.xmin + xdelta * xmax
    ymin2 = det.ymin + ydelta * ymin
    ymax2 = det.ymin + ydelta * ymax
    ret = (xmin2, ymin2, xmax2, ymax2)
    # node.warn(f"Eye: {x}/{y}, Crop eyes: {ret}, det {det.xmin}, {det.ymin}, {det.xmax}, {det.ymax}")
    return ret

while True:
    time.sleep(0.001)

    preview = node.io['preview'].tryGet()
    if preview is not None:
        sync[str(preview.getSequenceNum())] = {
            "frame": preview
        }
        # node.warn(f"New frame, {len(sync)}")

    face_dets = node.io['face_det_in'].tryGet()
    if face_dets is not None:
        passthrough = node.io['face_pass'].get()
        seq = passthrough.getSequenceNum()

        # No detections, carry on
        if len(face_dets.detections) == 0:
            del sync[str(seq)]
            continue

        #node.warn(f"New detection {seq}")
        if len(sync) == 0: continue
        img = find_in_dict(seq, "frame")
        if img is None: continue

        add_to_dict(face_dets.detections[0], seq, "detections")

        for det in face_dets.detections:
            correct_bb(det)

            # To head post estimation model
            cfg1 = ImageManipConfig()
            cfg1.setCropRect(det.xmin, det.ymin, det.xmax, det.ymax)
            cfg1.setResize(60, 60)
            cfg1.setKeepAspectRatio(False)
            node.io['headpose_cfg'].send(cfg1)
            node.io['headpose_img'].send(img)

            # To face landmark detection model
            cfg2 = ImageManipConfig()
            cfg2.setCropRect(det.xmin, det.ymin, det.xmax, det.ymax)
            cfg2.setResize(48, 48)
            cfg2.setKeepAspectRatio(False)
            node.io['landmark_cfg'].send(cfg2)
            node.io['landmark_img'].send(img)
            break # Only 1 face at the time currently supported

    headpose = node.io['headpose_in'].tryGet()
    if headpose is not None:
        passthrough = node.io['headpose_pass'].get()
        seq = passthrough.getSequenceNum()
        # Face rotation in degrees
        y = headpose.getLayerFp16('angle_y_fc')[0]
        p = headpose.getLayerFp16('angle_p_fc')[0]
        r = headpose.getLayerFp16('angle_r_fc')[0]
        angles = [y,p,r]
        # node.warn(f"angles {angles}")
        add_to_dict(angles, seq, "angles")
        check_gaze_est(seq)

    landmark_in = node.io['landmark_in'].tryGet()
    if landmark_in is not None:
        passthrough = node.io['landmark_pass'].get()
        seq = passthrough.getSequenceNum()

        img = find_in_dict(seq, "frame")
        det = find_in_dict(seq, "detections")
        if img is None or det is None: continue

        landmarks = landmark_in.getFirstLayerFp16()

        # We need to crop left and right eye out of the face frame
        left_cfg = ImageManipConfig()
        left_cfg.setCropRect(*get_eye_coords(landmarks[0], landmarks[1], det))
        left_cfg.setResize(60, 60)
        left_cfg.setKeepAspectRatio(False)
        node.io['left_manip_cfg'].send(left_cfg)
        node.io['left_manip_img'].send(img)

        right_cfg = ImageManipConfig()
        right_cfg.setCropRect(*get_eye_coords(landmarks[2], landmarks[3], det))
        right_cfg.setResize(60, 60)
        right_cfg.setKeepAspectRatio(False)
        node.io['right_manip_cfg'].send(right_cfg)
        node.io['right_manip_img'].send(img)

    left_eye = node.io['left_eye_in'].tryGet()
    if left_eye is not None:
        # node.warn("LEFT EYE GOT")
        seq = left_eye.getSequenceNum()
        add_to_dict(left_eye, seq, "left")
        check_gaze_est(seq)

    right_eye = node.io['right_eye_in'].tryGet()
    if right_eye is not None:
        # node.warn("RIGHT EYE GOT")
        seq = right_eye.getSequenceNum()
        add_to_dict(right_eye, seq, "right")
        check_gaze_est(seq)