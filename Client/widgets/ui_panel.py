"""UI Panel, contains some buttons"""
class Button:
    def __init__(self, rect, text):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.active = not self.active
                return True
        return False

    def draw(self, surface, font):
        color = (0,200,0) if self.active else (80,80,80)
        pygame.draw.rect(surface, color, self.rect)
        txt = font.render(self.text, True, (255,255,255))
        surface.blit(txt, (self.rect.x+5, self.rect.y+5))

class Slider:
    def __init__(self, x, y, w, min_val=0, max_val=1):
        self.rect = pygame.Rect(x, y, w, 10)
        self.value = 0
        self.dragging = False
        self.min = min_val
        self.max = max_val

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.dragging = True

        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False

        elif event.type == pygame.MOUSEMOTION and self.dragging:
            rel = (event.pos[0] - self.rect.x) / self.rect.w
            self.value = max(0, min(1, rel))

    def draw(self, surface):
        pygame.draw.rect(surface, (100,100,100), self.rect)
        knob_x = self.rect.x + int(self.value * self.rect.w)
        pygame.draw.circle(surface, (255,255,255), (knob_x, self.rect.y+5), 6)
        
class TextBox:
    def __init__(self, x, y, w, default=""):
        self.rect = pygame.Rect(x, y, w, 25)
        self.text = default
        self.active = False
        self.cursor_timer = 0
        self.cursor_visible = True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            was_active = self.active
            self.active = self.rect.collidepoint(event.pos)

            # 🔥 ONLY enable text input when focused
            if self.active and not was_active:
                pygame.key.start_text_input()
                pygame.key.set_text_input_rect(self.rect)

            elif not self.active and was_active:
                pygame.key.stop_text_input()
                # TODO: update IP display when cardputer disconnects
                

        if not self.active:
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]

            elif event.key == pygame.K_RETURN:
                self.active = False
                pygame.key.stop_text_input()

        elif event.type == pygame.TEXTINPUT:
            if event.text and event.text[0] in "0123456789.":
                self.text += event.text[0]
                
    def update(self):
        self.cursor_timer += 1
        if self.cursor_timer > 30:
            self.cursor_timer = 0
            self.cursor_visible = not self.cursor_visible

    def draw(self, surface, font):
        color = (255,255,255) if self.active else (150,150,150)
        pygame.draw.rect(surface, color, self.rect, 2)

        txt = font.render(self.text, True, (255,255,255))
        surface.blit(txt, (self.rect.x+5, self.rect.y+5))

        # blinking cursor
        if self.active and self.cursor_visible:
            cx = self.rect.x + 5 + txt.get_width()
            cy = self.rect.y + 5
            pygame.draw.line(surface, (255,255,255), (cx, cy), (cx, cy+18))
            
DEFAULT_IP_PREFIX = "192.168.1.174"

class UIPanel:
    def __init__(self):
        self.font = pygame.font.SysFont(None, 20)

        # --- BUTTON GRID ---
        self.buttons = []
        labels = ["Flash", "Front", "Back", "Focus"]

        for i, label in enumerate(labels):
            x = 20 + (i % 4) * 80
            y = 20 + (i // 4) * 40
            self.buttons.append(Button((x, y, 70, 30), label))

        # --- SLIDERS ---
        self.zoom_slider = Slider(400, 20, 150)
        self.quality_slider = Slider(400, 60, 150)

        # --- TEXT INPUTS ---
        self.cardputer_ip = TextBox(600, 20, 150, DEFAULT_IP_PREFIX)
        self.phone_ip = TextBox(600, 60, 150, DEFAULT_IP_PREFIX)

    def handle_event(self, event):
        for b in self.buttons:
            b.handle_event(event)

        self.zoom_slider.handle_event(event)
        self.quality_slider.handle_event(event)

        self.cardputer_ip.handle_event(event)
        self.phone_ip.handle_event(event)

    def draw(self, surface):
        for b in self.buttons:
            b.draw(surface, self.font)

        self.zoom_slider.draw(surface)
        self.quality_slider.draw(surface)

        self.cardputer_ip.draw(surface, self.font)
        self.phone_ip.draw(surface, self.font)

        # labels
        surface.blit(self.font.render("Zoom", True, (255,255,255)), (360, 15))
        surface.blit(self.font.render("Quality", True, (255,255,255)), (340, 55))

        surface.blit(self.font.render("Car IP", True, (255,255,255)), (600, 0))
        surface.blit(self.font.render("Phone IP", True, (255,255,255)), (600, 40))
