import cv2
from elements.yolo import OBJ_DETECTION
from config import RTSP_PORT, RTSP_PATH, Object_classes, Object_colors


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
    f"rtspclientsink location=rtsp://localhost:{RTSP_PORT}/{RTSP_PATH}"
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

