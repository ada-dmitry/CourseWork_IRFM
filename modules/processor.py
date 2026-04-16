from collections import Counter
from functools import lru_cache
import csv
import json
from pathlib import Path
import re


WORD_RE = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)?")
DIGIT_BEFORE_WORD_RE = re.compile(r"\d[\d\s.,-]*$")

STOP_WORDS = set(
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

NUMERAL_WORDS = set(
    """
    ноль один два три четыре пять шесть семь восемь девять десять одиннадцать
    двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать
    восемнадцать девятнадцать двадцать тридцать сорок пятьдесят шестьдесят
    семьдесят восемьдесят девяносто сто двести триста четыреста пятьсот шестьсот
    семьсот восемьсот девятьсот тысяча миллион миллиард триллион полтора
    полтораста оба
    """.split()
)

NUMBER_UNITS = set(
    """
    год месяц неделя день сутки час минута рубль копейка процент метр километр грамм
    килограмм литр
    """.split()
)

PROPER_WORDS = set(
    """
    ельцин интернет конституция кремль москва россия рф снг ссср
    """.split()
)

PROPER_PHRASES = [
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
    MORPH = pymorphy3.MorphAnalyzer()


def normalize(word: str) -> str:
    return word.lower().replace("ё", "е")


@lru_cache(maxsize=100_000)
def parse_word(word: str):
    if MORPH is None:
        return normalize(word), ""

    parsed = MORPH.parse(normalize(word))
    if not parsed:
        return normalize(word), ""

    best = parsed[0]
    return normalize(best.normal_form), str(best.tag)


def has_tag(tag: str, names: set[str]) -> bool:
    return bool(set(re.split(r"[, ]+", tag)) & names)


def is_numeral(lemma: str, tag: str) -> bool:
    return lemma in NUMERAL_WORDS or has_tag(tag, {"NUMR", "Anum"})


def is_proper_name(lemma: str, tag: str) -> bool:
    return lemma in PROPER_WORDS or has_tag(tag, {"Name", "Surn", "Patr", "Geox", "Orgn"})


def find_phrase_positions(lemmas: list[str]) -> set[int]:
    positions = set()

    for phrase in PROPER_PHRASES:
        phrase_len = len(phrase)
        for start in range(len(lemmas) - phrase_len + 1):
            if lemmas[start : start + phrase_len] == phrase:
                positions.update(range(start, start + phrase_len))

    return positions


def words_from_line(line: str):
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


def prepared_terms(text: str):
    for line_number, line in enumerate(text.splitlines(), start=1):
        for word in good_words_from_line(line):
            yield word["lemma"], line_number, word["char"], word["source"]


def prepare_text(text: str) -> str:
    lines = []

    for line in text.splitlines():
        lemmas = [word["lemma"] for word in good_words_from_line(line)]
        if lemmas:
            lines.append(" ".join(lemmas))

    return "\n".join(lines)


def build_subject_index(text: str, top_n: int = 100) -> list[dict]:
    counts = Counter()
    first_place = {}

    for lemma, line, char, source in prepared_terms(text):
        counts[lemma] += 1
        first_place.setdefault(lemma, (line, char, source))

    result = []
    for lemma, count in counts.most_common(top_n):
        line, char, source = first_place[lemma]
        result.append(
            {
                "word": lemma,
                "count": count,
                "line": line,
                "char": char,
                "source_word": source,
            }
        )

    return result


def write_subject_index_csv(entries: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(["word", "count", "line", "char", "source_word"])
        for entry in entries:
            writer.writerow(
                [
                    entry["word"],
                    entry["count"],
                    entry["line"],
                    entry["char"],
                    entry["source_word"],
                ]
            )


def write_subject_index_json(entries: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(entries, file, ensure_ascii=False, indent=2)
