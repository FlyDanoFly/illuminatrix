from games.StoryTimeBase import StoryTimeBase


class StoryTimeHorror(StoryTimeBase):
    # TODO: Make the proxy class cleaner than this hack
    PROXY = False

    STORY_SPEC_CSV: str = "sound_banks/story_time/gremoryland/Story mode_ Stories - GremoryLand (Sonya - in progress).csv"
    SOUND_BANK: str = "sound_banks/story_time/gremoryland"
