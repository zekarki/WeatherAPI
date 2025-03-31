from django.urls import path
from djangoapp import views

urlpatterns = [
    path('', views.index, name='index'),
    path('TheModelView/', views.TheModelView.as_view(), name='TheModelView'),
    path('validate_weather/', views.validate_weather_data, name='validate_weather'),
    path('readings', views.insert_multiple_readings, name='insert_multiple_readings'),
    path('user', views.insert_user, name='insert_user'),
    path('user/delete', views.delete_user, name='delete_user'),
    path('user/update', views.update_user_access, name='update_user_access'),
    path('users/delete', views.delete_multiple_students, name='delete_multiple_students'),
    path('reading/update-precipitation', views.update_precipitation, name='update_precipitation'),
    path('analysis/precipitation', views.max_precipitation_5months, name='max_precip_5months'),
    path('analysis/temperature', views.max_temperature_range, name='max_temp_range'),
    path('analysis/indexed', views.temperature_index_query, name='temperature_index_query'),
    path('reading', views.retrieve_specific_record, name='retrieve_specific_record'),
    path('readings-max', views.retrieve_max_temp_multiple_records, name='retrieve_max_temp_multiple_records'),

]
