from elasticsearch import Elasticsearch
from pymongo import MongoClient
from pprint import pprint
from tqdm import tqdm
import json
import os


class DB:
    IND = "appsearch"

    def __init__(self, addr, force_delete=False):
        self.db = MongoClient('mongodb+srv://app:Pk9mJ9FGy2OEGiyy@cluster0.vpufr.mongodb.net/main').main
        self.es = Elasticsearch([{'host': addr, 'port': 9200}])
        if self.es.ping():
            print('Elasticsearch connected')
        else:
            print('Elasticsearch not connected')

        self.create_index(force_delete)

    def create_index(self, force):
        if force:
            try:
                self.es.indices.delete(self.IND)
            except:
                pass
        if not self.es.indices.exists(self.IND):
            self.es.indices.create(index=self.IND)
            print('Index created')
            self.es.indices.close(self.IND)
            self.es.indices.put_settings(index=self.IND, body=json.load(open('data/es_settings.json')))
            self.es.indices.put_mapping(index=self.IND, body=json.load(open('data/es_mapping.json')))
            print("Index configured")
            self.es.indices.open(self.IND)
            self.es.indices.refresh(index=self.IND)
            print("Index opened")

    def insert(self, data):
        return self.es.index(index=self.IND, body=data)

    def update_es(self):
        res = self.db.apps.find({})
        for i in tqdm(res, total=res.res.count_documents()):
            self.insert({
                "title": i["title"],
                "description": i["description"],
                "category": i["category"],
                "tags": i["tags"],
                "company": "",
                "extid": str(i["_id"])
            })

    def category_search(self, text):
        return self.es.search(
            index=self.IND,
            body={
                "query": {
                    "match": {
                        "category": text
                    }
                }
            })

    def search(self, text):
        return self.es.search(
            index=self.IND,
            body={
                "query": {
                    "match": {
                        "title": text
                    }
                }
            })


if __name__ == "__main__":
    s = DB("212.109.197.144", os.environ.get('ERASE_ES', False))
    pprint(s.search("книи"))
