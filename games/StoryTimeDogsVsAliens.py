from games.StoryTimeBase import StoryTimeBase


class StoryTimeDogsVsAliens(StoryTimeBase):
    # TODO: Make the proxy class cleaner than this hack
    PROXY = False

    STORY_SPEC_CSV: str = "sound_banks/story_time/dogs_vs_aliens/Story mode_ Stories - Example_ Dog vs Aliens.csv"
    SOUND_BANK: str = "sound_banks/story_time/dogs_vs_aliens"
