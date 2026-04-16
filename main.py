from modules.crawler import crawl_document

def main():
    url = "https://www.consultant.ru/document/cons_doc_LAW_10699/"
    print(crawl_document(url))

if __name__ == "__main__":
    main()
