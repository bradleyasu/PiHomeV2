from networking.spotify import Spotify


width = 800
height = 480 

# pygame.display.init()


def main():
    spotify = Spotify(id="", secret="")   
    print(spotify.get_currently_playing())


main()