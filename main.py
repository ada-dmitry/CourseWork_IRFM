from modules.crawler import crawl_document
from modules.processor import prepare_text
from modules.index import build_subject_index, write_subject_index_csv, write_subject_index_json
from pathlib import Path


SOURCE_URL = "https://www.consultant.ru/document/cons_doc_LAW_10699/"
OUTPUT_DIR = "output"

def main():
    output_dir = Path(OUTPUT_DIR) # Служебные вызовы для создания директории вывода
    output_dir.mkdir(exist_ok=True)

    pages = crawl_document(SOURCE_URL) # Вызов краулера на исходный url для рекурсивного обхода
    original_text = "\n".join(page["text"] for page in pages) # Складываем результат работы краулера в единую строку

    prepared_text = prepare_text(original_text) # Вызов препаратора на полученную строку для обработки
    subject_index = build_subject_index(original_text, top_n=100) # Строим предметный указатель

    (output_dir / "uk_rf_original.txt").write_text(original_text, encoding="utf-8") # Вывод исходного текста в файл
    (output_dir / "uk_rf_prepared.txt").write_text(prepared_text, encoding="utf-8") # Вывод токенизированного и обработанного текста в файл
    write_subject_index_csv(subject_index, output_dir / "uk_rf_subject_index.csv") # Вывод предметного указателя в csv 
    write_subject_index_json(subject_index, output_dir / "uk_rf_subject_index.json") # Предметные указатель в json

    print(f"Загружено статей: {len(pages)}")
    print(f"Строк исходного текста: {len(original_text.splitlines())}")
    print(f"Лемм после обработки: {len(prepared_text.split())}")
    print("Топ-10 предметного указателя:")
    for entry in subject_index[:10]:
        print(f"{entry['word']}: {entry['count']} (строка {entry['line']}, символ {entry['char']})")

if __name__ == "__main__":
    main()
