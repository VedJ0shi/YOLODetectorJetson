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

        self.width   = width
        self.height  = height
        self.fps     = fps
        self._appsrc   = None   # set once a client triggers pipeline creation
        self._pipeline_playing = False  # True only after pipeline reaches PLAYING

        # FIX: Create ONE context and ONE loop bound to it.
        # Never create a second context or loop later in __init__.
        self._context = GLib.MainContext.new()
        self._loop    = GLib.MainLoop.new(self._context, False)

        # Build the server and attach it to the SAME context created above.
        self._server = GstRtspServer.RTSPServer()
        self._server.set_service(str(port))
        self._server.attach(self._context)   # must happen before the thread starts

        # Connect client callback for diagnostics.
        self._server.connect("client-connected", self._on_client_connected)

        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(
            f"( appsrc name=src "
            f"  caps=video/x-raw,format=BGR,width={width},height={height},"
            f"framerate={fps}/1 "
            f"  block=true format=time is-live=true ! "
            f"  videoconvert ! "
            f"  video/x-raw,format=NV12 ! "
            f"  nvv4l2h264enc bitrate=4000000 iframeinterval=30 ! "
            f"  h264parse ! "
            f"  rtph264pay name=pay0 pt=96 config-interval=1 )"
        )
        factory.set_shared(True)   # one pipeline shared across all clients
        factory.connect("media-configure", self._on_media_configure)

        self._server.get_mount_points().add_factory(path, factory)

        print(f"[SERVER] Server initialised on port {port}, path {path}")

        # FIX: Start the thread AFTER everything is set up, using the loop
        # that is already bound to self._context (where the server is attached).
        # Do NOT create any new context or loop after this point.
        t = threading.Thread(target=self._loop.run, daemon=True)
        t.start()

        print(f"[SERVER] RTSP streaming live at rtsp://0.0.0.0:{port}{path}")

    def _on_media_configure(self, factory, media):
        """Called when a client triggers pipeline creation — grab the appsrc
        and wait for the pipeline to reach PLAYING before allowing pushes."""
        pipeline = media.get_element()
        print("[SERVER] Pipeline being configured")
        self._appsrc = pipeline.get_by_name("src")
        self._pipeline_playing = False
        if self._appsrc is None:
            print("[WARN] Could not find appsrc element named 'src' in pipeline")
            return

        # Watch the bus for STATE_CHANGED so we know when PLAYING is reached.
        bus = media.get_element().get_bus()
        bus.add_signal_watch()
        bus.connect("message::state-changed", self._on_state_changed, pipeline)
        bus.connect("message::error", self._on_bus_error)

    def _on_state_changed(self, bus, message, pipeline):
        # Only care about state changes on the top-level pipeline element.
        if message.src != pipeline:
            return
        old, new, pending = message.parse_state_changed()
        if new == Gst.State.PLAYING:
            print("[SERVER] Pipeline is PLAYING — ready to receive frames")
            self._pipeline_playing = True
        elif new != Gst.State.PLAYING:
            self._pipeline_playing = False

    def _on_bus_error(self, bus, message):
        err, debug = message.parse_error()
        print(f"[SERVER] Pipeline error: {err.message} | debug: {debug}")

    def _on_client_connected(self, server, client):
        print("[SERVER] TCP connection received from client")

    def push_frame(self, frame: np.ndarray):
        """Push a BGR numpy frame into the RTSP pipeline."""
        if self._appsrc is None or not self._pipeline_playing:
            return   # no client connected, or pipeline not ready yet

        data = frame.tobytes()
        buf  = Gst.Buffer.new_allocate(None, len(data), None)
        buf.fill(0, data)

        # Monotonic timestamps are required by GStreamer for live sources.
        # time.monotonic_ns() was added in Python 3.7; use monotonic() * 1e9
        # for compatibility with the Python 3.6 on Jetson Nano.
        buf.pts      = int(time.monotonic() * 1e9)
        buf.duration = int(1e9 / self.fps)

        ret = self._appsrc.emit("push-buffer", buf)
        if ret != Gst.FlowReturn.OK:
            print(f"[WARN] appsrc push-buffer returned {ret}")

    def stop(self):
        """Cleanly shut down the event loop."""
        if self._loop and self._loop.is_running():
            self._loop.quit()