class Color():
    ''' LIGHT TOKENS — warm/cozy neutral ramp (sand/taupe tinted) '''
    GRAY_50 = '#FFFFFF'
    GRAY_75 = '#FBF8F3'
    GRAY_100 = '#F4EFE8'   # page background
    GRAY_200 = '#E7DFD3'   # header band / secondary surface
    GRAY_300 = '#DCD2C4'   # border / divider
    GRAY_400 = '#CFC6B6'   # switch inactive
    GRAY_500 = '#AFA28D'
    GRAY_600 = '#8A7C68'
    GRAY_700 = '#6E6354'   # text secondary
    GRAY_800 = '#443D34'
    GRAY_900 = '#2D2823'   # text primary (warm near-black)

    # Warm explicit surfaces (new)
    SURFACE = '#FFFFFF'    # raised card on cream page
    BORDER  = '#DCD2C4'

    # Clay / terracotta accent (new)
    CLAY_400 = '#BC6240'   # primary accent
    CLAY_500 = '#A8522F'   # pressed / darker accent
    CLAY_600 = '#954820'

    # Muted slate-blue kept for semantic "info"
    BLUE_400 = '#4F7CA6'
    BLUE_500 = '#446F97'
    BLUE_600 = '#3A6188'
    BLUE_700 = '#A8522F'   # legacy alias -> clay pressed (button primary_accent)

    RED_400 = '#C0473D'    # brick red
    RED_500 = '#AE3E35'
    RED_600 = '#9C352D'
    RED_700 = '#8A2C25'

    ORANGE_400 = '#D08A2E'  # amber
    ORANGE_500 = '#C07E27'
    ORANGE_600 = '#B07220'
    ORANGE_700 = '#A06619'

    GREEN_400 = '#5E8C5A'   # sage
    GREEN_500 = '#527E4F'
    GREEN_600 = '#477044'
    GREEN_700 = '#3C6239'

    INDIGO_400 = '#6767ec'
    INDIGO_500 = '#5c5ce0'
    INDIGO_600 = '#5151d3'
    INDIGO_700 = '#4646c6'

    CELERY_400 = '#44b556'
    CELERY_500 = '#3da74e'
    CELERY_600 = '#379947'
    CELERY_700 = '#318b40'

    MAGENTA_400 = '#d83790'
    MAGENTA_500 = '#ce2783'
    MAGENTA_600 = '#bc1c74'
    MAGENTA_700 = '#ae0e66'

    YELLOW_400 = '#dfbf00'
    YELLOW_500 = '#d2b200'
    YELLOW_600 = '#c4a600'
    YELLOW_700 = '#b79900'

    FUCHSIA_400 = '#c038cc'
    FUCHSIA_500 = '#b130bd'
    FUCHSIA_600 = '#a228ad'
    FUCHSIA_700 = '#93219e'

    SEAFOAM_400 = '#1b959a'
    SEAFOAM_500 = '#16878c'
    SEAFOAM_600 = '#0f797d'
    SEAFOAM_700 = '#096c6f'

    CHARTREUSE_400 = '#85d044'
    CHARTREUSE_500 = '#7cc33f'
    CHARTREUSE_600 = '#73b53a'
    CHARTREUSE_700 = '#6aa834'

    PURPLE_400 = '#9256d9'
    PURPLE_500 = '#864ccc'
    PURPLE_600 = '#7a42bf'
    PURPLE_700 = '#6f38b1'


    ''' DARK TOKENS — warm charcoal ramp (brown-tinted, not blue-black) '''
    DARK_GRAY_50 = '#322E28'   # raised surface / secondary button bg
    DARK_GRAY_75 = '#2B2722'   # header band (elevated above page)
    DARK_GRAY_100 = '#221F1B'  # page background (deepest)
    DARK_GRAY_200 = '#3E3933'  # border
    DARK_GRAY_300 = '#4A443C'  # switch inactive
    DARK_GRAY_400 = '#4A443C'
    DARK_GRAY_500 = '#6E6354'
    DARK_GRAY_600 = '#8A7C68'
    DARK_GRAY_700 = '#B5AA9A'
    DARK_GRAY_800 = '#B5AA9A'  # text secondary
    DARK_GRAY_900 = '#F5F0E8'  # text primary (warm white)

    # Warm explicit surfaces (new)
    DARK_SURFACE = '#322E28'
    DARK_BORDER  = '#3E3933'

    # Clay / terracotta accent (new)
    DARK_CLAY_400 = '#DB8A63'
    DARK_CLAY_500 = '#C77A54'
    DARK_CLAY_600 = '#B36A46'

    # Muted slate-blue kept for semantic "info"
    DARK_BLUE_400 = '#6FA0CB'
    DARK_BLUE_500 = '#7FACD3'
    DARK_BLUE_600 = '#8FB8DB'
    DARK_BLUE_700 = '#221F1B'  # legacy alias -> warm near-black (text on primary)

    DARK_RED_400 = '#E0685E'
    DARK_RED_500 = '#E87A71'
    DARK_RED_600 = '#F08C84'
    DARK_RED_700 = '#F89E97'

    DARK_ORANGE_400 = '#E9A94A'
    DARK_ORANGE_500 = '#EEB661'
    DARK_ORANGE_600 = '#F3C378'
    DARK_ORANGE_700 = '#F8D08F'

    DARK_GREEN_400 = '#82B07C'
    DARK_GREEN_500 = '#91BB8B'
    DARK_GREEN_600 = '#A0C69A'
    DARK_GREEN_700 = '#AFD1A9'

    DARK_INDIGO_400 = '#6767ec'
    DARK_INDIGO_500 = '#7575f1'
    DARK_INDIGO_600 = '#8282f6'
    DARK_INDIGO_700 = '#9090fa'

    DARK_CELERY_400 = '#44b556'
    DARK_CELERY_500 = '#4bc35f'
    DARK_CELERY_600 = '#51d267'
    DARK_CELERY_700 = '#58e06f'

    DARK_MAGENTA_400 = '#d83790'
    DARK_MAGENTA_500 = '#e2499d'
    DARK_MAGENTA_600 = '#ec5aaa'
    DARK_MAGENTA_700 = '#f56bb7'

    DARK_YELLOW_400 = '#dfbf00'
    DARK_YELLOW_500 = '#edcc00'
    DARK_YELLOW_600 = '#fad900'
    DARK_YELLOW_700 = '#ffe22e'

    DARK_FUCHSIA_400 = '#c038cc'
    DARK_FUCHSIA_500 = '#cf3edc'
    DARK_FUCHSIA_600 = '#d951e5'
    DARK_FUCHSIA_700 = '#e366ef'

    DARK_SEAFOAM_400 = '#1b959a'
    DARK_SEAFOAM_500 = '#20a3a8'
    DARK_SEAFOAM_600 = '#23b2b8'
    DARK_SEAFOAM_700 = '#26c0c7'

    DARK_CHARTREUSE_400 = '#85d044'
    DARK_CHARTREUSE_500 = '#8ede49'
    DARK_CHARTREUSE_600 = '#9bec54'
    DARK_CHARTREUSE_700 = '#a3f858'

    DARK_PURPLE_400 = '#9256d9'
    DARK_PURPLE_500 = '#9d64e1'
    DARK_PURPLE_600 = '#a873e9'
    DARK_PURPLE_700 = '#b483f0'
