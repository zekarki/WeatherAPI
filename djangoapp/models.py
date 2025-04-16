from django.db import models
import pymongo
import datetime
from bson import ObjectId
import bcrypt

# ✅ MongoDB Connection
client = pymongo.MongoClient('mongodb+srv://zekarki:zekarki@cluster0.qyuc2.mongodb.net/')
db = client['WeatherDB']
collection = db['Weather']
log_collection = db['deleted_logs']
user_collection = db['Users']

# ✅ Indexes
db['Weather'].create_index("Device Name")
user_collection.create_index([("last_login", pymongo.ASCENDING)], expireAfterSeconds=30 * 24 * 60 * 60)

# ==========================
# ✅ Weather DB Functions
# ==========================

def insert_weather(data):
    """Insert a single weather record."""
    data["Time"] = datetime.datetime.utcnow()
    return collection.insert_one(data)

def insert_multiple_weather(data_list):
    """Insert multiple weather records."""
    for d in data_list:
        d["Time"] = datetime.datetime.utcnow()
    return collection.insert_many(data_list)

def get_max_precipitation(sensor):
    """Get maximum precipitation for a sensor in the last 150 days."""
    date_limit = datetime.datetime.utcnow() - datetime.timedelta(days=150)
    return collection.find(
        {"Device Name": sensor, "Time": {"$gte": date_limit}},
        {"Precipitation mm/h": 1, "Time": 1, "Device Name": 1}
    ).sort("precipitation_mm_per_h", -1).limit(1)

def get_max_temperature(start, end):
    """Get the maximum temperature within a specific date range."""
    return collection.find(
        {"Time": {"$gte": start, "$lte": end}},
        {"Device Name": 1, "Time": 1, "Temperature (\u00b0C)": 1}
    ).sort("Temperature (\u00b0C)", -1).limit(1)

def temperature_range_query(low, high):
    """Find records with temperature in the specified range."""
    return collection.find({
        "Temperature (\u00b0C)": {"$gte": low, "$lte": high}
    })

def update_precipitation_value(record_id, new_value):
    """Update the precipitation value of a specific record."""
    return collection.update_one(
        {"_id": ObjectId(record_id)},
        {"$set": {"precipitation_mm_per_h": new_value}}
    )

def delete_reading_by_id(reading_id):
    """Log the weather reading before deletion."""
    # Find the record before deleting
    reading = collection.find_one({"_id": ObjectId(reading_id)})
    if not reading:
        return None

    # Add log timestamp
    reading["deleted_at"] = datetime.datetime.utcnow()

    # Insert into log collection
    log_collection.insert_one(reading)

    # Now delete the actual reading
    return collection.delete_one({"_id": ObjectId(reading_id)})


# ==========================
# ✅ User Data Functions
# ==========================

def insert_user_data(user_data):
    """Insert a new user into the database with hashed password."""
    try:
        user_data["last_login"] = datetime.datetime.utcnow()
        user_data["created_at"] = datetime.datetime.utcnow()

        if "role" not in user_data:
            user_data["role"] = "Student"

        if "username" not in user_data or "password" not in user_data:
            return None

        hashed_pw = bcrypt.hashpw(user_data["password"].encode(), bcrypt.gensalt())
        user_data["password"] = hashed_pw.decode()

        result = user_collection.insert_one(user_data)
        return result if result.inserted_id else None

    except Exception as e:
        print("❌ Exception during insert_user_data:", e)
        return None

def delete_user_by_id(user_id):
    """Delete a user by their MongoDB ObjectId."""
    return user_collection.delete_one({"_id": ObjectId(user_id)})

def delete_students_by_date(start, end):
    """Delete students who logged in between the given date range."""
    return user_collection.delete_many({
        "role": "Student",
        "last_login": {"$gte": start, "$lte": end}
    })

def update_user_roles(start, end, new_role):
    """Update the roles of users who were created within a specific date range."""
    return user_collection.update_many(
        {"created_at": {"$gte": start, "$lte": end}},
        {"$set": {"role": new_role}}
    )

def authenticate_user(username, password):
    """Authenticate a user with the provided username and password."""
    user = user_collection.find_one({"username": username})
    if user and bcrypt.checkpw(password.encode(), user["password"].encode()):
        return user
    return None
