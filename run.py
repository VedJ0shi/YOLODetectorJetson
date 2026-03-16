import api
import notif
import detect

if __name__ == "__main__":
    #initialize api and notification services:
    api.start_surveillance_api()
    notif.start_surveillance_notifications()

    #launch main detection loop
    detect.start_camera_detection()

