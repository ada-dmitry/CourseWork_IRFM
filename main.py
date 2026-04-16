from modules.crawler import crawl_document
from modules.processor import (
    build_subject_index,
    prepare_text,
    write_subject_index_csv,
    write_subject_index_json,
)


SOURCE_URL = "https://www.consultant.ru/document/cons_doc_LAW_10699/"
OUTPUT_DIR = "output"

def main():
    from pathlib import Path

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)

    pages = crawl_document(SOURCE_URL)
    original_text = "\n".join(page["text"] for page in pages)

    prepared_text = prepare_text(original_text)
    subject_index = build_subject_index(original_text, top_n=100)

    (output_dir / "uk_rf_original.txt").write_text(original_text, encoding="utf-8")
    (output_dir / "uk_rf_prepared.txt").write_text(prepared_text, encoding="utf-8")
    write_subject_index_csv(subject_index, output_dir / "uk_rf_subject_index.csv")
    write_subject_index_json(subject_index, output_dir / "uk_rf_subject_index.json")

    print(f"Загружено статей: {len(pages)}")
    print(f"Строк исходного текста: {len(original_text.splitlines())}")
    print(f"Лемм после обработки: {len(prepared_text.split())}")
    print("Топ-10 предметного указателя:")
    for entry in subject_index[:10]:
        print(f"{entry['word']}: {entry['count']} (строка {entry['line']}, символ {entry['char']})")

if __name__ == "__main__":
    main()
