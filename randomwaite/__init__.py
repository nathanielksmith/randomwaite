# TODO emoji suites
# TODO twitter responding / celery queue

import math
import re
import sys
import typing as t
from enum import Enum
from functools import partial
from io import BytesIO
from os import path
from random import choice, random, randrange, randint

import tweepy
from flickrapi.core import FlickrAPI
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageEnhance
from pixelsorter.sort import sort_image

from . import secrets as sec
from .cards import TarotCard, draw_tarot_card
from .flickr import get_photo
from .sentiment import POSITIVE, NEGATIVE

DEBUG = True
R = 0
G = 1
B = 2
CARD_WIDTH = 385
CARD_HEIGHT = 666
ZOOM_CHANCE = .25
FONT_PATH = path.join(path.dirname(__file__), 'fonts')
# repeats == increased likelihood
FONTS = [
    'alegreya.ttf',
    'antic_didone.ttf',
    'cinzel.ttf',
    'juliussans.ttf',
    'oswald.ttf',
    'vcr.ttf',
    'amatica.ttf',
    'bree.ttf',
    'vcr.ttf',
    'cormorant_infant.ttf',
    'imfell.ttf',
    'lobster.ttf',
    'palanquin.ttf',
    'vt323.ttf',
    'vcr.ttf',
    'amethysta.ttf',
    'cantata.ttf',
    'cutive.ttf',
    'jacques.ttf',
    'nothing.ttf',
    'tangerine.ttf',
]

ROMAN_TABLE = {
    'two': 'ii',
    'three': 'iii',
    'four': 'iv',
    'five': 'v',
    'six': 'vi',
    'seven': 'vii',
    'eight': 'viii',
    'nine': 'ix',
    'ten': 'x',
}
TITLE_ALIGNS = ('left', 'right', 'center')
TITLE_SIZES = {
    'large': 50,
    'small': 32,
    'stupid': 80,
}

Fill = t.Tuple[int]
TitlePlacement = Enum('TitlePlacement', 'top bottom middle random')

break_string_re = re.compile(' ')

def random_color() -> Fill:
    return (
        randrange(0,255),
        randrange(0,255),
        randrange(0,255),
    )

def maybe_romanize(text: str) -> str:
    for english,roman in ROMAN_TABLE.items():
        if re.search(english, text, flags=re.I):
            return re.sub(english, roman, text, flags=re.I)
    return text


def random_crop(original: Image) -> Image:
    min_x0 = 0
    max_x0 = original.width - CARD_WIDTH
    min_y0 = 0
    max_y0 = original.height - CARD_HEIGHT

    print('min x0', min_x0)
    print('max x0', max_x0)
    print('min y0', min_y0)
    print('max y0', max_y0)

    if max_y0 <= 0 or max_x0 <= 0:
        raise Exception('Got weird image')

    x0 = choice(range(min_x0, max_x0))
    y0 = choice(range(min_y0, max_y0))
    x1 = x0 + CARD_WIDTH
    y1 = y0 + CARD_HEIGHT

    print('CROPPING AT {}, {}, {}, {}'.format(x0, y0, x1, y1))

    return original.crop((x0, y0, x1, y1))


def maybe_zoom(original: Image) -> Image:
    zoom_level = 1 + random()
    new_width = math.floor(original.width * zoom_level)
    new_height = math.floor(original.height * zoom_level)

    print('ZOOMING AT', zoom_level)

    resized = original.resize((new_width, new_height))

    return random_crop(resized)


def color_balance(card: TarotCard, original: Image) -> Image:
    # TODO
    return original

def get_font_path() -> str:
    # TODO perhaps take a card and tie font to card
    return path.join(FONT_PATH, choice(FONTS))


def place_title(card: TarotCard, im: Image) -> Image:
    # boilerplate
    title = card.name
    position = choice(list(TitlePlacement))
    size = choice(list(TITLE_SIZES.keys()))
    align = choice(TITLE_ALIGNS)
    im = im.convert('RGBA')
    font_path = get_font_path()
    print('USING FONT', font_path)
    fnt = ImageFont.truetype(font_path, TITLE_SIZES[size])
    txt = Image.new('RGBA', im.size, (0,0,0,0))
    d = ImageDraw.Draw(txt)
    print(title)
    print(position)
    print(size)
    print(align)

    # ~ * randomness * ~
    if random() < .5:
        title = maybe_romanize(title)

    if random() < .6:
        if random() < .5:
            title = title.lower()
        else:
            title = title.upper()

    # check to see if we'd go out of bounds and split text if so
    if d.textsize(title, fnt)[0] > im.width:
        title = break_string_re.sub('\n', title)

    text_w, text_h = d.textsize(title, fnt)

    text_x = 0
    if text_w < im.width:
        text_x += randrange(0, im.width - text_w)

    if position == TitlePlacement.top:
        text_y = 0
    elif position == TitlePlacement.middle:
        text_y = im.height // 2
        if text_y + text_h > im.height:
            position = TitlePlacement.bottom
    elif position == TitlePlacement.bottom:
        text_y = im.height - text_h
    elif position == TitlePlacement.random:
        text_y = randrange(0, (im.height - text_h))

    print(text_x, text_y, text_w, text_h)

    # actual drawing
    text_fill = random_color()
    text_r,text_g,text_b = text_fill
    background_fill = map(lambda i: 255 - i, text_fill)
    bg_r, bg_g, bg_b = background_fill

    #d.rectangle((0, text_y, im.width, text_y+text_h+15), fill=(text_r,text_g,text_b,128))
    #d.text((text_x, text_y),
    #       title,
    #       font=fnt,
    #       fill=(bg_r, bg_g, bg_b, 128),
    #       spacing=1,
    #       align=align)
    d.rectangle((0, text_y, im.width, text_y+text_h+15), fill=(0,0,0,255))
    d.text((text_x, text_y),
           title,
           font=fnt,
           fill=(255,255,255,255),
           spacing=1,
           align=align)

    out = Image.alpha_composite(im, txt)

    return out

def maybe_inverse(card: TarotCard, im: Image) -> Image:
    if not card.inverted:
        return im

    if random() < .7:
        return im.rotate(180)
    else:
        return ImageOps.mirror(im)

def sort_pixels(max_interval:int, im: Image) -> Image:
    # TODO random angle, or at least diagonal chance
    pixels = list(im.getdata())
    outpixels = sort_image(pixels, im.size, max_interval=max_interval, randomize=True)
    output = Image.new(im.mode, im.size)
    output.putdata(outpixels)
    return output

def blur(im: Image) -> Image:
    return im.filter(ImageFilter.BLUR)

def find_edges(im: Image) -> Image:
    return im.filter(ImageFilter.FIND_EDGES)

def contour(im: Image) -> Image:
    return im.filter(ImageFilter.CONTOUR)

def emboss(im: Image) -> Image:
    return im.filter(ImageFilter.EMBOSS)

def detail(im: Image) -> Image:
    return im.filter(ImageFilter.DETAIL)

def invert(im: Image) -> Image:
    return ImageOps.invert(im)

def edge_enhance(im: Image) -> Image:
    return im.filter(ImageFilter.EDGE_ENHANCE)

def edge_enhance_more(im: Image) -> Image:
    return im.filter(ImageFilter.EDGE_ENHANCE_MORE)

def grayscale(im: Image) -> Image:
    return ImageOps.grayscale(im)

def posterize(bits: int, im: Image) -> Image:
    return ImageOps.posterize(im, bits)

def brighten(im: Image) -> Image:
    enbrightener = ImageEnhance.Brightness(im)
    return enbrightener.enhance(1.4)

PRE_TITLE_DISTORT = [blur, partial(sort_pixels, 15), find_edges, contour, emboss, detail, invert]
POST_TITLE_DISTORT = [blur, edge_enhance, detail, invert, partial(sort_pixels, 5)]

def process_sentiment(card: TarotCard, im: Image) -> Image:
    """To be called prior to title placement."""
    print('PROCESSING A {} SENTIMENT'.format(card.sentiment))
    if card.sentiment == NEGATIVE:
        # first, replace a color band with black
        bands = im.split()
        bye_band = choice([0,1,2])
        black_band = bands[bye_band].point(lambda _: 0)
        bands[bye_band].paste(black_band)
        im = Image.merge(im.mode, bands)

        return posterize(4, grayscale(im))
    elif card.sentiment == POSITIVE:
        return brighten(im)
    else:
        return posterize(7, im)

def generate(flickr: FlickrAPI) -> Image:
    card = draw_tarot_card()
    if card.inverted:
        print('drew inverted', card)
    else:
        print('drew', card)

    search_term = card.search_term

    print('searching for', search_term)

    photo = get_photo(flickr, card.search_term)

    print('going to fetch', photo.url)

    original = Image.open(photo.data)

    print('processing image')

    # 1 Pick random section of image to cut card from
    im = random_crop(original)

    # 2 Pick zoom level (possibly 100%)
    im = maybe_zoom(im)

    # 3 modify color balance (based on card)
    im = color_balance(card, im)

    # TODO distort before or after sort_pixels?
    im = process_sentiment(card, im)

    #print('SORTING')
    #im = sort_pixels(im)

    pre_distort = choice(PRE_TITLE_DISTORT)
    print('PRE-TITLE DISTORTING', im, pre_distort)
    im = im.convert('RGB')
    im = pre_distort(im)

    print('PLACING TITLE')
    im = place_title(card, im)

    im = maybe_inverse(card, im)

    first_post_distort = choice(POST_TITLE_DISTORT)
    second_post_distort = choice(POST_TITLE_DISTORT)
    while second_post_distort == first_post_distort:
        second_post_distort = choice(POST_TITLE_DISTORT)
    print('POST-TITLE DISTORTING', im, first_post_distort, second_post_distort)
    im = im.convert('RGB')
    im = first_post_distort(im)
    im = im.convert('RGB')
    im = second_post_distort(im)

    return im

def main():
    flickr = FlickrAPI(sec.FLICKR_KEY, sec.FLICKR_SECRET, format='parsed-json')
    twitter_auth = tweepy.OAuthHandler(sec.TWITTER_KEY, sec.TWITTER_SECRET)
    twitter_auth.set_access_token(sec.TWITTER_ACCESS_TOKEN, sec.TWITTER_ACCESS_SECRET)
    twitter = tweepy.API(twitter_auth)

    if len(sys.argv) > 1 and sys.argv[1] == 'authenticate':
        print('authenticating...')
        flickr.authenticate_via_browser(perms='read')


    im = generate(flickr)

    if not DEBUG:
        print('updating twitter...')
        buffer = BytesIO()
        im.save(buffer, format='JPEG')
        twitter.update_with_media('tarot.jpg', file=buffer)
    else:
        print('saving to /tmp/tarot.jpg')
        im.save('/tmp/tarot.jpg')

    sys.exit(0)
