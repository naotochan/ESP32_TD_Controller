import time
import network
from lib.dotenv import load

env = load()

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
if not wlan.isconnected():
    wlan.connect(env["WIFI_SSID"], env["WIFI_PASSWORD"])
    for _ in range(20):
        if wlan.isconnected():
            break
        time.sleep(0.5)

print("WiFi:", wlan.ifconfig()[0] if wlan.isconnected() else "FAILED")
