from functools import lru_cache
import re


WORD_RE = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)?")
DIGIT_BEFORE_WORD_RE = re.compile(r"\d[\d\s.,-]*$")

STOP_WORDS = set( # Стоп-слова (выведены вручную)
    """
    а без более бы бывший был была были было быть в во весь вместе вне вновь все всего
    всей всем всеми всех вследствие вы где да для до его ее если есть же за из или им
    ими их к как ко когда который ли либо между менее мочь на над надо наиболее
    настоящий не него нее нет ни них но о об оба однако он она они оно от перед по под
    после при про с со свой себя так также такой там то того той только том тот у уже
    чем через что чтобы эта эти это этот являться абзац глава данный кодекс пункт
    раздел статья часть
    """.split()
)

NUMERAL_WORDS = set( # Числительные (выведены вручную)
    """
    ноль один два три четыре пять шесть семь восемь девять десять одиннадцать
    двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать
    восемнадцать девятнадцать двадцать тридцать сорок пятьдесят шестьдесят
    семьдесят восемьдесят девяносто сто двести триста четыреста пятьсот шестьсот
    семьсот восемьсот девятьсот тысяча миллион миллиард триллион полтора
    полтораста оба
    """.split()
)

NUMBER_UNITS = set( # Слова-спутники числительных (тоже малоинформативны)
    """
    год месяц неделя день сутки час минута рубль копейка процент метр километр грамм
    килограмм литр
    """.split()
)

PROPER_WORDS = set( # Имена собственные
    """
    ельцин интернет конституция кремль москва россия рф снг ссср
    """.split()
)

PROPER_PHRASES = [ # Имена собственные в формате словосочетаний
    phrase.split()
    for phrase in [
        "арбитражный процессуальный кодекс",
        "верховный суд",
        "вооруженный сила",
        "государственный дума",
        "гражданский кодекс",
        "евразийский экономический союз",
        "земельный кодекс",
        "конституционный суд",
        "конституция российский федерация",
        "международный уголовный суд",
        "налоговый кодекс",
        "организация объединить нация",
        "правительство российский федерация",
        "президент российский федерация",
        "российский федерация",
        "совет безопасность",
        "совет федерация",
        "содружество независимый государство",
        "таможенный союз",
        "трудовой кодекс",
        "уголовно-исполнительный кодекс",
        "уголовно-процессуальный кодекс",
        "уголовный кодекс",
        "федеральный закон",
        "федеральный собрание",
        "центральный банк",
    ]
]

try:
    import pymorphy3
except ImportError:
    MORPH = None
else:
    MORPH = pymorphy3.MorphAnalyzer() # Почему не SpaCy? - потому что использовать NLP для простой лемматизации - это пушкой по воробьям. А PyMorphy - это просто большой словарь (и все равно меньше, чем модель), который анализирует русскую морфологию - по-умному - конечный автомат по словарю.


@lru_cache(maxsize=100_000)
def parse_word(word: str):
    """Возвращает (лемма, тег) для слова. Кешируем, чтобы не прогонять одно и то же через модуль постоянно.

    «ё» → «е» для единообразия леммы в словаре и при сравнении.
    Если pymorphy3 не установлен, тег пустой, лемма = lower().
    Берём первый (наиболее вероятный) разбор pymorphy3.
    """
    w = word.lower().replace("ё", "е")
    if MORPH is None:
        return w, ""

    parsed = MORPH.parse(w)
    if not parsed:
        return w, ""

    best = parsed[0]
    return best.normal_form.lower().replace("ё", "е"), str(best.tag)


@lru_cache(maxsize=10_000)
def _tag_parts(tag: str) -> frozenset[str]:
    """Разбивает строку тега pymorphy3 на множество граммем для быстрого поиска."""
    return frozenset(re.split(r"[, ]+", tag))


def has_tag(tag: str, names: set[str]) -> bool:
    """Проверяет, содержит ли тег хотя бы одну из граммем из names."""
    return bool(_tag_parts(tag) & names)


def is_numeral(lemma: str, tag: str) -> bool:
    """True если слово — числительное: по словарю NUMERAL_WORDS или тегу NUMR/Anum."""
    return lemma in NUMERAL_WORDS or has_tag(tag, {"NUMR", "Anum"})


def is_proper_name(lemma: str, tag: str) -> bool:
    """True если слово — имя собственное: по словарю PROPER_WORDS или тегу Name/Surn/Patr/Geox/Orgn."""
    return lemma in PROPER_WORDS or has_tag(tag, {"Name", "Surn", "Patr", "Geox", "Orgn"})


def find_phrase_positions(lemmas: list[str]) -> set[int]:
    """Возвращает индексы лемм, входящих в устойчивые фразы-собственные из PROPER_PHRASES.

    Скользящим окном ищет каждую фразу в списке лемм и помечает все её позиции,
    чтобы is_bad_word мог отфильтровать их целиком.
    """
    positions = set()

    for phrase in PROPER_PHRASES:
        phrase_len = len(phrase)
        for start in range(len(lemmas) - phrase_len + 1):
            if lemmas[start : start + phrase_len] == phrase:
                positions.update(range(start, start + phrase_len))

    return positions


def words_from_line(line: str):
    """Разбирает строку на слова и возвращает список dict с морфологическими данными.

    Каждый dict: source — оригинальное слово, lemma, tag, char — 1-based позиция
    в строке, after_digit — стоит ли перед словом число (для фильтрации единиц измерения).
    """
    words = []

    for match in WORD_RE.finditer(line):
        word = match.group()
        lemma, tag = parse_word(word)
        before_word = line[: match.start()].rstrip()
        words.append(
            {
                "source": word,
                "lemma": lemma,
                "tag": tag,
                "char": match.start() + 1,
                "after_digit": bool(DIGIT_BEFORE_WORD_RE.search(before_word)),
            }
        )

    return words


def is_bad_word(word: dict, phrase_positions: set[int], index: int, after_number: bool) -> bool:
    """Возвращает True если слово нужно отфильтровать.

    Причины отсева: длина ≤ 2, стоп-слово, часть устойчивой фразы-собственной,
    имя собственное, числительное, единица измерения после числа.
    after_number — признак того, что предыдущее значимое слово было числительным
    (передаётся из good_words_from_line для цепочек вида «пять лет»).
    """
    lemma = word["lemma"]
    tag = word["tag"]

    if len(lemma) <= 2 or lemma in STOP_WORDS:
        return True
    if index in phrase_positions or is_proper_name(lemma, tag):
        return True
    if is_numeral(lemma, tag):
        return True
    if lemma in NUMBER_UNITS and (after_number or word["after_digit"]):
        return True

    return False


def good_words_from_line(line: str):
    """Генератор: выдаёт только «хорошие» слова строки после всех фильтров.

    Сначала вычисляет позиции фраз-собственных, затем идёт по словам,
    отслеживая флаг after_number — он сбрасывается на каждом не-числительном,
    чтобы точно отловить единицы измерения, стоящие сразу после числа.
    """
    words = words_from_line(line)
    phrase_positions = find_phrase_positions([word["lemma"] for word in words])
    after_number = False

    for index, word in enumerate(words):
        bad = is_bad_word(word, phrase_positions, index, after_number)
        after_number = is_numeral(word["lemma"], word["tag"]) or (
            word["lemma"] in NUMBER_UNITS and (after_number or word["after_digit"])
        )

        if not bad:
            yield word


def prepare_text(text: str) -> str:
    """Возвращает отфильтрованный текст: каждая строка — леммы через пробел.

    Пустые строки (все слова отсеяны) пропускаются.
    """
    lines = []

    for line in text.splitlines():
        lemmas = [word["lemma"] for word in good_words_from_line(line)]
        if lemmas:
            lines.append(" ".join(lemmas))

    return "\n".join(lines)
