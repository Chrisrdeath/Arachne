#These are the most important connection codes for scraping
CONNECT_CODES = {
    200: "Connected",
    403: "Forbidden",
    404: "Not Found",
    429: "Too Many Requests",
    503: "Service Unavailable",
    522: "Connection Timed Out",
}

#next page possible text
NAV_TAGS = [
    'div',
    'nav',
    'ol',
    'section',
    'ul',
]

NAV_KEYWORDS = [
    'load more',
    'load page',
    'loadmore',
    'nav-button',
    'nav',
    'next page',
    'nextpage',
    'pagination',
    'scroll',
    'pages'
]

THMB_KEYWORDS = [
    'mini',
    'normal',
    'preview',
    'small',
    'thm',
    'thumb',
    'tiny',
]

MAIN_TAGS = [
    'div',
    'article',
    'section',
    'main'
]

MAIN_KEYWORDS = [
    'con', 
    'post',
    'full',
    'main',
]

IGNORE_KEYWORDS = [
    'loader',
    'button',
    'btn',
    'logo',
    'reply',
    'pay',
    'prev',
    'next'
]

ANGULAR_CHECK = [
    "app-root"
]

CONTENT_TYPE = [
    'post',
    'album'
]

VID_RESOLUTIONS = [
    '480',
    '720',
    '1080'
]

FIRST_TEXT = [
    '&lt;&lt;',
    '<<'
]

PREV_TEXT = [
    '&lt;',
    '<',
    '«',
    'prev'
]

NEXT_TEXT = [
    '&gt',
    '>',
    '»',
    'next'
]

LAST_TEXT = [
    '&gt;&gt;',
    '>>'
]