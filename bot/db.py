import json
from functools import reduce

from bson import ObjectId
from elasticsearch import Elasticsearch
from pymongo import MongoClient
from tqdm import tqdm


class DB:
    IND = "appsearch"

    def __init__(self, mdb_conn, es_conn, force_delete=False):
        self.db = MongoClient(mdb_conn).main
        self.es = Elasticsearch([{'host': es_conn, 'port': 9200}])
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
            self.update_es()

    def insert(self, data):
        return self.es.index(index=self.IND, body=data)

    def update_es(self):
        res = self.db.apps.find({})
        for i in tqdm(res, total=res.count()):
            i["extid"] = str(i["_id"])
            del i["_id"]
            self.insert(i)
        print("Finishing copying records")

    def execute_search(self, **params):
        def proc(x):
            x["_source"]["_score"] = x["_score"]
            return x["_source"]

        try:
            return list(map(proc, self.es.search(timeout="2s", **params)['hits']['hits']))
        except:
            return []

    def execute_msearch(self, allow_remove_source=True, **params):
        def proc(x):
            if allow_remove_source and len(x["_source"]) == 1:
                return x["_source"].popitem()[1]
            x["_source"]["_score"] = x["_score"]
            return x["_source"]

        try:
            data = self.es.msearch(body=reduce(
                lambda x, y: x + [{"index": params["index"]}, y],
                params["body"],
                [])
            )['responses']
            return reduce(lambda x, y: x + list(map(proc, y['hits']['hits'])), data, [])
        except:
            return []

    def category_search(self, text):
        return self.execute_search(
            index=self.IND,
            body={
                "query": {
                    "match": {
                        "category": text
                    }
                }
            }
        )

    def search(self, txt):
        return self.execute_msearch(index=self.IND, body=[
            {
                "query": {
                    "match": {
                        "title": txt
                    }
                },
            },
            {
                "query": {
                    "match": {
                        "description": txt
                    }
                },
            }
        ])

    def get_ids_for_query(self, txt):
        res = self.execute_msearch(index=self.IND, body=[
            {
                "query": {
                    "match": {
                        "title": txt
                    }
                },
                "_source": ["extid"],
            },
            {
                "query": {
                    "match": {
                        "description": txt
                    }
                },
                "_source": ["extid"],
            }
        ])
        return list(map(lambda x: ObjectId(x), res))

    def combine_tags(self, txt):
        res = next(self.db.apps.aggregate([
            {
                "$match": {
                    "_id": {
                        "$in": self.get_ids_for_query(txt),
                    }
                }
            },
            {
                "$unwind": "$tags"
            },
            {
                "$group": {
                    "_id": "null",
                    "tags": {
                        "$addToSet": "$tags"
                    }
                }
            }
        ]))['tags']
        if '' in res:
            res.remove('')
        return res

    def query_by_tags(self, txt, tags):
        return list(self.db.apps.find(
            {
                "$and": [{
                    "_id": {
                        "$in": self.get_ids_for_query(txt),
                    }
                }] + ([{
                    "tags": {
                        "$elemMatch": {
                            "$in": tags
                        }
                    }
                }] if len(tags) > 0 else [])
            }
        ))
