import os
import sys
import time

# Deploy interrupt window: 2s where Ctrl+C can break in and .deploying takes effect.
# Essential for deploy.sh to reach raw REPL reliably after the DTR reset pulse.
for _ in range(20):
    if ".deploying" in os.listdir():
        sys.exit("Deploy mode — skipping main.py")
    time.sleep_ms(100)

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
