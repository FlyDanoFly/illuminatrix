from games.StoryTimeBase import StoryTimeBase


class StoryTimePlants(StoryTimeBase):
    # TODO: Make the proxy class cleaner than this hack
    PROXY = False

    STORY_SPEC_CSV: str = "sound_banks/story_time/plants/Story mode_ Stories - Plants.csv"
    SOUND_BANK: str = "sound_banks/story_time/plants"
