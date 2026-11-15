# MQTT（O Bricks 擴充功能 mqtt 會把這個檔案上傳到主機上專案資料夾的 lib/）：連 WiFi、連 MQTT broker、送出、讀取收到的資料。
# 資料格式和 O Bricks 網頁的儀表板一樣：主題＋資料，資料是 JSON（例如 35、[0.5, -0.2]、"hello"）；
# 主機和儀表板連同一個 broker、用一樣的前綴，就能互傳。
# 讀資料的函式（value、number、has_new）每次被呼叫時會順便處理收到的訊息、定時送心跳，放在「重複執行」裡就好；
# 第一次讀某個主題時自動訂閱。斷線時自動重連（每 3 秒試一次）。
# MQTT 用戶端：韌體有 umqtt.simple 就用韌體的，沒有才用這個擴充附的 mqtt_simple.py（micropython-lib 的 umqtt.simple）。
# 主題、資料都先轉成 UTF-8 的 bytes 再交給它：umqtt.simple 用 len() 算長度，字串裡有中文時字數和位元組數不一樣，封包會壞掉
import json
import time
import network
import machine
import random
import ubinascii

try:
    from umqtt.simple import MQTTClient
except ImportError:
    from mqtt_simple import MQTTClient

PING_MS = 30000  # 多久沒送東西就送一次心跳（keepalive 是 60 秒）
RETRY_MS = 3000  # 斷線後多久重連一次
POLL_MAX = 20  # 每次最多處理幾筆收到的訊息

_client = None
_connected = False
_broker = ''
_prefix = ''
_subs = set()  # 讀過的主題（重連後重新訂閱）
_values = {}  # 主題 → 最後收到的資料
_fresh = set()  # 收到新資料、還沒被 has_new 讀過的主題
_last_send = 0
_last_retry = 0


def wifi(ssid, password, timeout=15):
    """連上 WiFi（最多等 timeout 秒），連上回傳 True"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('WiFi 連線中：', ssid)
        wlan.connect(ssid, password)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > timeout * 1000:
                print('WiFi 連不上：', ssid)
                return False
            time.sleep(0.2)
    print('WiFi 已連上，IP：', wlan.ifconfig()[0])
    return True


def connect(broker='broker.hivemq.com', prefix='', port=1883):
    """連上 MQTT broker；prefix 是主題前綴（選填，要和儀表板的連線設定一樣）。連上回傳 True"""
    global _client, _broker, _prefix
    _broker = broker.strip()
    _prefix = prefix.strip().strip('/')
    client_id = 'obricks-%s-%04x' % (ubinascii.hexlify(machine.unique_id()).decode()[-6:], random.getrandbits(16))
    _client = MQTTClient(client_id, _broker, port=port, keepalive=60)
    _client.set_callback(_on_message)
    return _open()


def send(topic, data):
    """把資料轉成 JSON 送到這個主題（數字、文字、清單、是／否都可以）。送出了回傳 True"""
    global _last_send
    _poll()
    if not _connected:
        return False
    try:
        _client.publish(_full(topic).encode(), json.dumps(data).encode())
        _last_send = time.ticks_ms()
        return True
    except Exception as e:
        _lost(e)
        return False


def value(topic):
    """這個主題最後收到的資料，還沒收到是 None"""
    _subscribe(topic)
    _poll()
    return _values.get(topic)


def number(topic, n=1):
    """這個主題最後收到的數字：資料是清單時拿第 n 個（從 1 開始，例如儀表板搖桿的 x 是 1、y 是 2）；沒有資料或不是數字時是 0"""
    v = value(topic)
    n = int(n)
    if isinstance(v, (list, tuple)):
        v = v[n - 1] if 0 < n <= len(v) else 0
    elif n != 1:
        v = 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


def has_new(topic):
    """這個主題收到新資料時回傳 True 一次（讀過就清掉）"""
    _subscribe(topic)
    _poll()
    if topic in _fresh:
        _fresh.discard(topic)
        return True
    return False


# ── 內部 ──

def _full(topic):
    return _prefix + '/' + topic if _prefix else topic


def _on_message(topic, msg):
    topic = topic.decode()
    if _prefix and topic.startswith(_prefix + '/'):
        topic = topic[len(_prefix) + 1:]
    try:
        text = msg.decode()
    except Exception:
        text = str(msg)
    try:
        data = json.loads(text)
    except ValueError:
        data = text  # 不是 JSON：當成文字（很多設備直接送 23.5、on 這種純文字）
    _values[topic] = data
    _fresh.add(topic)


def _open():
    global _connected, _last_send
    try:
        _client.connect()
        for topic in _subs:
            _client.subscribe(_full(topic).encode())
        _connected = True
        _last_send = time.ticks_ms()
        print('MQTT 已連上：', _broker)
    except Exception as e:
        _connected = False
        print('MQTT 連不上：', _broker, e)
    return _connected


def _lost(e):
    global _connected, _last_retry
    if _connected:
        print('MQTT 斷線：', e)
    _connected = False
    _last_retry = time.ticks_ms()


def _ready():
    # 連線中回傳 True；斷線時每 RETRY_MS 重連一次
    global _last_retry
    if _client is None:
        return False
    if _connected:
        return True
    if time.ticks_diff(time.ticks_ms(), _last_retry) < RETRY_MS:
        return False
    _last_retry = time.ticks_ms()
    return _open()


def _subscribe(topic):
    if topic in _subs:
        return
    _subs.add(topic)
    if _connected:
        try:
            _client.subscribe(_full(topic).encode())
        except Exception as e:
            _lost(e)


def _poll():
    # 處理收到的訊息（不會卡住）、太久沒送東西就送心跳
    global _last_send
    if not _ready():
        return
    try:
        for _ in range(POLL_MAX):
            if _client.check_msg() is None:
                break
        if time.ticks_diff(time.ticks_ms(), _last_send) > PING_MS:
            _client.ping()
            _last_send = time.ticks_ms()
    except Exception as e:
        _lost(e)
