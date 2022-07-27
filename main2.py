import pygame


width = 800
height = 480 

# pygame.display.init()


def main():
    pygame.init()
    DISPLAY = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
    # DISPLAY = pygame.display.set_mode((1000,500),0,32)
    WHITE = (255,255,255)
    blue = (0,0,255)
    DISPLAY.fill(WHITE)
    pygame.mouse.set_visible(False)
    pygame.draw.rect(DISPLAY, blue,(480,200,50,250))
    pygame.display.update()
    pygame.mouse.set_pos(480, 200)
    while True:
        for event in pygame.event.get():
            pos = pygame.mouse.get_pos()
            pygame.draw.rect(DISPLAY, blue, (pos[0]-25,pos[1], 50, 250))
            pygame.display. update()
            DISPLAY.fill(WHITE)

            if event.type == pygame.QUIT:
                pygame.quit()
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    running = False
main()