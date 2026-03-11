import cv2
import sys
from server import RTSPMediaServer
from config import RTSP_PORT, RTSP_PATH, Object_classes, Object_colors
from elements.yolo import OBJ_DETECTION


Object_detector = OBJ_DETECTION('weights/yolov5s.pt', Object_classes)

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

def main():
    rtsp = RTSPMediaServer(
        port   = RTSP_PORT,
        path   = RTSP_PATH,
        width  = 1280,
        height = 720,
        fps    = 30,
    )

    cam = cv2.VideoCapture(capture_pipeline(), cv2.CAP_GSTREAMER)
    if not cam.isOpened():
        raise RuntimeError("Failed to open camera pipeline")

    print("Detection loop running — press Ctrl-C to stop")
    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                #frame dropped
                continue

            #YOLO Detection:
            objs = Object_detector.detect(frame)
            for obj in objs: #iterate over predictions
                label  = obj['label']
                score  = obj['score']
                [(xmin, ymin), (xmax, ymax)] = obj['bbox']

                #Annotate frame:
                color  = Object_colors[Object_classes.index(label)]
                frame  = cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 2)
                frame  = cv2.putText(
                    frame, f'{label} ({score})',
                    (xmin, ymin), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 1, cv2.LINE_AA
                )

            #Serve annotated frame to client via ongoing rtsp stream
            rtsp.push_frame(frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        sys.exit()
    finally:
        cam.release()
        print("Stopped.")


if __name__ == "__main__":
    main()