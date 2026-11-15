# MQTT

Connect to an MQTT broker over WiFi and exchange data with the O Bricks dashboard or other devices. Data is "topic + data", where the data is JSON (for example `35`, `[0.5, -0.2]`, `"hello"`), the same as the dashboard.

The hub needs WiFi, for example a Raspberry Pi Pico W or Pico 2 W.

## Using it with the dashboard

1. In the hub program, put "**connect to WiFi**" first, then "**connect to MQTT broker**" (the default is `broker.hivemq.com`, the same as the dashboard default).
2. On the dashboard, press "**Connect**" on the right of the tab bar, keep the default HiveMQ broker and connect.
3. Both sides must use the **same prefix** (or both leave it empty).
4. The hub reads topics sent by dashboard controls (joystick, slider, button, switch) with "**MQTT topic … number**" and "**MQTT topic … has new data?**". Data the hub sends with "**MQTT send**" shows up in dashboard value displays and charts.

| Dashboard control | Data it sends | Read it on the hub with |
|---|---|---|
| Slider | A number, e.g. `70` | MQTT topic robot/speed number #1 |
| Joystick | `[x, y]`, -1 to 1 | x is #1, y is #2 |
| Button | `1` when pressed, `0` when released | MQTT topic robot/stop has new data? |
| Switch | `1` on, `0` off | MQTT topic robot/led number #1 |

## Blocks

- **connect to WiFi name … password …**: waits up to 15 seconds and prints the IP in the console.
- **connect to MQTT broker … prefix …**: the prefix is optional. Reconnects automatically if the connection drops.
- **MQTT send topic … data …**: numbers, text or true/false.
- **MQTT topic … has new data?**: true once each time new data arrives. Use it in an "if".
- **MQTT topic … number #…**: the last number received; picks one when the data has several numbers. 0 until something arrives.
- **MQTT topic … latest data**: the last data received (number, text or list), or None until something arrives.

The libraries the program uses (`obricks_mqtt.py`, `mqtt_simple.py`) are written to `lib/` in the project folder on the hub automatically when you run or download the program. You do not need to copy them yourself.

The blocks that read data also handle incoming messages each time they run, so just put them in a "forever" loop. There is no separate receive code to write, and a topic is subscribed automatically the first time it is read.

## Notes

- **The WiFi password is stored in the program**: remove it before sharing a project or sample.
- **A public broker is shared by everyone**: anyone may see the data you send or send data in, so do not send anything sensitive. To keep your topics from clashing with other people, add a prefix (for example `myclass/team1`) and use the same prefix on the dashboard.
- The hub connects over MQTT TCP port 1883 (the dashboard uses WebSocket in the browser). Both connect to the same broker, so they can talk to each other.
- If the firmware has `umqtt.simple`, it is used; otherwise the copy included in this extension is used (umqtt.simple from micropython-lib, MIT license).
