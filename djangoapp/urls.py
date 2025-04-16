from django.urls import path
from djangoapp import views

urlpatterns = [
    path('', views.index, name='index'),

    # ======= Weather Readings =======
    path('reading', views.reading_routes, name='reading_routes'),          # POST #1
    path('readings', views.multiple_readings, name='insert_retrive_update_multiple_readings'),  # POST #3

    # ======= Analysis =======
    path('analysis', views.max_precipitation_5months, name='max_precipitation'),        # GET #4
    path('analysis/temp', views.temperature_index_query, name='indexed_query'),         # GET #7

    # ======= Users =======
    path('user', views.insert_user, name='insert_user'),                                # POST #2
    path('user/<str:id>', views.delete_user, name='delete_user'),                       # DELETE #8
    path('users', views.multiple_users, name='delete_update_multiple_users_access'),        # DELETE #9
    # ======= Login =======
    path('login', views.login, name='login'),                                           # PATCH #12
]