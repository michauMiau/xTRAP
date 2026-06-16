import pygame
import socket
import math

# --- NETWORK ---
PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
sock.setblocking(False)

def network_thread():
    global latest_data
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            latest_data = data
        except:
            pass
# --- PYGAME ---
pygame.init()
screen = pygame.display.set_mode((200, 800))
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

# --- DATA ---
ax = ay = az = 0
max_g = 0

def draw_g_meter(surface, x, y, radius, ax, ay):
    pygame.draw.circle(surface, (100,100,100), (x,y), radius, 2)

    dot_x = int(x + ax * radius * 0.5)
    dot_y = int(y + ay * radius * 0.5)

    pygame.draw.circle(surface, (255,0,0), (dot_x, dot_y), 5)

running = True
while running:
    # --- INPUT ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # --- NETWORK ---
    try:
        data, _ = sock.recvfrom(1024)
        parts = data.decode().split(",")
        ax, ay, az = map(float, parts)
    except:
        pass

    g = math.sqrt(ax*ax + ay*ay + az*az)
    max_g = max(max_g, g)

    # --- DRAW ---
    screen.fill((20,20,20))

    # G meter
    draw_g_meter(screen, 100, 100, 60, ax, ay)

    # Text
    txt = font.render(f"G: {g:.2f}  MAX: {max_g:.2f}", True, (255,255,255))
    screen.blit(txt, (50, 200))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()