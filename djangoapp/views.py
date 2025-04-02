from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import datetime
import base64
from . import models as db
from bson import ObjectId

# ✅ Basic Auth decorator
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

# ✅ Role-based access decorator
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

# ✅ Home route
def index(request):
    return HttpResponse("<h1>🌦️ WeatherDB API - Welcome to my API Database Project!🌦️ </h1>")

# ✅ Example model view
@method_decorator(csrf_exempt, name='dispatch')
class TheModelView(View):
    def get(self, request):
        return JsonResponse({"message": "Model view works!"})

# ✅ Insert a weather reading (Teacher, Sensor)
@csrf_exempt
@require_auth
@require_role(["Teacher", "Sensor"])
def validate_weather_data(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body.decode())
            if body.get("humidity_percent") > 100 or not (-50 <= body.get("temperature_c", 0) <= 60):
                return JsonResponse({"error": "Invalid weather values."}, status=400)
            result = db.insert_weather(body)
            return JsonResponse({"inserted_id": str(result.inserted_id)}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ✅ Insert multiple weather readings (Teacher, Sensor)
@csrf_exempt
@require_auth
@require_role(["Teacher", "Sensor"])
def insert_multiple_readings(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode())
            if not isinstance(data, list) or not data:
                return JsonResponse({"error": "documents must be a non-empty list"}, status=400)
            result = db.insert_multiple_weather(data)
            return JsonResponse({"inserted_ids": [str(i) for i in result.inserted_ids]}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ✅ Create a new user (Teacher only)
@csrf_exempt
@require_auth
@require_role(["Teacher"])
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
    return JsonResponse({"error": "Only POST allowed"}, status=405)

# ✅ Delete user by ID (Teacher only)
@csrf_exempt
@require_auth
@require_role(["Teacher"])
def delete_user(request):
    if request.method == "DELETE":
        try:
            data = json.loads(request.body.decode())
            result = db.delete_user_by_id(data["_id"])
            return JsonResponse({"message": "Deleted" if result.deleted_count else "Not found"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ✅ Delete students by date range (Teacher only)
@csrf_exempt
@require_auth
@require_role(["Teacher"])
def delete_multiple_students(request):
    if request.method == "DELETE":
        try:
            data = json.loads(request.body.decode())
            start = datetime.datetime.strptime(data["start"], "%Y-%m-%d")
            end = datetime.datetime.strptime(data["end"], "%Y-%m-%d")
            result = db.delete_students_by_date(start, end)
            return JsonResponse({"message": f"{result.deleted_count} deleted"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ✅ Update precipitation (Teacher only)
@csrf_exempt
@require_auth
@require_role(["Teacher"])
def update_precipitation(request):
    if request.method in ["PUT", "PATCH"]:
        try:
            data = json.loads(request.body.decode())
            result = db.update_precipitation_value(data["_id"], data["new_precipitation"])
            return JsonResponse({"message": "Updated" if result.modified_count else "No change"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ✅ Update user access (Teacher only)
@csrf_exempt
@require_auth
@require_role(["Teacher"])
def update_user_access(request):
    if request.method in ["PUT", "PATCH"]:
        try:
            data = json.loads(request.body.decode())
            start = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d")
            end = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d")
            result = db.update_user_roles(start, end, data["new_access"])
            return JsonResponse({"message": f"Updated {result.modified_count} user(s)"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ✅ View: Max precipitation (last 5 months) formatted nicely
@csrf_exempt
@require_auth
@require_role(["Teacher", "Student"])
def max_precipitation_5months(request):
    if request.method == "GET":
        try:
            sensor = request.GET.get("sensor")
            result = db.get_max_precipitation(sensor)
            output = []

            for d in result:
                formatted_record = {
                    "Sensor Name": d.get("Device Name"),
                    "Reading Date/Time": d.get("Time").strftime("%d-%b-%Y %H:%M"),
                    "Precipitation (mm/h)": d.get("Precipitation mm/h")
                }
                output.append(formatted_record)

            return JsonResponse(output, safe=False)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ✅ View: Max temperature in date range (Teacher, Student)
@csrf_exempt
@require_auth
@require_role(["Teacher", "Student"])
def max_temperature_range(request):
    if request.method == "GET":
        try:
            start = datetime.datetime.strptime(request.GET["start"], "%Y-%m-%d")
            end = datetime.datetime.strptime(request.GET["end"], "%Y-%m-%d")
            result = list(db.get_max_temperature(start, end))
            for d in result:
                d["_id"] = str(d["_id"])
            return JsonResponse(result, safe=False)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

# ✅ View: Temperature range query (Teacher, Student)
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

# ✅ Retrieve a specific record (assignment requirement)
@csrf_exempt
@require_auth
@require_role(["Teacher", "Student"])
def retrieve_specific_record(request):
    if request.method == "GET":
        try:
            sensor = request.GET.get("sensor")
            start_time = request.GET.get("start")
            end_time = request.GET.get("end")

            if not (sensor and start_time and end_time):
                return JsonResponse({"error": "Missing parameters"}, status=400)

            start = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M")
            end = datetime.datetime.strptime(end_time, "%Y-%m-%dT%H:%M")

            record = db.collection.find_one(
                {
                    "Device Name": sensor,
                    "Time": {"$gte": start, "$lte": end}
                },
                {
                    "Temperature (\u00b0C)": 1,
                    "Atmospheric Pressure (kPa)": 1,
                    "Solar Radiation (W/m2)": 1,
                    "Precipitation mm/h": 1,
                    "Time": 1,
                    "Device Name": 1
                }
            )

            if not record:
                return JsonResponse({"error": "No matching record found"}, status=404)

            # Format nicely
            response = {
                "Sensor Name": record.get("Device Name"),
                "Date/Time": record.get("Time").strftime("%d-%b-%Y %H:%M"),
                "Temperature (°C)": record.get("Temperature (\u00b0C)"),
                "Atmospheric Pressure (kPa)": record.get("Atmospheric Pressure (kPa)"),
                "Radiation (W/m2)": record.get("Solar Radiation (W/m2)"),
                "Precipitation (mm/h)": record.get("Precipitation mm/h")
            }

            return JsonResponse(response, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
        
# ✅ Retrieve max temperature for multiple records (Teacher, Student)
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

            # Group by Device Name and get Max Temperature
            pipeline = [
                {"$match": {"Time": {"$gte": start, "$lte": end}}},
                {"$group": {
                    "_id": "$Device Name",
                    "MaxTemperature": {"$max": "$Temperature (\u00b0C)"},
                    "Time": {"$first": "$Time"}
                }}
            ]

            result = list(db.collection.aggregate(pipeline))

            if not result:
                return JsonResponse({"error": "No records found"}, status=404)

            # Format output
            output = []
            for r in result:
                formatted = {
                    "Sensor Name": r.get("_id"),
                    "Reading Date/Time": r.get("Time").strftime("%d-%b-%Y %H:%M"),
                    "Max Temperature (°C)": r.get("MaxTemperature")
                }
                output.append(formatted)

            return JsonResponse(output, safe=False, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
# ✅ Retrieve all weather readings (Teacher, Student)
@csrf_exempt
@require_auth
@require_role(["Teacher", "Sensor"])
def update_multiple_weather_readings(request):
    if request.method == "PATCH":
        try:
            data = json.loads(request.body.decode())
            ids = data.get("ids", [])
            update_fields = data.get("update_fields", {})

            if not ids or not update_fields:
                return JsonResponse({"error": "ids and update_fields are required"}, status=400)

            # convert string ids to ObjectId
            from bson import ObjectId
            object_ids = [ObjectId(id) for id in ids]

            result = db.collection.update_many(
                {"_id": {"$in": object_ids}},
                {"$set": update_fields}
            )

            return JsonResponse({"message": f"Updated {result.modified_count} record(s)"})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
# ✅ Delete a weather reading (Teacher, Sensor)        
@csrf_exempt
@require_auth
@require_role(["Teacher", "Sensor"])
def delete_reading(request):
    if request.method == "DELETE":
        try:
            data = json.loads(request.body.decode())
            reading_id = data.get("_id")
            if not reading_id:
                return JsonResponse({"error": "Missing _id parameter"}, status=400)
            
            result = db.delete_reading_by_id(reading_id)
            if result.deleted_count:
                return JsonResponse({"message": "Deleted"})
            else:
                return JsonResponse({"message": "Not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
# ✅ Delete multiple weather readings (Teacher only)
@csrf_exempt
@require_auth
@require_role(["Teacher"])
def delete_multiple_readings(request):
    if request.method == "DELETE":
        try:
            data = json.loads(request.body.decode())
            ids = data.get("ids")

            if not ids or not isinstance(ids, list):
                return JsonResponse({"error": "Provide a list of IDs under 'ids'"}, status=400)

            object_ids = [ObjectId(id_str) for id_str in ids]
            result = db.collection.delete_many({"_id": {"$in": object_ids}})

            return JsonResponse({"message": f"{result.deleted_count} readings deleted"}, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
# ✅ Retrieve all weather readings (Teacher, Student)   
@csrf_exempt
@require_auth
@require_role(["Teacher", "Student"])
def projected_temperature(request):
    if request.method == "GET":
        try:
            # Find all readings with temperature > 44
            result = db.collection.find(
                {"Temperature (\u00b0C)": {"$gt": 44}},  # filter condition
                {"Device Name": 1, "Time": 1, "Temperature (\u00b0C)": 1, "_id": 0}  # projection
            )
            output = list(result)
            return JsonResponse(output, safe=False)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)




