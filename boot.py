import time
import network
from lib.dotenv import load

env = load()
ssid = env.get("WIFI_SSID", "")
password = env.get("WIFI_PASSWORD", "")

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
if ssid and not wlan.isconnected():
    wlan.connect(ssid, password)
    for _ in range(20):
        if wlan.isconnected():
            break
        time.sleep(0.5)

print("WiFi:", wlan.ifconfig()[0] if wlan.isconnected() else "FAILED")
