import threading, time
import numpy as np
import gi 
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib



class RTSPMediaServer:
    """
    Wraps GstRtspServer and feeds it from an appsrc that we push opencv-annotated
    frames into.  The GLib main loop runs on a background thread so it doesn't
    block the detection loop.
    """

    def __init__(self, port: str, path: str, width: int, height: int, fps: int):
        Gst.init(None)

        self.width  = width
        self.height = height
        self.fps    = fps
        self._appsrc = None          # set once the pipeline is first used

        # Create context and loop explicitly before attach()
        self._context = GLib.MainContext.new()
        self._loop    = GLib.MainLoop.new(self._context, False)

        # Build the server
        self._server = GstRtspServer.RTSPServer()
        self._server.set_service(port)
        self._server.attach(self._context)

        # Connect client callback for diagnostics
        self._server.connect("[SERVER] client-connected", self._on_client_connected)

        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(
            f"(appsrc name=src "
            f"caps=video/x-raw,format=BGR,width={width},height={height},"
            f"framerate={fps}/1 "
            f"block=true format=time is-live=true ! "
            f"videoconvert ! "
            f"video/x-raw,format=I420 ! "
            f"nvv4l2h264enc bitrate=4000000 iframeinterval=30 ! "
            f"h264parse ! "
            f"rtph264pay name=pay0 pt=96 config-interval=1 )"
        )
        factory.set_shared(True)    # one pipeline shared across all clients
        factory.connect("media-configure", self._on_media_configure)

        self._server.get_mount_points().add_factory(path, factory)
         
        print(f"[RTSP] Server initialised on port {port}, path {path}")
    

        # Run GLib loop on a daemon thread
        self._context = GLib.MainContext.new()
        self._loop = GLib.MainLoop.new(self._context, False)
        self._loop = GLib.MainLoop()
        t = threading.Thread(target=self._loop.run, daemon=True)
        t.start()

        print(f"[SERVER] RTSP streaming live at rtsp://0.0.0.0:{port}{path}")

    def _on_media_configure(self, factory, media):
        """Called when a client triggers pipeline creation — grab the appsrc."""
        pipeline = media.get_element()
        print("[SERVER] Client connected, pipeline being configured")
        self._appsrc = pipeline.get_by_name("src")

    
    def _on_client_connected(self, server, client):
        print(f"[SERVER] TCP connection received from client")

    def push_frame(self, frame: np.ndarray):
        """Push a BGR numpy frame into the RTSP pipeline."""
        if self._appsrc is None:
            return  # no client connected yet, nothing to push to

        data    = frame.tobytes()
        buf     = Gst.Buffer.new_allocate(None, len(data), None)
        buf.fill(0, data)

        # Timestamping
        pts            = time.monotonic_ns()
        buf.pts        = pts
        buf.duration   = int(1e9 / self.fps)

        ret = self._appsrc.emit("push-buffer", buf)
        if ret != Gst.FlowReturn.OK:
            print(f"[WARN] appsrc push-buffer returned {ret}")
    
    def stop(self):
        """Cleanly shut down the event loop and wait for the thread to exit."""
        if self._loop and self._loop.is_running():
            self._loop.quit()