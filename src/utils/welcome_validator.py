"""Conservative rule-based classification; uncertain text is retained for review."""
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    APPROVE = 'approve'
    REJECT = 'reject'
    KEEP = 'keep'  # uncertain: leave the message alone


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    reason: str


TEMPLATE = 'Name/Nickname:\nGraduation Year:\nAP Classes Taking/Taken:\nFun Facts/Random Deets:'
LABEL = re.compile(r'^(?:[-•> ]*)\**\s*(?:my\s+)?(name(?:\s*/\s*nickname)?|nickname|grad(?:uation)?\s*(?:year|class)|class\s+of|year|grade|ap(?:s|\s+classes(?:\s+taking\s*/\s*taken|\s+taking|\s+taken)?|\s+courses)?|fun\s+facts?(?:\s*/\s*random\s+deets)?|random\s+deets|interests?|hobbies|about\s+me)[\s*]*:[\s*]*(.*?)\s*$', re.I)
GREETING = re.compile(r'(?:hi+|hey+|hello+|hiya|yo+|sup|wassup|what[’\']?s up|good (?:morning|evening|afternoon))(?:\s+(?:everyone|everybody|all|guys|folks|there|yall|y[’\']all))?[\s!?.,~]*', re.I)
CHAT = re.compile(r'(?:lol+|lmao+|lmfao+|bruh+|bro+|lol bro what|bro what|what|ok(?:ay)?|thanks|thank you|nice|real|fr|wyd|wsg|gm|gn|welcome|welcome to (?:the server|ap students))[\s!?.,~]*', re.I)
# Only match entire reaction/chat messages, never substrings in introductions.
# Normalize elongated ASCII letters for comparison, not for introduction fields.
REACTION_WORDS = frozenset({
    'lol', 'lmao', 'lmfao', 'rofl', 'bruh', 'bro', 'no', 'yes', 'nah',
    'ok', 'okay', 'haha', 'hehe', 'hahaha', 'hahahaha', 'hahahahaha',
    'omg', 'wtf', 'fr', 'rip', 'wow', 'nice', 'real', 'wyd', 'wsg',
    'gm', 'gn', 'hi', 'hey', 'hello', 'yo', 'sup', 'thanks',
})
CHAT_PHRASES = frozenset({
    'bro what are you talking about', 'what are you talking about',
    'what do you mean', 'bro what do you mean', 'what is going on',
    'bro what is going on', 'how are you guys', 'how are you all',
    'how are you', 'thank you so much', 'lol bro what', 'bro what',
})
LAUGHTER = re.compile(r'(?:ha){2,}|(?:he){2,}|(?:ja){3,}', re.I)
KEYBOARD_SPAM = re.compile(r'(?:asdf|qwer|zxcv|hjkl|jkl;){2,}', re.I)


def _chat_key(text):
    text = re.sub(r'[!?.,~]+', ' ', text.casefold())
    return ' '.join(re.sub(r'([a-z])\1+', r'\1', text).split())


_REACTION_KEYS = frozenset(_chat_key(word) for word in REACTION_WORDS)
_CHAT_KEYS = frozenset(_chat_key(phrase) for phrase in CHAT_PHRASES)


def obvious_chat(text):
    key = _chat_key(text)
    if key in _CHAT_KEYS:
        return True
    words = key.split()
    return bool(words) and all(
        word in _REACTION_KEYS or LAUGHTER.fullmatch(word)
        for word in words
    )


QUESTION = re.compile(r'^(?:anyone|anybody|does anyone|can anyone|is anyone|who here|who is|who[’\']s|where (?:is|are|can)|how (?:do|can|does)|what (?:is|are|do)|when (?:is|are)|can (?:you|someone))\b', re.I)
AD = re.compile(r'^(?:@everyone\s+|@here\s+)?(?:join|check out)\s+(?:my|our|this)\s+(?:discord\s+)?server\b', re.I)
PLACEHOLDER = re.compile(r'^(?:[-–—_?]+|\.{2,}|\[.*\]|<[^>]+>)$')


# Targeted folding for detection only; preserve accents and non-Latin scripts.
INVISIBLE = dict.fromkeys(map(ord, '\u200b\u200c\u200d\u2060\ufeff\u00ad\u2800\u3164\u115f\u1160\ufe0e\ufe0f'))
INVITE = re.compile(r"(?<![\w.])(?:https?://)?(?:www\.)?(?:discord\.gg/|discord(?:app)?\.com/invite/|dsc\.gg/|discord\.me/|invite\.gg/|discord\.gift/|discord\.new/)[a-z0-9_-]+", re.I)
SCAM = re.compile(r'\b(?:free\s+(?:nitro|robux)|buy\s+(?:cheap\s+)?followers|dm\s+me\s+for\s+(?:promo|nitro|money)|claim\s+(?:your\s+)?(?:prize|reward))\b', re.I)
LINK = re.compile(r'https?://|www\.', re.I)
CUSTOM_EMOJI = re.compile(r'<a?:[a-zA-Z0-9_]+:\d+>')
MENTION = re.compile(r'<@!?\d+>|<@&\d+>|@everyone|@here', re.I)
KEYBOARD_ROW = re.compile('|'.join(re.escape(row[i:i+6]) for row in ('qwertyuiop','asdfghjkl','zxcvbnm','poiuytrewq','lkjhgfdsa','mnbvcxz') for i in range(len(row)-5)), re.I)


def fold(text):
    return unicodedata.normalize('NFKC', text or '').translate(INVISIBLE).strip()


def undecorate(text):
    text = CUSTOM_EMOJI.sub(' ', text)
    # Do not strip letters, accents, or punctuation internal to words.
    return ''.join(' ' if unicodedata.category(c) in ('So', 'Sk') else c for c in text).strip('*_`~ !?.,:;|\t\n\r')


def low_content(text):
    plain = undecorate(text)
    if not plain or not any(c.isalnum() for c in plain):
        return 'reaction_or_symbols'
    if not MENTION.sub('', plain).strip(' !?.,'):
        return 'mention_only'
    # Accent/combining mark folding only for matching known English chat tokens.
    chat = ''.join(c for c in unicodedata.normalize('NFD', plain) if unicodedata.category(c) not in ('Mn','Me'))
    if GREETING.fullmatch(chat) or CHAT.fullmatch(chat) or obvious_chat(chat):
        return 'greeting_or_chat'
    token = plain.casefold().rstrip('!?.,~ ')
    if KEYBOARD_SPAM.fullmatch(token) or (re.fullmatch(r'[a-z]+', token) and KEYBOARD_ROW.search(token)):
        return 'keyboard_pattern'
    if re.fullmatch(r'(.)\1{7,}', token, re.S):
        return 'repeated_character'
    if re.fullmatch(r'[a-z]+', token):
        run = re.search(r'([a-z])\1{7,}', token)
        if run and len(run.group()) * 2 >= len(token):
            return 'elongated_word_spam'
    return None


# Positive evidence is deliberately narrow for standalone English fragments.
# No name dictionary, identity inference, network calls, or model.
AP_SUBJECT = (r'(?:calculus(?:\s+(?:ab|bc))?|calc(?:\s+(?:ab|bc))?|bio(?:logy)?|chem(?:istry)?|'
              r'physics(?:\s+(?:[12]|c(?:\s*:?\s*(?:mechanics|e\s*&\s*m|electricity and magnetism))?))?|'
              r'precalculus|precalc|statistics|stats|computer science(?:\s+(?:a|principles))?|'
              r'cs[ap]|csp|csa|english(?:\s+(?:language|literature)(?:\s+and composition)?)?|'
              r'lang|lit|world(?:\s+history)?|(?:u\.?s\.?|us|european|euro|art)\s+history|'
              r'ush|wh|government(?:\s+and politics)?|gov|(?:us|comparative)\s+gov(?:ernment)?|'
              r'psych(?:ology)?|environmental science|human geography|hug|macro(?:economics)?|'
              r'micro(?:economics)?|economics|seminar|research|capstone|music theory|'
              r'art(?:\s+and design)?|drawing|2d art|3d art|(?:spanish|french|german|italian|chinese|japanese)'
              r'(?:\s+language(?:\s+and culture)?|\s+literature)?|latin|african american studies|'
              r'business(?:\s+with personal finance)?|cybersecurity)')
AP_COURSE = r'(?:ap\s*' + AP_SUBJECT + r'|apush|apwh|apes|apcsp|apcsa|apah|aphug|apgov|aplang|aplit)'
COURSES = re.compile(r'^' + AP_COURSE + r'(?:(?:\s*[,/&+]\s*|\s+(?:and|&|plus)\s+)(?:' + AP_COURSE + r'|' + AP_SUBJECT + r'))*[.!]?$' , re.I)
CLASS_YEAR = re.compile(r"(?:class\s+of\s+['’]?(?:20\d{2}|\d{2})|(?:grad(?:uating|uate|uation)?(?:\s+year)?\s*[: ]\s*)20\d{2}|20\d{2}|c/o\s*['’]?(?:20\d{2}|\d{2}))",re.I)
STATUS = re.compile(r'(?:freshman|sophomore|junior|senior|(?:high school|college|university|middle school) student|(?:grade\s+\d{1,2}|\d{1,2}(?:st|nd|rd|th)\s+grad(?:e|er)))', re.I)
INTEREST = (r'(?:math(?:ematics|s)?|physics|chemistry|biology|science|history|english|literature|'
            r'computer science|cs|coding|programming|robotics|engineering|chess|gaming|video games|'
            r'music|art|drawing|painting|reading|writing|photography|sports|soccer|football|basketball|'
            r'volleyball|tennis|swimming|running|hiking|baking|cooking|anime|manga|dance|dancing|'
            r'guitar|piano|violin|singing|theater|theatre|debate|astronomy|languages|travel|'
            r'crocheting|knitting|gardening|film|movies|fashion|design|poetry|track|cross country)')
INTERESTS = re.compile(r'^' + INTEREST + r'(?:(?:\s*[,/&+]\s*|\s+(?:and|&|plus)\s+)' + INTEREST + r')*[.!]?$', re.I)
SELF_DESCRIPTION = re.compile(r'^(?:(?:future|aspiring)\s+(?:(?:electrical|mechanical|civil|software|computer|aerospace|chemical)\s+)?(?:engineer|doctor|scientist|teacher|programmer|developer|artist|lawyer|researcher|nurse|architect|mathematician|physicist)|professional procrastinator|bookworm|(?:math|science|history|coding|computer|physics|chemistry|biology|music|book|anime|chess)\s+(?:nerd|geek|enthusiast|lover))$', re.I)
# First-person patterns require a substantive object; avoid accepting bare "I like".
PERSONAL = re.compile(r"^(?:i\s+(?:really\s+|also\s+)?(?:love|like|enjoy|prefer|play|study|take|took|have taken|am taking|want to|plan to|hope to|collect|read|write|listen to|watch|use|have|spend my time|survived|somehow survived)|i(?:'m|m| am)\s+(?:taking|studying|interested in|into|from|learning|majoring in|here to|passionate about|obsessed with|planning on)|my\s+(?:favorite|favourite)\s+(?:class|subject|hobby|sport|game|book|food|music|color|colour)(?:s)?\s+(?:is|are)|my\s+(?:hobb(?:y|ies)|interests?)\s+(?:is|are|include)|my\s+(?:youtube|twitch|art)\s+channel\s+is)\s+(.+)$", re.I)
SELF_NAME = re.compile(r"^(?:(?:my (?:name|nickname)(?: is|'s)|call me|i go by)\s+(.+)|(.{1,80})\s+is my (?:name|nickname))$", re.I)
IM = re.compile(r"^i(?:'m|m| am)\s+(.+)$", re.I)
# Do not pretend every arbitrary first-person status is a name.
NON_NAME = frozenset({'here','there','fine','good','great','okay','ok','bored','tired','hungry','sad','happy','sorry','done','back','lost','confused','mad','angry','dead','alive','online','offline','not','yes','no','lol','lmao','bruh','trolling','troll','testing','test','cool','new','someone','nobody','nothing'})
PRIVACY = re.compile(r"(?:prefer not to (?:say|share|disclose)|(?:rather|would rather) not (?:say|share)|private|anonymous|not sharing|no comment)", re.I)
FOREIGN_INTRO = re.compile(r"^(?:je m'appelle|je suis|j'aime|me llamo|soy|me gusta(?:n)?|mi nombre es|eu sou|sou|me chamo|gosto de|ich heiße|ich bin|ich mag|mi chiamo|sono|mi piace|ik ben|ik heet|ik hou van)\s+\S", re.I)
STRIP_GREETING = re.compile(r"^(?:(?:hi+|hey+|hello+|hiya|yo+|sup|lol+|lmao+|bro+|bonjour|hola|salut|oi|hallo|ciao)(?:\s+(?:everyone|all|guys|folks|there|yall|y'all))?[\s,!:.~-]+)+", re.I)


def _evidence_text(text):
    # Retain sentence punctuation (especially question marks) for scope checks.
    text = CUSTOM_EMOJI.sub(' ', text)
    text = ''.join(' ' if unicodedata.category(c) in ('So', 'Sk') else c for c in text)
    return text.replace('’', "'").replace('‘', "'").replace('ʼ', "'").replace('I`m', "I'm").replace('i`m', "i'm").replace('**', '').replace('__', '').strip(' #|*_`~\t\r\n¡¿')


NO_DETAIL = frozenset({'not introduction','not an introduction','random text','slurs lol','this message','this','that','you','you guys','your mom','the server','this server','it','stuff','things','whatever','nothing','anything','everything','idk'})
REVERSE_INTEREST = re.compile(r"^(.{1,120})\s+(?:is|are) my fav(?:orite|ourite)?\s+(?:class|subject|hobby|sport|game|book|food|color|colour|activity|interest)s?$",re.I)
COURSE_PHRASE = re.compile(r"^(?:(?:currently|now|planning on|thinking of)\s+)?(?:taking|took|studying|planning to take|going to take|have taken)\s+(.+)$",re.I)
COURSE_TOKEN = re.compile(r'(?<!\w)(?:' + AP_COURSE + r'|' + AP_SUBJECT + r')(?!\w)', re.I)
QUESTION_START = re.compile(r'^(?:anyone|anybody|does|do|did|is|are|was|were|can|could|would|will|who|what|where|when|why|how|should|have|has)\b',re.I)


def _substantive(value):
    value = value.strip(' *_`~!?,.;:')
    return bool(value and any(c.isalnum() for c in value)
                and not PLACEHOLDER.fullmatch(value)
                and value.casefold() not in NO_DETAIL | {'n/a','na','none','nothing','idk','unknown','tbd'}
                and not SCAM.fullmatch(value)
                and not re.fullmatch(r'(?:free (?:nitro|robux)(?: giveaway)?|dm me for promo)', value, re.I)
                and low_content(value) is None)


def _field_evidence(label, value):
    label = label.casefold()
    if PRIVACY.fullmatch(value):
        return True
    if not value or PLACEHOLDER.fullmatch(value) or value.casefold() in NO_DETAIL | {'n/a','na','-','?','tbd','unknown','idk'}:
        return False
    if label.startswith('ap'):
        return bool(re.fullmatch(r'(?:none(?: yet)?|no aps?(?: yet)?|not taking any(?: aps?)?|not sure|undecided|\d{1,2}(?: aps?)?)', value, re.I) or COURSE_TOKEN.search(value))
    # An explicitly labeled nickname can be unconventional or stretched.
    # Known keyboard spam, exact reaction words, URLs and symbols are not details.
    if label.startswith(('name','nickname')):
        if LINK.search(value) or INVITE.search(value) or SCAM.search(value) or value.casefold() in REACTION_WORDS:
            return False
        return low_content(value) not in {'keyboard_pattern','repeated_character','reaction_or_symbols','mention_only'} and any(c.isalnum() for c in value)
    if label.startswith(('grad','class','year','grade')):
        return bool(CLASS_YEAR.fullmatch(value) or STATUS.fullmatch(value) or re.fullmatch(r"['’]?\d{2}|\d{1,2}(?:st|nd|rd|th)?|(?:fall|spring|summer)\s+20\d{2}|(?:not sure|undecided)",value,re.I))
    if LINK.fullmatch(value) or re.fullmatch(r'(?:https?://|www\.)\S+', value, re.I):
        return False
    # A labeled interest can legitimately be any activity, not just our vocabulary.
    # A small set of unambiguous activity pictographs counts only in a labeled field.
    if label.startswith(('hobb','interest','fun','random')) and any(c in '🏀⚽🏈🎮🎸🎨📚🎵🎹🎻🏐🏊🏃♟' for c in value):
        return True
    return _substantive(value)


def _nonlatin(text):
    letters = [c for c in text if c.isalpha()]
    # A single confusable non-Latin letter must not turn English junk into an exemption.
    nonlatin = sum(not unicodedata.name(c, '').startswith('LATIN ') for c in letters)
    return nonlatin >= 2 and nonlatin * 2 >= len(letters)


# Additional evidence for conversational introductions. Keep these anchored to
# a self-description or a conventional standalone introduction fragment.
ACADEMIC_LEVEL = (r'(?:(?:hs|high school|college|university|middle school)\s+)?'
                  r'(?:freshm[ae]n|sophomore|junior|senior|student|jnr(?:\s+(?:yr|year))?|'
                  r'(?:grade|year|y)\s*(?:[1-9]|1[0-3])(?:\s+student)?|'
                  r'(?:[1-9]|1[0-3])(?:st|nd|rd|th)(?:\s+(?:grade|grader|year))?)')
ACADEMIC_INTRO = re.compile(r'^(?:(?:i(?:\s+am|\s*\x27m|m)|m)\s+)?'
                           r'(?:(?:currently|also)\s+)?(?:a[n]?\s+)?(?:in\s+)?'
                           + ACADEMIC_LEVEL + r'(?=$|[\s,.!])', re.I)
OCCUPATION = re.compile(r'^(?:(?:i(?:\s+am|\s*\x27m|m)|m)\s+)?(?:a[n]?\s+)?'
                        r'(?:(?:senior|junior|full[- ]stack|front[- ]?end|back[- ]?end|aspiring|certified|software|'
                        r'civil|mechanical|electrical|academic|forex|retail|research|data|'
                        r'computer|part[- ]time|high school|AP)\s+){0,4}'
                        r'(?:engineer|developer|programmer|teacher|tutor|trader|consultant|'
                        r'researcher|scientist|analyst|designer|artist|writer|nurse|doctor|'
                        r'accountant|architect|technician|librarian|musician|student|professor)\b', re.I)
SELF_BACKGROUND = re.compile(r"^(?:i(?:'m|m| am)|m)\s+(?:a[n]?\s+)?(?:"
    r"(?:big\s+|huge\s+)?fan\s+of|(?:certificate|certified|qualified)\s+in|"
    r"(?:working|employed)\s+(?:as|in)|(?:based|living|studying)\s+in|"
    r"(?:[\w'-]{2,30}\s+){0,2}(?:student|learner)\s+from)\s+(.+)$", re.I)
SELF_LOCATION_NAME = re.compile(r"^i(?:'m|m| am)\s+([^\W\d_][\w'-]{0,39}(?:\s+[^\W\d_][\w'-]{0,39}){0,2})\s+from\s+(.+)$", re.I)
SELF_GRADE_LOCATION = re.compile(r"^i(?:'m|m| am)\s+(?:a[n]?\s+)?[\w'-]{2,30}\s+in\s+" + ACADEMIC_LEVEL + r'(?=$|[\s,.!])', re.I)
NO_AP_TYPO = re.compile(r"^(?:i(?:'m|m| am)|m)\s+(?:taking|takeng|takin|studying)\s+(?:no|zero)\s+aps?\b", re.I)
THIRD_PERSON_INTRO = re.compile(r'^(?:<@!?\d+>|@[\w.-]+(?:\s+[\w.-]+){0,2})\s+is\s+(?:a[n]?\s+)?' + ACADEMIC_LEVEL + r'(?=$|[\s,.!])', re.I)
EXTRA_GREETING = re.compile(r"^(?:(?:h+i+(?:e+l+l+o+)?|h+e+l+o+|h+e+l+l+o+|h+e+y+|howdy|hy)(?:\s+(?:everyone|everybody|all|guys|gang|friends|folks|there|yall|y'all))?[\s,!:.~-]+)+", re.I)


# These cues are descriptive, not identity verification. Unmatched cases remain safe.
NAME_CUE = re.compile(r"^(?:(?:you can call me|everyone calls me|i(?:'m|m| am) known as|this is|it'?s)\s+([\w'-]{1,40}(?: [\w'-]{1,40}){0,2})|([\w'-]{1,40}) here)$", re.I)
NAME_DECORATION = re.compile(r"(?:\s*(?:[:;=][-^]?[)D3]|<3|:\w{1,30}:)|\s+(?:lol|btw|haha)|\s*\([^()]{1,30}\))+$", re.I)
EXTRA_SELF = re.compile(r"^(?:i(?:'m|m| am)?\s+(?:do(?:ing)?|self[- ]studying|teach|tutor|ski|sing|swim|run|code|wanna be|joined for|graduate in|(?:in|a|an)\s+(?:band|robotics|gamer|parent|homeschooler|engineering student))\b|(?:currently in|in|doing|taking|preparing for|learning|into|hoping to study|want to be|my goal is|here for|here to study|looking for study buddies)\b|(?:rising|just a)\s+(?:junior|senior|sophomore|freshman)\b)", re.I)

def conversational_evidence(chunk):
    # A course/interest alone inside a question is not evidence. Only apply
    # these patterns to the beginning of a non-question clause.
    if not chunk or QUESTION_START.match(chunk) or chunk.endswith('?'):
        return False
    name = NAME_CUE.fullmatch(NAME_DECORATION.sub('', chunk).strip())
    if name and all(part.casefold() not in NON_NAME | {'a','an','the','message','introduction'} for part in (name.group(1) or name.group(2)).split()):
        return True
    if EXTRA_SELF.match(chunk) and not re.match(r'^(?:i do not|i do nothing|i am in trouble|i do not care)\b', chunk, re.I):
        return True
    # Bare fragments need a plausible continuation rather than merely a
    # keyword at the beginning of unrelated prose (e.g. "student loan").
    for pattern in (ACADEMIC_INTRO, OCCUPATION):
        match = pattern.match(chunk)
        if match:
            tail = chunk[match.end():].strip(' ,.!')
            if not tail or re.match(r"(?:taking|took|studying|self[- ]studying|in|at|from|with|working|majoring|graduating|planning|currently|this year|next year|and|of|who)\b", tail, re.I) or tail.startswith('('):
                return True
    if SELF_GRADE_LOCATION.match(chunk) or NO_AP_TYPO.match(chunk) or THIRD_PERSON_INTRO.match(chunk):
        return True
    match = SELF_BACKGROUND.fullmatch(chunk)
    if match and _substantive(match.group(1)):
        return True
    match = SELF_LOCATION_NAME.fullmatch(chunk)
    return bool(match and match.group(1).casefold() not in NON_NAME and _substantive(match.group(1)) and _substantive(match.group(2)))


def _positive_evidence(text):
    # Split sentences before fragments. A question must not pass merely because
    # its last comma-separated fragment is a known hobby or AP course.
    for line in text.splitlines():
        line = _evidence_text(line).lstrip('-•> ').strip()
        if not line:
            continue
        for sentence in re.split(r'(?<=[.!?])\s+', line):
            sentence = sentence.strip(' !.,¡¿')
            if not sentence or QUESTION_START.match(sentence):
                continue
            if sentence.endswith('?'):
                # A self-introduction before a follow-up question is still valid.
                lead, separator, _ = sentence.partition(',')
                if not separator or not (PERSONAL.fullmatch(lead.strip()) or SELF_NAME.fullmatch(lead.strip()) or IM.fullmatch(lead.strip())):
                    continue
                sentence = lead.strip()
            clean = STRIP_GREETING.sub('', EXTRA_GREETING.sub('', sentence)).strip(' !.,¡¿') or sentence
            if not clean:
                continue
            if QUESTION_START.match(clean):
                reverse = REVERSE_INTEREST.fullmatch(sentence)
                if reverse and (_substantive(reverse.group(1)) or reverse.group(1).casefold() == 'lol'):
                    return True
                continue
            if FOREIGN_INTRO.match(sentence) or FOREIGN_INTRO.match(clean):
                return True
            chunks = [sentence, clean] + re.split(r"\s*[;,]\s*|\s+and\s+(?=i(?:\b|['’]m\b|m\b)|my\s)", clean, flags=re.I)
            for chunk in dict.fromkeys(chunks):
                chunk = chunk.strip(' !.,')
                if not chunk or chunk.endswith('?') or QUESTION_START.match(chunk):
                    continue
                if conversational_evidence(chunk):
                    return True
                if (re.fullmatch(r"(?:no aps?(?: yet)?|i(?:'m|m| am) not taking any aps?(?: yet)?|i haven’t taken any aps?(?: yet)?|i haven't taken any aps?(?: yet)?)",chunk,re.I) or CLASS_YEAR.fullmatch(chunk) or STATUS.fullmatch(chunk) or COURSES.fullmatch(chunk)
                        or INTERESTS.fullmatch(chunk) or SELF_DESCRIPTION.fullmatch(chunk)):
                    return True
                if re.fullmatch(r'(?:' + STATUS.pattern + r')\s+(?:taking\s+)?' + AP_COURSE + r'(?:\s+.*)?',chunk,re.I):
                    return True
                if re.fullmatch(r'(?:' + SELF_DESCRIPTION.pattern.removeprefix('^').removesuffix('$') + r')\s*,?\s*class of\s+[\'’]?(?:20\d{2}|\d{2})',chunk,re.I):
                    return True
                m = COURSE_PHRASE.fullmatch(chunk)
                if m and COURSE_TOKEN.search(m.group(1)):
                    return True
                m = REVERSE_INTEREST.fullmatch(chunk)
                if m and (_substantive(m.group(1)) or m.group(1).casefold() == 'lol'):
                    return True
                m = SELF_NAME.fullmatch(chunk)
                if m:
                    value = m.group(1) or m.group(2)
                    if (any(c.isalnum() for c in value) and value.casefold() not in NO_DETAIL
                            and not LINK.search(value) and not SCAM.search(value)
                            and low_content(value) not in {'keyboard_pattern','repeated_character','reaction_or_symbols','mention_only'}):
                        return True
                m = PERSONAL.fullmatch(chunk)
                if m and _substantive(m.group(1)):
                    return True
                m = IM.fullmatch(chunk)
                if m:
                    value = NAME_DECORATION.sub('', m.group(1)).strip(' !.,')
                    status = re.sub(r'^(?:a|an)\s+', '', value, flags=re.I)
                    if (STATUS.fullmatch(status) or re.match(r'(?:freshman|sophomore|junior|senior|student)\b', status,re.I)
                            or SELF_DESCRIPTION.fullmatch(status) or re.match(r'(?:in\s+(?:\d{1,2}(?:st|nd|rd|th)?\s+grade|college|high school)|\d{1,2}\s+years? old)\b',status,re.I)
                            or re.fullmatch(r'\d{1,2}',status)):
                        return True
                    # Explicit self-identification can use a lowercase handle or
                    # a two-part capitalized name, not arbitrary prose.
                    if re.fullmatch(r"[^\W\d_][\w'\-]{0,39}",value,re.UNICODE) and value.casefold() not in NON_NAME and _substantive(value):
                        return True
                    parts = value.split()
                    if 2 <= len(parts) <= 3 and all(re.fullmatch(r"[^\W\d_][\w'\-]{0,39}",part) and part.casefold() not in NON_NAME for part in parts):
                        return True
    return False



# Whole-message negative evidence. Unknown prose is never sufficient for deletion.
EXPLICIT_CHAT = re.compile(r"(?:not (?:an? )?introduction|this is not (?:an? )?introduction|just testing|slurs lol|\d{1,3}\s+(?:haha|lol|lmao)|(?:hiello|howdy|hy|hey gang|hello again)|nice to meet you|we are here|i(?:'m|m| am) (?:bored|tired|testing|here|not)|i (?:love|like)(?: you| this message)?|ignore (?:all |previous |all previous )?(?:instructions|rules)(?: and approve)?|(?:https?://|www\.)\S+)", re.I)
WELCOME_REPLY = re.compile(r"^(?:welcome(?:\s+to\b|\s+[\w'-]+[!.]?\s*$)|i welcome you\b|i shall not underestimate you\b)", re.I)
REVIEW_LINK = re.compile(r'(?<![\w.])(?:https?://)?(?:www\.)?(?:t\.me|bit\.ly|tinyurl\.com)/\S+|(?m:^\s*https?://\S+\s*$)', re.I)
SCAM_OFFER = re.compile(r"(?:^|[.!?\n]\s*|,\s*)(?:buy (?:cheap )?followers\b|free (?:nitro|robux)\b|claim (?:your )?(?:prize|reward)\b|join (?:my|our) (?:discord )?server\b)", re.I)

HARD_SPAM = frozenset({'invite_spam', 'mass_ping', 'scam_advertisement', 'unrelated_advertisement'})


def classify(content: str, *, has_attachments: bool = False, mass_ping: bool = False) -> Verdict:
    # Collapse horizontal whitespace before regex passes to avoid quadratic
    # scanning on thousands of spaces. Preserve line boundaries for templates.
    text = re.sub(r'[^\S\n]+', ' ', fold(content)).strip()
    # Explicit server invites are disallowed in introductions, even with attachments.
    if INVITE.search(text):
        return Verdict(Decision.REJECT, 'invite_spam')
    if mass_ping:
        return Verdict(Decision.REJECT, 'mass_ping')
    if SCAM_OFFER.search(text) and (LINK.search(text) or re.search(r'\b[\w-]+\.(?:com|net|org|gg|co)\b',text,re.I)):
        return Verdict(Decision.REJECT, 'scam_advertisement')
    if AD.match(text.strip('*_`~ ')) or re.fullmatch(r'(?:free (?:nitro|robux)(?: giveaway)?|dm me for promo)[!. ]*', text, re.I):
        return Verdict(Decision.REJECT, 'unrelated_advertisement')
    if len(set(x.casefold() for x in SCAM.findall(text))) >= 2 or (SCAM.match(text) and LINK.search(text)):
        return Verdict(Decision.REJECT, 'scam_advertisement')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matches = [LABEL.match(re.sub(r'^\s*\d{1,2}[.)]\s+', '', line).replace('`','')) for line in lines]
    fields = [(m.group(1), m.group(2).strip('* _`')) for m in matches if m]
    if any((SCAM.match(v) and LINK.search(v)) or re.fullmatch(r'(?:free (?:nitro|robux)(?: giveaway)?|dm me for promo)', v, re.I) for _, v in fields):
        return Verdict(Decision.REJECT, 'scam_advertisement')
    if (REVIEW_LINK.search(text) and len(lines) > 1) or re.search(r'(?<![\w.])(?:t\.me|bit\.ly|tinyurl\.com)/\S+', text, re.I):
        return Verdict(Decision.KEEP, 'no_introduction_evidence')
    if any(_field_evidence(label, value) for label, value in fields):
        return Verdict(Decision.APPROVE, 'filled_template')
    if has_attachments:
        # Image-only introductions and uncertain captions remain protected.
        return Verdict(Decision.KEEP, 'attachment_or_uncertain')
    if not text:
        return Verdict(Decision.REJECT, 'empty_message')
    if fields and all(matches):
        if not any(v for _, v in fields):
            return Verdict(Decision.REJECT, 'empty_template')
        # A malformed year/course field may still describe a real student.
        # Only remove templates where every field is visibly empty or junk.
        def junk(value):
            return (not value or PLACEHOLDER.fullmatch(value) or low_content(value) is not None
                    or value.casefold() in NO_DETAIL | {'n/a','na','tbd','unknown','random','none'}
                    or re.fullmatch(r'(?:https?://|www\.)\S+', value, re.I))
        if all(junk(v) for _, v in fields):
            return Verdict(Decision.REJECT, 'junk_template')
        return Verdict(Decision.KEEP, 'no_introduction_evidence')
    reason = low_content(text)
    if reason:
        return Verdict(Decision.REJECT, reason)
    if PRIVACY.fullmatch(text) or re.fullmatch(r'prefer not to introduce myself',text,re.I):
        return Verdict(Decision.KEEP, 'privacy_opt_out')
    if _positive_evidence(text):
        return Verdict(Decision.APPROVE, 'personal_introduction')
    if _nonlatin(text):
        return Verdict(Decision.KEEP, 'unfamiliar_language')
    key = _evidence_text(text).strip(' !.,')
    if EXPLICIT_CHAT.fullmatch(key):
        return Verdict(Decision.REJECT, 'explicit_chat')
    lead = STRIP_GREETING.sub('', EXTRA_GREETING.sub('', key)).strip() or key
    if WELCOME_REPLY.match(lead) or WELCOME_REPLY.match(key):
        return Verdict(Decision.REJECT, 'welcoming_reply')
    if QUESTION_START.match(lead) and ('?' in text or QUESTION.match(lead)):
        return Verdict(Decision.REJECT, 'standalone_question')
    return Verdict(Decision.KEEP, 'no_introduction_evidence')


def resolve_channel_id(cfg, text_channels):
    """Explicit ID wins; otherwise require exactly one matching text channel."""
    if 'channel_id' in cfg and cfg['channel_id'] is not None:
        value = cfg['channel_id']
        if isinstance(value, bool) or not str(value).isdigit():
            return None
        matches = [c.id for c in text_channels if str(c.id) == str(value)]
    else:
        name = cfg.get('channel_name', 'welcome')
        if not isinstance(name, str) or not name.strip():
            return None
        matches = [c.id for c in text_channels if c.name.casefold() == name.strip().casefold()]
    return matches[0] if len(matches) == 1 else None


def moderator_bypass(cfg, member, channel=None):
    permissions = getattr(member, 'guild_permissions', None)
    if getattr(permissions, 'administrator', False) or getattr(permissions, 'manage_messages', False):
        return True
    if channel is not None and hasattr(channel, 'permissions_for'):
        if getattr(channel.permissions_for(member), 'manage_messages', False):
            return True
    ids = cfg.get('moderator_role_ids', [])
    ids = {str(x) for x in ids} if isinstance(ids, list) else set()
    defaults = ['Moderator','Chat Moderator','Trial Chat Moderator','Lead Moderator','Admin','Administrator']
    names = cfg.get('moderator_role_names', defaults)
    names = {x.strip().casefold() for x in names if isinstance(x, str) and x.strip()} if isinstance(names, list) else set()
    # Legacy custom substrings are opt-in and match whole words, never e.g. Badminton.
    legacy = cfg.get('moderator_role_name_contains', [])
    legacy = [x.strip().casefold() for x in legacy if isinstance(x, str) and x.strip()] if isinstance(legacy, list) else []
    if 'moderator_role_name_contains' in cfg and 'moderator_role_names' not in cfg:
        names = set()
    return any(str(r.id) in ids or r.name.casefold() in names or any(
        re.search(r'(?<!\w)' + re.escape(n) + r'(?!\w)', r.name.casefold()) for n in legacy)
        for r in getattr(member, 'roles', []))
