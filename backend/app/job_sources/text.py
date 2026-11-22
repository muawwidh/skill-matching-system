"""Text helpers for imported postings: HTML to text, language and location checks."""
import hashlib
import html
import re
from html.parser import HTMLParser

_TAG = re.compile(r"</?[a-z][a-z0-9]*(?:\s[^<>]*)?/?>", re.I)
_BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section",
               "article", "header", "footer", "blockquote", "table", "hr"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK_TAGS - {"ul", "ol"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS - {"li", "br"}:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(markup: str) -> str:
    """Plain text: blocks separated by a blank line, one line per list item with a leading "- "."""
    if not markup:
        return ""
    if "&lt;" in markup and "<" not in markup:  # Greenhouse returns escaped HTML
        markup = html.unescape(markup)
    text = markup
    # Some postings nest escaped HTML inside HTML; parse until no tags remain (at most three passes).
    for _ in range(3):
        parser = _TextExtractor()
        parser.feed(text)
        parser.close()
        text = "".join(parser.parts)
        if not _TAG.search(text):
            break
    lines = []
    for line in text.replace("\xa0", " ").splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line in {"", "-"}:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        lines.append(line)
    return "\n".join(lines).strip()


# Frequent function words; a simple, dependency-free language check.
_STOPWORDS = {
    "en": set("the and of to in for with on you we our are is be as or will your this that from at an by have "
              "who what can about work team experience".split()),
    "de": set("der die das und zu in den von mit für ist ein eine wir sie du auf im dem nicht auch bei als "
              "oder uns unsere deine dich wird werden kenntnisse erfahrung".split()),
    "fr": set("le la les et de des du un une pour dans avec sur nous vous est en au aux qui que vos notre".split()),
    "nl": set("de het een en van voor met op je jij wij ons onze is zijn bij als ook naar".split()),
    "es": set("el la los las y de del en para con por un una que es nuestro nuestra tu su".split()),
    "it": set("il lo la gli le e di del della per con un una che è nostro nostra tuo".split()),
    "pt": set("o a os as e de do da em para com um uma que é nosso nossa você".split()),
    "pl": set("i w na z do się jest oraz dla nie od po jak że".split()),
    "sv": set("och att det som en ett för med på är vi du av till".split()),
}
_WORD = re.compile(r"[a-zà-ÿäöüßąćęłńóśźżåø]+", re.I)


def detect_language(text: str) -> str:
    """Best-guess language code from stopword counts, or "unknown" for very short or unclear text."""
    words = [word.lower() for word in _WORD.findall(text)]
    if len(words) < 15:
        return "unknown"
    scores = {language: sum(1 for word in words if word in stopwords)
              for language, stopwords in _STOPWORDS.items()}
    best = max(scores, key=scores.get)
    if scores[best] < max(3, len(words) * 0.03):
        return "unknown"
    return best


def is_english(title: str, description: str) -> bool:
    return detect_language(f"{title}\n{description}") == "en"


_EUROPE = re.compile(
    r"\b(europe|european union|emea|\beu\b|eea|germany|deutschland|austria|switzerland|netherlands|belgium|"
    r"luxembourg|france|spain|portugal|italy|ireland|united kingdom|\buk\b|england|scotland|wales|denmark|"
    r"sweden|norway|finland|iceland|estonia|latvia|lithuania|poland|czech|slovakia|hungary|slovenia|croatia|"
    r"romania|bulgaria|greece|cyprus|malta|serbia|berlin|munich|münchen|hamburg|frankfurt|cologne|köln|"
    r"stuttgart|düsseldorf|leipzig|dresden|amsterdam|rotterdam|utrecht|dublin|paris|lyon|madrid|barcelona|"
    r"valencia|lisbon|porto|milan|rome|turin|vienna|zurich|zürich|geneva|basel|brussels|antwerp|copenhagen|"
    r"stockholm|gothenburg|oslo|helsinki|warsaw|krakow|kraków|wroclaw|wrocław|gdansk|prague|brno|budapest|"
    r"bucharest|sofia|athens|vilnius|kaunas|riga|tallinn|london|manchester|edinburgh|glasgow|cambridge|oxford|"
    r"bristol|belfast|cardiff|leeds|birmingham)\b", re.I)
_REMOTE = re.compile(r"\b(remote|anywhere|worldwide|distributed|home[- ]?based|work from home)\b", re.I)
_OTHER_REGION = re.compile(
    r"\b(united states|\bus\b|usa|u\.s\.|americas|north america|latam|latin america|canada|mexico|brazil|"
    r"argentina|colombia|chile|apac|asia|india|japan|singapore|australia|new zealand|china|korea|philippines|"
    r"indonesia|israel|uae|dubai|south africa|nigeria|kenya|egypt|turkey|saudi)\b", re.I)


def is_europe_or_remote(location: str, remote: bool = False) -> bool:
    """EU/EEA, UK or Switzerland; or remote without a non-European region named."""
    if _EUROPE.search(location or ""):
        return True
    if (remote or _REMOTE.search(location or "")) and not _OTHER_REGION.search(location or ""):
        return True
    return False


def content_hash(title: str, company: str, description: str) -> str:
    """Hash of the normalized posting text, used to drop the same posting listed twice."""
    normalized = " ".join(f"{title}\n{company}\n{description}".casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# --- Contact details -------------------------------------------------------------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)
# International (+.. / 00..) or trunk-prefixed (0..) numbers with 8-15 digits; salaries and years do not match.
_PHONE = re.compile(r"(?<![\w+.,])(?:\+|00|\(0|0)\d[\d\s().\-/]{6,}\d(?!\w)")
_NAME_WORD = r"[A-ZÄÖÜÉÈ][a-zäöüßéèáíóúñ'’-]+"
# A personal name right after a contact cue, e.g. "Recruiter: Jane Example", "reach out to Max Muster",
# "Ihre Ansprechpartnerin: Frau Anna Maria Muster", "neem contact op met Sanne de Vries".
_CONTACT_NAME = re.compile(
    r"(?P<cue>(?i:\b(?:contact(?:\s+person)?|your\s+contact|point\s+of\s+contact|recruiter|talent\s+partner|"
    r"hiring\s+manager|reach\s+out\s+to|get\s+in\s+touch\s+with|ansprechpartner(?:in)?|kontakt|"
    r"wenden\s+sie\s+sich(?:\s+bitte)?\s+an|contact\s+opnemen\s+met|contact\s+op\s+met|interlocuteur)"
    r"\s*[:\-–]?\s*(?:(?:mr|ms|mrs|dr|herr|frau|mevrouw|meneer)\.?\s+)?))"
    rf"(?P<name>{_NAME_WORD}(?:\s+(?:(?:van|von|de|der|den|da|di|le|la)\s+)?{_NAME_WORD}){{1,2}})")
# Words that make a capitalised phrase a role, team or process step rather than a person.
_NOT_NAME_WORDS = set(
    "us the our your team teams talent people recruiting recruiter recruitment interview call intro screening "
    "hiring manager hr human resources department office support customer service legal compliance data "
    "protection privacy officer acquisition partner lead engineering product sales finance operations "
    "assessment chat stage round panel technical final first second process application".split())


def _digits(value: str) -> int:
    return sum(character.isdigit() for character in value)


def strip_contact_details(text: str) -> tuple[str, dict[str, int]]:
    """Replace e-mail addresses, phone numbers and named contacts in a posting.

    E-mails and phone numbers (8-15 digits, international or trunk prefix) are
    replaced everywhere. A personal name is replaced only right after a contact
    cue ("Recruiter:", "reach out to", "Ansprechpartnerin", ...), so ordinary
    sentences that mention "contact" are kept. Returns the text and counts.
    """
    counts = {"emails": 0, "phones": 0, "names": 0}

    def replace_name(match: re.Match) -> str:
        name = match.group("name")
        if any(word.casefold() in _NOT_NAME_WORDS for word in name.split()):
            return match.group(0)
        counts["names"] += 1
        return f"{match.group('cue')}[name removed]"

    lines = []
    for line in text.splitlines():
        counts["emails"] += len(_EMAIL.findall(line))
        line = _EMAIL.sub("[e-mail removed]", line)
        for phone in _PHONE.findall(line):
            if 8 <= _digits(phone) <= 15:
                counts["phones"] += 1
                line = line.replace(phone, "[phone removed]")
        lines.append(_CONTACT_NAME.sub(replace_name, line))
    return "\n".join(lines), counts
