from elasticsearch import Elasticsearch


class Search:
    def __init__(self, addr):
        self.es = Elasticsearch([{'host': addr, 'port': 9200}])
        if self.es.ping():
            print('Elasticsearch connected')
        else:
            print('Elasticsearch not connected')


if __name__ == "__main__":
    s = Search("212.109.197.144")
