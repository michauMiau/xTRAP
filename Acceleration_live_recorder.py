""" TEST PROGRAM: Live recorder for acceleration data from IMU sensor."""
import machine
import time
import math
import os

from lib.display import Display
from lib.userinput import UserInput
from lib.userinput import bmi270
from machine import I2C

ZERO_Y = 75

# --- INICJALIZACJA EKRANU I KLAWSZY ---
display = Display()
userinput = UserInput()

# Kolory (RGB565)
WHITE = 0xFFFF
RED   = 0xF800
GREEN = 0x07E0
BLUE  = 0x001F
DARK  = 0x2104 # Ciemnoszary dla linii bazowej
ORANGE = 0x23F5
# --- ZMIENNE WYKRESU ---
W = 240 # Szerokość ekranu
# Bufory na historię pomiarów (przechowują pozycję Y na ekranie)
hist_x = [75] * W
hist_y = [75] * W
hist_z = [75] * W
hist_g = [75] * W

# --- INICJALIZACJA CZUJNIKA BMI270 ---
# UWAGA: Upewnij się, że piny SDA i SCL zgadzają się z Twoim fizycznym podłączeniem!
# Użyłem pinów z Twojej dokumentacji (2 i 3). W Cardputerze złącze Grove to zazwyczaj SDA=2, SCL=1.
i2c = I2C(0)
imu = bmi270.BMI270(i2c)

def read_bmi270():
    try:
        # Odczyt bezpośrednio z atrybutu .acceleration tak jak w docsach
        ax, ay, az = imu.acceleration
        return ax, ay, az
    except Exception:
        # W razie błędu odczytu zwracamy zera, żeby wykres się nie zawiesił
        return 0.0, 0.0, 0.0

def map_value(val, in_min=-2.0, in_max=2.0, out_min=130, out_max=20):
    # Przelicza wartość z czujnika (np. od -2g do +2g) na piksele Y (od dołu 130 do góry 20)
    # Ucinamy wartości poza ekranem
    val = max(min(val, in_max), in_min)
    return int((val - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

# --- FUNKCJA OBLICZANIA SIŁY G ---
def get_g_force(ax, ay, az):
    # Wzór na wypadkową: G = sqrt(ax^2 + ay^2 + az^2)
    return math.sqrt(ax**2 + ay**2 + az**2)

# --- KONFIGURACJA BLACK BOX ---
SD_MOUNT = "/sd"
current_log_file = ""
is_recording = False
is_paused = False

def get_next_filename():
    i = 1
    while True:
        fname = "{}/blackbox_{}.csv".format(SD_MOUNT, i)
        try:
            os.stat(fname) # Sprawdza czy plik istnieje
            i += 1
        except OSError: # Jeśli nie istnieje, to mamy nasz numer
            return fname

# --- INICJALIZACJA SD ---
try:
    sd = machine.SDCard(slot=1, width=1)
    os.mount(sd, SD_MOUNT)
    sd_ready = True
except Exception:
    sd_ready = False
    

    
# --- POPRAWIONA PĘTLA GŁÓWNA ---
running = True
while running:
    # 1. Obsługa klawiszy (zawsze aktywna, nawet w pauzie)
    try:
        keys = userinput.get_new_keys()
        for k in keys:
            if k == 'ESC':
                machine.reset()
            elif k == 'ENT':
                # START NAGRYWANIA
                print("Started Recording")
                current_log_file = get_next_filename()
                with open(current_log_file, "w") as f:
                    f.write("timestamp_ms,ax,ay,az,g_total,event\n")
                is_recording = True
                is_paused = False
            elif k == 'SPC':
                # PAUZA / WZNOWIENIE
                is_paused = not is_paused
    except Exception:
        pass

    # 2. Logika i rysowanie (tylko jeśli NIE ma pauzy)
    if not is_paused:
        ax, ay, az = read_bmi270()
        g_total = get_g_force(ax, ay, az)
        
        # Nagrywanie do pliku (tylko jeśli wciśnięto ENT i nie ma pauzy)
        if is_recording:
            ACCIDENT_THRESHOLD = 3.0
            is_crash = g_total > ACCIDENT_THRESHOLD
            try:
                with open(current_log_file, "a") as f:
                    f.write("{},{:.2f},{:.2f},{:.2f},{:.2f},{}\n".format(
                        time.ticks_ms(), ax, ay, az, g_total, "CRASH" if is_crash else ""
                    ))
                    print("{},{:.2f},{:.2f},{:.2f},{:.2f},{}\n".format(
                        time.ticks_ms(), ax, ay, az, g_total, "CRASH" if is_crash else ""
                    ))
            except Exception:
                pass

        # Aktualizacja wykresów
        py_x, py_y, py_z = map_value(ax), map_value(ay), map_value(az)
        py_g = map_value(g_total - 1.0)
        
        hist_x.pop(0)
        hist_x.append(py_x)
        hist_y.pop(0)
        hist_y.append(py_y)
        hist_z.pop(0)
        hist_z.append(py_z)
        hist_g.pop(0)
        hist_g.append(py_g)

        display.fill(0)
        display.hline(0, ZERO_Y, W, DARK)
        for i in range(1, W):
            display.line(i-1, hist_x[i-1], i, hist_x[i], RED)
            display.line(i-1, hist_y[i-1], i, hist_y[i], GREEN)
            display.line(i-1, hist_z[i-1], i, hist_z[i], BLUE)
            display.line(i-1, hist_g[i-1], i, hist_g[i], ORANGE)
    else:
        # Jeśli pauza, nie czyścimy ekranu całkowicie, tylko nakładamy napis
        display.rect(80, 60, 80, 20, 0, fill=True)
        display.text("PAUSE", 100, 65, WHITE)

    # 3. Panel statusu (zawsze widoczny)
    display.rect(0, 0, 240, 18, 0, fill=True)
    
    if is_paused:
        status = "|| PAUSED"
        col = WHITE
    elif is_recording:
        # Pokazuje nazwę aktualnego pliku
        fname = current_log_file.split("/")[-1]
        status = "REC: {} G:{:.2f}".format(fname, g_total)
        col = RED if (time.ticks_ms() // 500) % 2 else WHITE # Mruga na czerwono
    else:
        status = "READY: PRESS ENT TO REC"
        col = GREEN if sd_ready else RED

    display.text(status, 5, 2, col)
    display.show()
    
    time.sleep(0.05 if not is_paused else 0.2)
