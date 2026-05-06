from enum import StrEnum


class Legendary(StrEnum):
    NECK = "Neck"
    BOOTS = "Boots"
    FEET = "Boots"
    CLOAK = "Cloak"
    CAPE = "Cloak"
    BACK = "Cloak"


class Weapon(StrEnum):
    VOIDBRINGERS_TOUCH = "Voidbringer's Touch"
    CHRONOSHIFT = "Chronoshift"
    NATURES_FURY = "Nature's Fury"
    ICICLES_OF_ANZHYR = "Icicles of Anzhyr"


class MasterTrait(StrEnum):
    AMETHYST_SPLINTERS = "Amethyst Splinters"
    BRAVE_MACHINATIONS = "Brave Machinations"
    DIAMOND_STRIKE = "Diamond Strike"
    EMERALD_JUDGEMENT = "Emerald Judgement"
    HEROIC_BRAND = "Heroic Brand"
    MARTIAL_INITIATIVE = "Martial Initiative"
    RUBY_STORM = "Ruby Storm"
    SAPPHIRE_AURASTONE = "Sapphire Aurastone"
    VISIONS_OF_GRANDEUR = "Visions Of Grandeur"


class HeroicTrait(StrEnum):
    HIDDEN_POWER = "Hidden Power"
    HUNTERS_FOCUS = "Hunters Focus"
    INSPIRED_ALLEGIANCE = "Inspired Allegiance"
    KINDLING = "Kindling"
    NAVIGATORS_INTUITION = "Navigators Intuition"
    SEIZED_OPPORTUNITY = "Seized Opportunity"
    VENGEFUL_SOUL = "Vengeful Soul"
    WILLFUL_MOMENTUM = "Willful Momentum"
    PATIENT_SOUL = "Patient Soul"


class Gem(StrEnum):
    RED = "red__ruby"
    RUBY = "red__ruby"
    PURPLE = "purple__amethyst"
    AMETHYST = "purple__amethyst"
    YELLOW = "yellow__topaz"
    TOPAZ = "yellow__topaz"
    GREEN = "green__emerald"
    EMERALD = "green__emerald"
    BLUE = "blue__saphire"
    SAPHIRE = "blue__saphire"
    WHITE = "white__diamond"
    DIAMOND = "white__diamond"
