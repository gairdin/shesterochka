from pymongo import MongoClient

# Подключение к MongoDB
uri = "mongodb://localhost:27017/Cluster0"
client = MongoClient(uri)
db = client.get_database()

# Коллекция акций
promotions_collection = db["promotions"]