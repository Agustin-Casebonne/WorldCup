from pymongo import MongoClient

MONGO_URI = ""  # pega tu URI aquí
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

db = client['worldcup']
coll = db['matches']

print("Count:", coll.count_documents({}))
print("One document sample:")
doc = coll.find_one({})
print(doc)

# Ejemplo: últimos 5 partidos por fecha (si hay campo 'date' en formato ISO)
for d in coll.find({}).sort("date",-1).limit(5):
    print(d["date"], d.get("home_team"), d.get("away_team"), d.get("home_score"), d.get("away_score"))