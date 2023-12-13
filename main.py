import machine, neopixel, dht, time, ssd1306

from machine import Pin, SoftI2C, ADC, PWM
from ssd1306 import SSD1306_I2C

from network import WLAN,STA_IF
from linenotify import LineNotify

# 初始化LED
pin = Pin(15, Pin.OUT)
num_leds = 8 
np = neopixel.NeoPixel(pin, num_leds)

# -------------------------
# 下雨腳位
d = Pin(4, Pin.IN)
adc_rain = ADC(Pin(4))

# 降電壓的概念
adc_rain.atten(ADC.ATTN_11DB)

# -------------------------
# 水位偵測設置
# 創建ADC對象，將引腳26用於連接傳感器
adc_water_level = ADC(Pin(26))

# 設置ADC的電壓範圍為11dB
adc_water_level.atten(ADC.ATTN_11DB)

# 傳感器規格
max_sensor_value = 65535  # 最大傳感器讀數
max_water_level_cm = 3.5  # 最大水位高度

# 計算轉換因子
conversion_factor = max_water_level_cm / max_sensor_value

# -------------------------
# 水泵腳位
pump_pin = Pin(5)

# 土壤溼度
adc_soil_moisture = ADC(Pin(25))

# 設置ADC的電壓範圍
adc_soil_moisture.atten(ADC.ATTN_11DB)

# 最乾燥和最潮濕的ADC讀數
max_dry = 4095
min_wet = 0
# ---------------------------------------
# 蜂鳴器腳位
buzzer_pin = Pin(2, Pin.OUT)

# ---------------------------------------
# OLED 螢幕設置
DISPLAY_WIDTH = 128   
DISPLAY_HEIGHT = 64
gpio_sda = 19
gpio_scl = 22
 
i2cbus = SoftI2C(sda=Pin(gpio_sda), scl=Pin(gpio_scl))

# ---------------------------------------
# 紅綠燈設定腳位
red_led = Pin(17, Pin.OUT)  
yellow_led = Pin(3, Pin.OUT)  
green_led = Pin(21, Pin.OUT)  

# 定義土壤需澆水濕度
low_moisture_threshold = 30  # 低於此觸發澆水

# ---------------------------------------
# 光源
light_sensor_pin = Pin(13, Pin.IN)

# ---------------------------------------

# 用於發送line
def connect_ap_and_send_msg(content):
    ssid = '...'
    password = '...'
    
    wlan = WLAN(STA_IF)
    wlan.active(True)

    print('Connecting...')
    wlan.connect(ssid,password)
    while not wlan.isconnected():
        pass

    print(wlan.ifconfig())

    line = LineNotify('...')
    line.notify(content)
    
    wlan.disconnect()
    wlan.active(False)


# 計算土壤溫溼度
def get_humidity_percentage():
    # 讀取
    adc_soil_moisture_reading = adc_soil_moisture.read()
    # 計算百分比
    humidity_percentage = 100 * (max_dry - adc_soil_moisture_reading) / (max_dry - min_wet)
    
    return humidity_percentage


# 用於辨識土壤濕度的紅綠燈
def soil_status_light(humidity_percentage):
    # 紅綠燈
    if humidity_percentage > 50:
        green_led.on()
        red_led.off()
        yellow_led.off()
    elif humidity_percentage > 25:
        yellow_led.on()
        green_led.off()
        red_led.off()
    else:
        red_led.on()
        green_led.off()
        yellow_led.off()

# ---------------------------------------
while True:
    # 取得目前土壤濕度
    humidity_percentage = get_humidity_percentage()
    
    # 紅綠燈
    soil_status_light(humidity_percentage)
    
    # 讀取傳感器值
    sensor_reading = adc_water_level.read_u16()

    # 使用轉換因子將傳感器讀數轉換為水位高度
    water_level_cm = sensor_reading * conversion_factor
    
    # 後續用於判斷容器是否有水以啟動水泵
    have_water = 1
    
    # 當容器的水低於1CM
    if water_level_cm < 1:
        have_water = 0
        buzzer_pwm = PWM(buzzer_pin)
        
        # 設定蜂鳴器的頻率和音量
        buzzer_pwm.freq(440)  # 設置頻率（440 Hz，代表中央C音符）
        buzzer_pwm.duty(512)  # 設置音量（0-1023）
 
        # 播放蜂鳴器聲音
        buzzer_pwm.duty(512)  # 打開蜂鳴器
        time.sleep(1)  # 播放時間
        buzzer_pwm.duty(0)  # 關閉蜂鳴器
 
        # 關閉PWM
        buzzer_pwm.deinit()
        
        # Line notify
        connect_ap_and_send_msg('水位過低，請加水')
        time.sleep(5)
        
    # -----------------------------------
    # 計算要點亮的LED數量
    num_active_leds = min(int(water_level_cm / max_water_level_cm * num_leds), num_leds)

    # 點亮LED燈
    for i in range(num_active_leds):
        np[i] = (66, 66, 245)

    # 關閉多餘的LED燈
    for i in range(num_active_leds, num_leds):
        np[i] = (0, 0, 0)

    np.write()
    
    # -----------------------------------
    # 顯示溫度和濕度
    d11 = dht.DHT11(Pin(10))
    d11.measure()
    temp = d11.temperature()
    humid = d11.humidity()
    # -----------------------------------
    # 偵測雨量大小
    if adc_rain.read() > 4000:
        rain_msg = '沒有雨'
    elif adc_rain.read() > 2500:
        rain_msg = '小雨'
    else:
        rain_msg = '下大雨'
        connect_ap_and_send_msg('下大雨，請把盆栽往室內移動')
        time.sleep(10)
    
    # --------------------------------
    if humidity_percentage < low_moisture_threshold and have_water == 1:
        # 啟動水泵
        pump_pin.init(Pin.OUT)#開啟馬達
        time.sleep(1)#執行一秒
        pump_pin.init(Pin.IN) #關閉馬達
    
    # -----------------------------------
    # 取得澆水後土壤濕度
    humidity_percentage = get_humidity_percentage()
    
    # 澆水後的紅綠燈
    soil_status_light(humidity_percentage)
        
    # -----------------------------------
    # 光源
    is_light = light_sensor_pin.value()
    
    if is_light == 0:
        light_msg = '有光照'
    else:
        light_msg = '無光照'
    
    # -----------------------------------
    # 顯示
    print(f'溫度：{temp} C')
    print(f'濕度：{humid}%')
    print(f'水位高度（cm)：{round(water_level_cm, 2)}')
    print(adc_rain.read(),'  ',rain_msg)
    print(rain_msg)
    print(f'土壤濕度百分比：{humidity_percentage:.2f}%')
    print(f'光源狀態：{light_msg}')
    
    msg = f'\n溫度：{temp} C\n濕度百分比：{humid}\n水位高度：{round(water_level_cm, 2)} cm\n下雨狀態：{rain_msg}\n土壤濕度百分比：{humidity_percentage:.2f}\n光源狀態：{light_msg}'
    
    connect_ap_and_send_msg(msg)
    # -----------------------------------
    # OLED 顯示
    display = ssd1306.SSD1306_I2C(DISPLAY_WIDTH, DISPLAY_HEIGHT, i2cbus)

    display.text(f'level {water_level_cm:.2f} cm', 0, 0, 1)
    display.text(f'temp {temp} C', 0, 15, 30)
    display.text(f'humid {humid} %', 0, 30, 45)
    display.text(f'soil {humidity_percentage} %', 0, 45, 60)

    display.show()
    
    # -----------------------------------
    time.sleep(10)




