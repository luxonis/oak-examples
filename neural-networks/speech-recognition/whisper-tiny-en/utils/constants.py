from enum import IntEnum


class Tokens(IntEnum):
    TOKEN_SOT = 50257  # Start of transcript
    TOKEN_EOT = 50256  # End of transcript
    TOKEN_BLANK = 220  # Blank token " "
    TOKEN_NO_TIMESTAMP = 50362
    TOKEN_TIMESTAMP_BEGIN = 50363
    TOKEN_NO_SPEECH = 50361


class Config:
    """Configuration constants."""

    NON_SPEECH_TOKENS = [
        1,
        2,
        7,
        8,
        9,
        10,
        14,
        25,
        26,
        27,
        28,
        29,
        31,
        58,
        59,
        60,
        61,
        62,
        63,
        90,
        91,
        92,
        93,
        357,
        366,
        438,
        532,
        685,
        705,
        796,
        930,
        1058,
        1220,
        1267,
        1279,
        1303,
        1343,
        1377,
        1391,
        1635,
        1782,
        1875,
        2162,
        2361,
        2488,
        3467,
        4008,
        4211,
        4600,
        4808,
        5299,
        5855,
        6329,
        7203,
        9609,
        9959,
        10563,
        10786,
        11420,
        11709,
        11907,
        13163,
        13697,
        13700,
        14808,
        15306,
        16410,
        16791,
        17992,
        19203,
        19510,
        20724,
        22305,
        22935,
        27007,
        30109,
        30420,
        33409,
        34949,
        40283,
        40493,
        40549,
        47282,
        49146,
        50257,
        50357,
        50358,
        50359,
        50360,
        50361,
    ]
    TOKENS = Tokens
    SAMPLE_BEGIN = 1  # first token is TOKEN_SOT
    NO_SPEECH_THR = 0.6  # Above this prob we deem there's no speech in the audio
    PRECISION = 0.02  # in seconds
    MAX_INITIAL_TIMESTAMP = 1.0  # in seconds
    MAX_INITIAL_TIMESTAMP_INDEX = int(MAX_INITIAL_TIMESTAMP / PRECISION)
    MEAN_DECODE_LEN = 224  # The official default max decoded length is 448.
    LED_COLORS = {
        "red": (0, 0, 255),
        "green": (0, 255, 0),
        "blue": (255, 0, 0),
        "yellow": (0, 255, 255),
        "cyan": (255, 255, 0),
        "magenta": (255, 0, 255),
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "orange": (0, 165, 255),
        "pink": (203, 192, 255),
        "purple": (128, 0, 128),
        "brown": (19, 69, 139),
    }
