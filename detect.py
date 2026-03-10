import cv2
import numpy as np
from elements.yolo import OBJ_DETECTION

MAC_IP = "192.168.4.230"
MAC_RTP_PORT = 5000

Object_classes = ['person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 'traffic light',
                'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
                'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
                'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
                'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
                'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
                'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
                'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear',
                'hair drier', 'toothbrush' ]

Object_colors = list(np.random.rand(80,3)*255)
Object_detector = OBJ_DETECTION('weights/yolov5s.pt', Object_classes)

def gstreamer_pipeline(
    capture_width=1920,
    capture_height=1080,
    display_width=1280,
    display_height=720,
    framerate=30,
):
    return (
    "nvarguscamerasrc ! "
    f"video/x-raw(memory:NVMM),width={capture_width},height={capture_height},format=NV12,framerate={framerate}/1 ! "
    "nvvidconv ! "
    f"video/x-raw,width={display_width},height={display_height},format=BGRx ! "
    "videoconvert ! "
    "video/x-raw,format=BGR ! "
    "appsink"
)


def output_gstreamer_pipeline(
    display_width=1280,
    display_height=720,
    framerate=30,
):
    return (
    "appsrc ! "
    f"video/x-raw,format=BGR,width={display_width},height={display_height},framerate={framerate}/1 ! "
    "videoconvert ! "
    "video/x-raw,format=I420 ! "
    f"x264enc tune=zerolatency bitrate=2000 speed-preset=ultrafast ! "
    "rtph264pay config-interval=1 pt=96 ! "
    f"udpsink host={MAC_IP} port={MAC_RTP_PORT}"
)


cam = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
stream = cv2.VideoWriter(output_gstreamer_pipeline(), cv2.CAP_GSTREAMER, 0, 30, (1280, 720))

while True:
    ok, frame = cam.read()
    if ok:
        # detection process
        objs = Object_detector.detect(frame)

        # plotting
        for obj in objs:
            # print(obj)
            label = obj['label']
            score = obj['score']
            [(xmin,ymin),(xmax,ymax)] = obj['bbox']
            color = Object_colors[Object_classes.index(label)]
            frame = cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), color, 2) 
            frame = cv2.putText(frame, f'{label} ({str(score)})', (xmin,ymin), cv2.FONT_HERSHEY_SIMPLEX , 0.75, color, 1, cv2.LINE_AA)

        stream.write(frame)

    keyCode = cv2.waitKey(30)
    if keyCode == ord('q'):
        break


cam.release()
stream.release()

