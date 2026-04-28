## Как работает index

Index находится в `modules/index.py`. Его задача: взять исходный текст УК РФ и построить предметный указатель — топ-N наиболее частотных лемм с позицией первого вхождения.

Модуль использует `good_words_from_line` из `modules/processor.py` и ничего не знает о загрузке или обходе страниц.

## Что делает index

1. Обходит текст построчно и извлекает «хорошие» слова через `processor.py`.
2. Считает частоту каждой леммы.
3. Запоминает, где лемма встретилась впервые.
4. Возвращает топ-N по частоте.
5. Сохраняет результат в CSV и JSON.

## Генератор prepared_terms

```python
prepared_terms(text)
```

Обходит текст построчно и для каждого слова, прошедшего фильтрацию, выдаёт кортеж:

```python
(лемма, номер_строки, позиция_символа, исходное_слово)
```

Нумерация строк начинается с `1`, позиция символа — 1-based, как в `processor.py`.

## Построение предметного указателя

```python
build_subject_index(text, top_n=100)
```

Алгоритм:

1. Проходит по всем словам через `prepared_terms`.
2. Считает частоты через `Counter`.
3. Запоминает первое вхождение каждой леммы через `setdefault` — первый вызов выигрывает, последующие игнорируются.
4. Берёт `top_n` самых частотных лемм.

Одна запись результата:

```python
{
    "word": "срок",
    "count": 3342,
    "line": 34,
    "char": 151,
    "source_word": "срок",
}
```

## Запись результатов

Для сохранения индекса есть две функции.

```python
write_subject_index_csv(entries, path)
```

Сохраняет CSV с разделителем `;`:

```text
word;count;line;char;source_word
срок;3342;34;151;срок
```

```python
write_subject_index_json(entries, path)
```

Сохраняет JSON с отступами и без ASCII-экранирования кириллицы (`ensure_ascii=False`).

## Где используется index

В `main.py`:

```python
subject_index = build_subject_index(original_text, top_n=100)
write_subject_index_csv(subject_index, output_dir / "uk_rf_subject_index.csv")
write_subject_index_json(subject_index, output_dir / "uk_rf_subject_index.json")
```

Входные данные — исходный текст статей до лемматизации (`original_text`), а не подготовленный. Лемматизация происходит внутри через `processor.py`.
