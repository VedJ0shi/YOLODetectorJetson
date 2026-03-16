import cv2
import time
import numpy as np
from elements.yolo import OBJ_DETECTION
from cvconfig import Object_classes, Object_colors
from registry import Object_register
from notif import update_system


Object_detector = OBJ_DETECTION('weights/yolov5s.pt', Object_classes)

#warming up YOLO for inference
_dummy = np.zeros((720, 1280, 3), dtype=np.uint8)
Object_detector.detect(_dummy)
print("[CV Service] Model ready")


def capture_pipeline(
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


def output_pipeline(
    display_width=1280,
    display_height=720,
    framerate=30,
    host = '127.0.0.1', 
    port = 5000 
):
    return (
        "appsrc ! "
        f"video/x-raw,format=BGR,width={display_width},height={display_height},"
        f"framerate={framerate}/1 ! "
        "videoconvert ! "
        "video/x-raw,format=BGRx ! "
        "nvvidconv ! "
        "video/x-raw(memory:NVMM),format=NV12 ! "
        "nvv4l2h264enc bitrate=4000000 iframeinterval=30 ! "
        "h264parse ! "
        "mpegtsmux ! "
        f"udpsink host={host} port={port}"
)


def start_camera_detection():

    cam = cv2.VideoCapture(capture_pipeline(), cv2.CAP_GSTREAMER)
    stream = cv2.VideoWriter(output_pipeline(), cv2.CAP_GSTREAMER, 0, 30, (1280, 720))

    while True:
        ok, frame = cam.read()
        if ok:
            now  = time.time()
            #detection call
            objs = Object_detector.detect(frame)
            
            #frame annotation procedure
            for obj in objs: #iterate over predictions
                label = obj['label']
                print(label)
                score = obj['score']
                [(xmin,ymin),(xmax,ymax)] = obj['bbox']
                color = Object_colors[Object_classes.index(label)]
                frame = cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), color, 2) 
                frame = cv2.putText(frame, f'{label} ({str(score)})', (xmin,ymin), cv2.FONT_HERSHEY_SIMPLEX , 0.75, color, 1, cv2.LINE_AA)

                # Update system state and fire notification hooks
                if label in Object_register.watch:
                    update_system("watch", {"detected": label, "time": now})
    
                if label in Object_register.catch:
                    update_system("catch", {"detected": label, "time": now})

            #streaming frames to mediamtx server
            stream.write(frame)
            

        keyCode = cv2.waitKey(30)
        if keyCode == ord('q'):
            break


    cam.release()
    stream.release()

