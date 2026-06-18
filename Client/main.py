"""Main client loop"""
import kivy
import threading
from state import state
from network import network_loop
#from widgets.g_meter import GMeter # TODO: Implement for kivy later
from widgets.battery import BatteryText # TODO: Refactor for kivy
#from widgets.orientation import Orientation  #  TODO: Implement for kivy later
from widgets.ui_panel import UIPanel # TODO: Refactor for kivy
from input import handle_input
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.utils import get_color_from_hex as color

#screen = pygame.display.set_mode((800, 200))
#clock = pygame.time.Clock()
#font = pygame.font.SysFont(None, 24)

#pygame.display.set_caption("RC Control Center")

#pygame._sdl2.controller.init() # Initialize the controller module for controlling with a pad

# --- START NETWORK THREAD ---
threading.Thread(target=network_loop, daemon=True).start()

# --- WIDGETS ---
#g_meter = GMeter(100, 100, 60) # Hardcoded position values my <3
battery = BatteryText(200, 50, font)
#orientation = Orientation(450, 100, 80)
ui = UIPanel()

running = True
while running:
    
    last_text_event = None
    
    for event in pygame.event.get():
        print(event) 
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.TEXTINPUT:
            last_text_event = event
        else:
            ui.handle_event(event)
    if last_text_event:
        ui.handle_event(last_text_event)
        
   
    screen.fill((20,20,20))

    # --- DRAW ---
    g_meter.draw(screen, state.ax, state.ay)
    battery.draw(screen, state)
    orientation.draw(screen, state.ax, state.ay, state.az)
    ui.draw(screen)
    handle_input()
    txt = font.render(f"G: {state.g:.2f} MAX: {state.max_g:.2f}", True, (255,255,255))
    screen.blit(txt, (200, 100))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
