import csv
import json
from collections import Counter
from pathlib import Path

from modules.processor import good_words_from_line


def prepared_terms(text: str):
    """Генератор: выдаёт (лемма, номер_строки, позиция_символа, исходное_слово) для каждого хорошего слова."""
    for line_number, line in enumerate(text.splitlines(), start=1):
        for word in good_words_from_line(line):
            yield word["lemma"], line_number, word["char"], word["source"]


def build_subject_index(text: str, top_n: int = 100) -> list[dict]:
    """
    Строит предметный указатель: топ-N лемм по частоте с позицией первого вхождения.

    first_place.setdefault гарантирует, что запоминается именно первое вхождение —
    prepared_terms обходит текст сверху вниз, поэтому первый же setdefault выигрывает.
    """
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
    """Сохраняет предметный указатель в CSV с разделителем «;»."""
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
    """Сохраняет предметный указатель в JSON с отступами и без ASCII-экранирования кириллицы."""
    with path.open("w", encoding="utf-8") as file:
        json.dump(entries, file, ensure_ascii=False, indent=2)
