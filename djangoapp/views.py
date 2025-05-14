from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import datetime
import base64
from . import models as db
from bson import ObjectId

# ===== Basic Auth Decorator =====
def require_auth(view_func):
    def wrapper(request, *args, **kwargs):
        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith("Basic "):
            return JsonResponse({"error": "Authentication required"}, status=401)
        try:
            encoded = auth.split(" ")[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":")
            user = db.authenticate_user(username, password)
            if not user:
                return JsonResponse({"error": "Invalid credentials"}, status=401)
            request.user = user
            return view_func(request, *args, **kwargs)
        except Exception as e:
            return JsonResponse({"error": "Invalid auth format", "details": str(e)}, status=401)
    return wrapper

# ===== Role-based Access Control =====
def require_role(allowed_roles):
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            user = request.user  
            if not user:
                return JsonResponse({"error": "Unauthorized"}, status=401)
            if user["role"] not in allowed_roles:
                return JsonResponse({"error": "Forbidden"}, status=403)
            return func(request, *args, **kwargs)
        return wrapper
    return decorator

# ===== Home =====
def index(request):
    return HttpResponse("<h1>🌦️ WeatherDB API - Welcome to my API Database Project!🌦️ </h1>")

# ===== reading_routes =====
@csrf_exempt
@require_auth
def reading_routes(request):
    user = request.user

    # ============ POST ============
    if request.method == "POST":
        if user["role"] not in ["Teacher", "Sensor"]:
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            body = json.loads(request.body.decode())
            # if body.get("humidity_percent") > 100 or not (-50 <= body.get("temperature_c", 0) <= 60):
            #     return JsonResponse({"error": "Invalid weather values."}, status=400)
            temperature = body.get("Temperature (\u00b0C)")
            humidity = body.get("Humidity (%)")

            if temperature is None or humidity is None:
                return JsonResponse({"error": "Missing temperature or humidity values"}, status=400)

            if humidity > 100 or not (-50 <= temperature <= 60):
                return JsonResponse({
                    "error": "Invalid weather values. Temperature must be between -50°C and 60°C, and humidity must be 0–100%."
                }, status=400)

            result = db.insert_weather(body)
            return JsonResponse({"inserted_id": str(result.inserted_id)}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # ============ PUT/PATCH ============
        
    if request.method in ["PUT", "PATCH"]:
        if user["role"] not in ["Teacher"]:
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            data = json.loads(request.body.decode())
            _id = data.get("_id")
            update_fields = data.get("update_fields", {})

            if not _id or not update_fields:
                return JsonResponse({"error": "Missing _id or update_fields"}, status=400)

            # ✅ Validation checks
            if "Temperature (\u00b0C)" in update_fields:
                temp = update_fields["Temperature (\u00b0C)"]
                if temp < -50 or temp > 60:
                    return JsonResponse({
                        "error": "Temperature must be between -50°C and 60°C."
                    }, status=400)

            if "Humidity (%)" in update_fields:
                humidity = update_fields["Humidity (%)"]
                if humidity < 0 or humidity > 100:
                    return JsonResponse({
                        "error": "Humidity must be between 0% and 100%."
                    }, status=400)

            if "Precipitation mm/h" in update_fields:
                precip = update_fields["Precipitation mm/h"]
                if precip < 0:
                    return JsonResponse({
                        "error": "Precipitation value cannot be negative."
                    }, status=400)

            result = db.collection.update_one({"_id": ObjectId(_id)}, {"$set": update_fields})
            return JsonResponse({"message": "Updated" if result.modified_count else "No change"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)



    # ============ GET ============
    if request.method == "GET":
        if user["role"] not in ["Teacher", "Student"]:
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            try:
                body = json.loads(request.body.decode())  # ✅ Safely try to load body
            except Exception:
                body = {}  # If body is empty or not JSON, use empty dict

            _id = body.get("_id")   # ✅ Now _id comes from body
            start_time = request.GET.get("start")
            end_time = request.GET.get("end")

            # 🔥 1. If _id is provided, search by _id
            if _id:
                try:
                    record = db.collection.find_one({"_id": ObjectId(_id)})
                    if not record:
                        return JsonResponse({"error": "No record found with this ID"}, status=404)
                    record["_id"] = str(record["_id"])
                    return JsonResponse(record, status=200)
                except Exception as e:
                    return JsonResponse({"error": str(e)}, status=400)

            # 🔥 2. If start and end are provided, search by datetime
            if start_time and end_time:
                start = datetime.datetime.strptime(start_time.strip(), "%Y-%m-%dT%H:%M")
                end = datetime.datetime.strptime(end_time.strip(), "%Y-%m-%dT%H:%M")
                result = list(db.get_max_temperature(start, end))
                for d in result:
                    d["_id"] = str(d["_id"])
                return JsonResponse(result, safe=False, status=200)

            # 🔥 3. If neither _id nor start/end, return error
            return JsonResponse({"error": "Missing _id in body or start/end in URL"}, status=400)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

        

    # ============ DELETE ============
    if request.method == "DELETE":
        if user["role"] not in ["Teacher"]:
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            data = json.loads(request.body.decode())
            record_id = data.get("_id")
            if not record_id:
                return JsonResponse({"error": "Missing _id for deletion"}, status=400)

            result = db.delete_reading_by_id(record_id)
            # result = db.delete_reading_with_logging(record_id)
            if result and result.deleted_count:
                return JsonResponse({"message": "Reading deleted and logged successfully"})
            else:
                return JsonResponse({"error": "Record not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
        
    return JsonResponse({"error": "Method not allowed"}, status=405)


# ===== Multiple readings =====
@csrf_exempt
@require_auth
def multiple_readings(request):
    user = request.user

    # ===== Insert Multiple =====
    if request.method == "POST":
        if user["role"] not in ["Teacher", "Sensor"]:
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            data = json.loads(request.body.decode())
            if not isinstance(data, list) or not data:
                return JsonResponse({"error": "documents must be a non-empty list"}, status=400)
            result = db.insert_multiple_weather(data)
            return JsonResponse({"inserted_ids": [str(i) for i in result.inserted_ids]}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # ===== Retrieve Specific Record =====
    if request.method == "GET":
        if user["role"] not in ["Teacher", "Student"]:
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            _id = request.GET.get("_id")
            sensor = request.GET.get("sensor")
            start_time = request.GET.get("start", "").strip()
            end_time = request.GET.get("end", "").strip()

            # 🔥 If _id is provided, search by _id
            if _id:
                try:
                    record = db.collection.find_one(
                        {"_id": ObjectId(_id)}
                    )
                    if not record:
                        return JsonResponse({"error": "No matching record found by ID"}, status=404)

                    response = {}
                    for key in record:
                        value = record[key]
                        if key == "_id":
                            response["_id"] = str(value)
                        elif isinstance(value, datetime.datetime):
                            response["Date/Time"] = value.strftime("%d-%b-%Y %H:%M")
                        elif key == "Device Name":
                            response["Sensor Name"] = value
                        else:
                            response[key] = value

                    return JsonResponse(response, status=200)
                except Exception as e:
                    return JsonResponse({"error": str(e)}, status=400)

            # 🔥 If sensor and start/end are provided, search by sensor name and time
            if sensor and start_time and end_time:
                start = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M")
                end = datetime.datetime.strptime(end_time, "%Y-%m-%dT%H:%M")
                record = db.collection.find_one(
                    {"Device Name": sensor, "Time": {"$gte": start, "$lte": end}}
                )
                if not record:
                    return JsonResponse({"error": "No matching record found by Sensor/Time"}, status=404)

                response = {}
                for key in record:
                    value = record[key]
                    if key == "_id":
                        response["_id"] = str(value)
                    elif isinstance(value, datetime.datetime):
                        response["Date/Time"] = value.strftime("%d-%b-%Y %H:%M")
                    elif key == "Device Name":
                        response["Sensor Name"] = value
                    else:
                        response[key] = value

                return JsonResponse(response, status=200)

            return JsonResponse({"error": "Missing parameters"}, status=400)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # ===== Update Multiple Weather Readings =====
    #   # PUT
    if request.method == "PUT":
        if user["role"] not in ["Teacher", "Sensor"]:
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            data = json.loads(request.body.decode())
            
            updates = data.get("updates", [])
            if not isinstance(updates, list) or not updates:
                return JsonResponse({"error": "updates must be a non-empty list of {id, update_fields} items"}, status=400)

            modified_count = 0

            for item in updates:
                record_id = item.get("id")
                update_fields = item.get("update_fields", {})
                if not record_id or not update_fields:
                    continue  # skip incomplete entries

                # Optional: temperature validation here
                if "Temperature (\u00b0C)" in update_fields:
                    temp = update_fields["Temperature (\u00b0C)"]
                    if temp < -50 or temp > 60:
                        return JsonResponse({
                            "error": f"Temperature for record {record_id} must be between -50°C and 60°C."
                        }, status=400)

                result = db.collection.update_one(
                    {"_id": ObjectId(record_id)},
                    {"$set": update_fields}
                )
                modified_count += result.modified_count

            return JsonResponse({"message": f"Updated {modified_count} record(s)"})

            return JsonResponse({"message": f"Updated {result.modified_count} record(s)"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
        
    # ===== Update Multiple Weather Readings (PATCH) =====
    elif request.method == "PATCH":
        if user["role"] not in ["Teacher", "Sensor"]:
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            data = json.loads(request.body.decode())  # ✅ define 'data' here inside the try block
            updates = data.get("updates", [])
            if not isinstance(updates, list) or not updates:
                return JsonResponse({"error": "updates must be a non-empty list of {id, update_fields} items"}, status=400)

            modified_count = 0

            for item in updates:
                record_id = item.get("id")
                update_fields = item.get("update_fields", {})
                if not record_id or not update_fields:
                    continue  # skip incomplete entries

                # Optional: temperature validation
                if "Temperature (\u00b0C)" in update_fields:
                    temp = update_fields["Temperature (\u00b0C)"]
                    if temp < -50 or temp > 60:
                        return JsonResponse({
                            "error": f"Temperature for record {record_id} must be between -50°C and 60°C."
                        }, status=400)

                result = db.collection.update_one(
                    {"_id": ObjectId(record_id)},
                    {"$set": update_fields}
                )
                modified_count += result.modified_count

            return JsonResponse({"message": f"Updated {modified_count} record(s)"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    # ===== Delete Multiple Weather Readings =====
    elif request.method == "DELETE":
        if user["role"] not in ["Teacher"]:
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            data = json.loads(request.body.decode())
            ids = data.get("ids", [])
            if not isinstance(ids, list) or not ids:
                return JsonResponse({"error": "ids must be a non-empty list"}, status=400)

            object_ids = [ObjectId(i) for i in ids]
            # result = db.collection.delete_many({"_id": {"$in": object_ids}})

            # return JsonResponse({"message": f"Deleted {result.deleted_count} record(s)"})
            deleted_count = 0
            for oid in object_ids:
                record = db.collection.find_one({"_id": oid})
                if record:
                    record["deleted_at"] = datetime.datetime.utcnow()
                    db.log_collection.insert_one(record)
                    db.collection.delete_one({"_id": oid})
                    deleted_count += 1

            return JsonResponse({"message": f"Deleted and logged {deleted_count} record(s)"})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)



    # ===== Invalid Method =====
    return JsonResponse({"error": "Method not allowed"}, status=405) 


# ===== Insert a user =====
@csrf_exempt
@require_auth
@require_role(["Admin", "Teacher"])
def insert_user(request):
    if request.method == "POST":
        try:
            user_data = json.loads(request.body.decode())
            result = db.insert_user_data(user_data)
            if not result:
                return JsonResponse({"error": "User creation failed"}, status=500)
            return JsonResponse({
                "message": "User created successfully",
                "user_id": str(result.inserted_id),
                "username": user_data.get("username"),
                "role": user_data.get("role")
            }, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ===== Delete user by ID (URL param) =====
@csrf_exempt
@require_auth
@require_role(["Teacher"])
def delete_user(request, id):
    if request.method == "DELETE":
        try:
            result = db.delete_user_by_id(id)
            return JsonResponse({"message": "Deleted" if result.deleted_count else "Not found"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ===== Delete multiple students =====
@csrf_exempt
@require_auth
@require_role(["Admin", "Teacher"])
def multiple_users(request):
    user = request.user  
    
    # ===== Delete user by role and date =====

    if request.method == "DELETE":
        try:
            data = json.loads(request.body.decode())
            start = datetime.datetime.strptime(data["start"], "%Y-%m-%d")
            end = datetime.datetime.strptime(data["end"], "%Y-%m-%d")
            # result = db.delete_students_by_date(start, end)
            role = data.get("role", "Student")  # default to Student if not specified
            requester_role = user["role"]       # role of who is making the request

            # Only Admin can delete Teachers
            if role == "Teacher" and requester_role != "Admin":
                return JsonResponse({"error": "Only Admins can delete Teacher accounts"}, status=403)

            # Proceed to delete
            result = db.user_collection.delete_many({
                "role": role,
                "last_login": {"$gte": start, "$lte": end}
            })


            return JsonResponse({"message": f"{result.deleted_count} deleted"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
        
    elif request.method == "PATCH":
        try:
            data = json.loads(request.body.decode())
            start = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d")
            end = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d")
            result = db.update_user_roles(start, end, data["new_access"])
            return JsonResponse({"message": f"Updated {result.modified_count} user(s)"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
        
    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)


# ===== Update precipitation (PUT or PATCH) =====
#@csrf_exempt
#@require_auth
#@require_role(["Teacher"])
#def update_precipitation(request):
    

# ===== Update multiple user access =====
# @csrf_exempt
# @require_auth

# ===== Login =====
@csrf_exempt
def login(request):
    if request.method == "PATCH":
        try:
            credentials = json.loads(request.body.decode())
            username = credentials.get("username")
            password = credentials.get("password")
            if not username or not password:
                return JsonResponse({"error": "Username and password required"}, status=400)
            user = db.authenticate_user(username, password)
            if not user:
                return JsonResponse({"error": "Invalid credentials"}, status=401)
            db.user_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"last_login": datetime.datetime.utcnow()}}
            )
            return JsonResponse({"message": "Login successful", "role": user["role"]})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ===== Max precipitation (5 months) =====
@csrf_exempt
@require_auth
@require_role(["Teacher", "Student"])
def max_precipitation_5months(request):
    if request.method == "GET":
        try:
            sensor = request.GET.get("sensor")
            result = db.get_max_precipitation(sensor)
            output = [{"Sensor Name": d.get("Device Name"), "Reading Date/Time": d.get("Time").strftime("%d-%b-%Y %H:%M"), "precipitation_mm_per_h": d.get("Precipitation mm/h")} for d in result]
            return JsonResponse(output, safe=False)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ===== Max temperature range =====
#@csrf_exempt
#@require_auth
#@require_role(["Teacher", "Student"])
#def max_temperature_range(request):
    

# ===== Indexed query =====
@csrf_exempt
@require_auth
@require_role(["Teacher", "Student"])
def temperature_index_query(request):
    if request.method == "GET":
        try:
            low = float(request.GET["low"])
            high = float(request.GET["high"])
            result = list(db.temperature_range_query(low, high))
            for d in result:
                d["_id"] = str(d["_id"])
            return JsonResponse(result, safe=False)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


# ===== Multiple records max temp =====
@csrf_exempt
@require_auth
@require_role(["Teacher", "Student"])
def retrieve_max_temp_multiple_records(request):
    if request.method == "GET":
        try:
            start_time = request.GET.get("start")
            end_time = request.GET.get("end")
            if not (start_time and end_time):
                return JsonResponse({"error": "Missing start or end parameter"}, status=400)
            start = datetime.datetime.strptime(start_time, "%Y-%m-%d")
            end = datetime.datetime.strptime(end_time, "%Y-%m-%d")
            pipeline = [{"$match": {"Time": {"$gte": start, "$lte": end}}}, {"$group": {"_id": "$Device Name", "MaxTemperature": {"$max": "$Temperature (\u00b0C)"}, "Time": {"$first": "$Time"}}}]
            result = list(db.collection.aggregate(pipeline))
            if not result:
                return JsonResponse({"error": "No records found"}, status=404)
            output = [{"Sensor Name": r.get("_id"), "Reading Date/Time": r.get("Time").strftime("%d-%b-%Y %H:%M"), "Max Temperature (°C)": r.get("MaxTemperature")} for r in result]
            return JsonResponse(output, safe=False, status=200)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)